"""Validate KG context builder.

Tests that the knowledge graph context builder correctly processes portfolio
input, matches watch topics, generates entities, builds query plans, and
tracks missing data. No network calls or API keys needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_knowledge_graph_context import build_kg_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_portfolio() -> dict:
    """Portfolio with typical holdings across multiple sectors."""
    return {
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "sector": "电子",
                "theme": "半导体",
                "risk_bucket": "high",
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金A",
                "current_value": 20000,
                "sector": "债券",
                "theme": "短债",
                "risk_bucket": "low",
            },
            {
                "fund_code": "000961",
                "fund_name": "纳斯达克100指数",
                "current_value": 15000,
                "sector": "QDII",
                "risk_bucket": "high",
            },
        ],
    }


def _portfolio_with_missing_code() -> dict:
    """Portfolio with a holding missing fund_code."""
    return {
        "holdings": [
            {
                "fund_name": "未知基金",
                "current_value": 5000,
                "sector": "",
            },
        ],
    }


def _empty_portfolio() -> dict:
    """Empty portfolio."""
    return {"holdings": []}


def _portfolio_no_holdings_key() -> dict:
    """Portfolio dict without holdings key."""
    return {"cash_available": 10000}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKGContextBuilder:
    """Validate KG context builder behavior."""

    def test_snapshot_type(self):
        """snapshot_type must be 'knowledge_graph_context'."""
        result = build_kg_context(_sample_portfolio())
        assert result["snapshot_type"] == "knowledge_graph_context"

    def test_generated_at_present(self):
        """generated_at must be a non-empty ISO timestamp."""
        result = build_kg_context(_sample_portfolio())
        assert result["generated_at"]
        assert "T" in result["generated_at"]

    def test_portfolio_summary(self):
        """portfolio_summary must have holding_count and total_value."""
        result = build_kg_context(_sample_portfolio())
        assert result["portfolio_summary"]["holding_count"] == 3
        assert result["portfolio_summary"]["total_value"] == 65000

    def test_entities_generated(self):
        """Entities must include fund, sector, and macro entities."""
        result = build_kg_context(_sample_portfolio())
        entities = result["entities"]
        assert "fund:002168" in entities
        assert "fund:007540" in entities
        assert "fund:000961" in entities

    def test_fund_name_entities(self):
        """Entities must include fund_name: prefixed entries."""
        result = build_kg_context(_sample_portfolio())
        entities = result["entities"]
        assert any(e.startswith("fund_name:") for e in entities)

    def test_sector_entities(self):
        """Entities must include sector: prefixed entries."""
        result = build_kg_context(_sample_portfolio())
        entities = result["entities"]
        assert any(e.startswith("sector:") for e in entities)

    def test_macro_entities_from_topics(self):
        """Entities must include macro: prefixed entries for matched topics."""
        result = build_kg_context(_sample_portfolio())
        entities = result["entities"]
        macro_entities = [e for e in entities if e.startswith("macro:")]
        assert len(macro_entities) > 0

    def test_fund_entities_structure(self):
        """Each fund_entity must have fund_code, fund_name, sector, theme_tags, risk_bucket."""
        result = build_kg_context(_sample_portfolio())
        for fe in result["fund_entities"]:
            assert "fund_code" in fe
            assert "fund_name" in fe
            assert "sector" in fe
            assert "theme_tags" in fe
            assert "risk_bucket" in fe

    def test_theme_matching(self):
        """Holdings must be matched to watch topics based on keywords."""
        result = build_kg_context(_sample_portfolio())
        # 半导体ETF should match 半导体 topic
        semi_fe = [fe for fe in result["fund_entities"] if fe["fund_code"] == "002168"]
        assert len(semi_fe) == 1
        assert "半导体" in semi_fe[0]["theme_tags"]

    def test_short_debt_matching(self):
        """短债基金 should match 短债 topic."""
        result = build_kg_context(_sample_portfolio())
        bond_fe = [fe for fe in result["fund_entities"] if fe["fund_code"] == "007540"]
        assert len(bond_fe) == 1
        assert "短债" in bond_fe[0]["theme_tags"]

    def test_nasdaq_matching(self):
        """纳斯达克 fund should match 纳斯达克 and QDII topics."""
        result = build_kg_context(_sample_portfolio())
        nasdaq_fe = [fe for fe in result["fund_entities"] if fe["fund_code"] == "000961"]
        assert len(nasdaq_fe) == 1
        assert "纳斯达克" in nasdaq_fe[0]["theme_tags"]
        assert "QDII" in nasdaq_fe[0]["theme_tags"]

    def test_watch_topics_present(self):
        """watch_topics must contain all defined watch topics."""
        result = build_kg_context(_sample_portfolio())
        assert "半导体" in result["watch_topics"]
        assert "短债" in result["watch_topics"]
        assert "纳斯达克" in result["watch_topics"]
        assert len(result["watch_topics"]) == 12  # all 12 defined topics

    def test_query_plan_generated(self):
        """query_plan must be generated with at least one entry per holding."""
        result = build_kg_context(_sample_portfolio())
        assert len(result["query_plan"]) > 0
        for qp in result["query_plan"]:
            assert "query_id" in qp
            assert "query" in qp
            assert "entities" in qp
            assert "topic_tags" in qp

    def test_query_plan_deduped(self):
        """query_plan entries must have unique query_ids."""
        result = build_kg_context(_sample_portfolio())
        qids = [qp["query_id"] for qp in result["query_plan"]]
        assert len(qids) == len(set(qids))

    def test_missing_data_tracking(self):
        """missing_data must track fund_code_missing, provider_snapshot_missing, etc."""
        result = build_kg_context(_sample_portfolio())
        md = result["missing_data"]
        assert "fund_code_missing" in md
        assert "units_missing" in md
        assert "nav_missing" in md
        assert "cost_basis_missing" in md
        assert "provider_snapshot_missing" in md
        assert "manual_transactions_missing" in md

    def test_missing_fund_code_tracked(self):
        """Holdings without fund_code must be tracked in fund_code_missing."""
        result = build_kg_context(_portfolio_with_missing_code())
        assert len(result["missing_data"]["fund_code_missing"]) > 0

    def test_no_fund_code_guessing(self):
        """Missing fund codes must NOT be guessed or auto-completed."""
        result = build_kg_context(_portfolio_with_missing_code())
        for fe in result["fund_entities"]:
            if fe["fund_name"] == "未知基金":
                assert fe["fund_code"] == ""

    def test_provider_snapshot_missing_true_by_default(self):
        """provider_snapshot_missing must be True when no provider snapshot provided."""
        result = build_kg_context(_sample_portfolio())
        assert result["missing_data"]["provider_snapshot_missing"] is True

    def test_manual_transactions_missing_true_by_default(self):
        """manual_transactions_missing must be True when no CSV provided."""
        result = build_kg_context(_sample_portfolio())
        assert result["missing_data"]["manual_transactions_missing"] is True

    def test_provider_snapshot_missing_false_when_provided(self):
        """provider_snapshot_missing must be False when provider snapshot provided."""
        result = build_kg_context(_sample_portfolio(), provider_snapshot={"some": "data"})
        assert result["missing_data"]["provider_snapshot_missing"] is False

    def test_manual_transactions_missing_false_when_provided(self):
        """manual_transactions_missing must be False when CSV data provided."""
        result = build_kg_context(_sample_portfolio(), manual_transactions=[{"date": "2026-01-01"}])
        assert result["missing_data"]["manual_transactions_missing"] is False

    def test_empty_portfolio_no_crash(self):
        """Must not crash with empty portfolio."""
        result = build_kg_context(_empty_portfolio())
        assert result["portfolio_summary"]["holding_count"] == 0
        assert result["portfolio_summary"]["total_value"] == 0
        assert result["entities"] == []
        assert result["fund_entities"] == []

    def test_portfolio_without_holdings_key(self):
        """Must handle portfolio dict without 'holdings' key."""
        result = build_kg_context(_portfolio_no_holdings_key())
        assert result["portfolio_summary"]["holding_count"] == 0

    def test_risk_bucket_entities(self):
        """Risk bucket entities must be generated for classified holdings."""
        result = build_kg_context(_sample_portfolio())
        risk_entities = [e for e in result["entities"] if e.startswith("risk_bucket:")]
        assert len(risk_entities) > 0

    def test_entities_no_duplicates(self):
        """Entities list must not contain duplicates."""
        result = build_kg_context(_sample_portfolio())
        assert len(result["entities"]) == len(set(result["entities"]))
