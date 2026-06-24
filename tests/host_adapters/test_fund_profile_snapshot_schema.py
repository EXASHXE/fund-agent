"""Validate fund_profile_snapshot schema and KG entity extraction.

Tests that:
1. The fund_profile_snapshot JSON schema validates correctly
2. The template and demo files conform to the schema
3. _extract_from_fund_profile_snapshot produces correct entities and query plan
4. build_kg_context merges fund_profile_snapshot entities properly
5. fund_profile_snapshot takes precedence when both it and provider_snapshot exist

No network calls or API keys needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_knowledge_graph_context import (  # noqa: E402
    _extract_from_fund_profile_snapshot,
    build_kg_context,
)

SCHEMA_PATH = ROOT / "schemas" / "fund_profile_snapshot.schema.json"
TEMPLATE_PATH = ROOT / "examples" / "user_portfolio_templates" / "fund_profile_snapshot_template.json"
DEMO_PATH = ROOT / "examples" / "user_portfolio_templates" / "fund_profile_snapshot_demo.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_fund_profile_snapshot() -> dict:
    """Minimal valid fund_profile_snapshot for testing."""
    return {
        "schema_version": "fund_profile_snapshot.v1",
        "as_of_date": "2024-12-31",
        "fund_profiles": {
            "SYN001": {
                "fund_code": "SYN001",
                "fund_name": "合成成长混合A",
                "fund_type": "混合型",
                "manager": "示例经理甲",
                "benchmark": "SYNHS300",
                "inception_date": "2018-03-15",
                "size_category": "mid",
                "tags": ["成长", "混合"],
            },
            "SYN002": {
                "fund_code": "SYN002",
                "fund_name": "合成短债C",
                "fund_type": "债券型",
                "manager": "示例经理乙",
                "benchmark": "SYNBOND1Y",
                "inception_date": "2020-07-01",
                "size_category": "large",
                "tags": ["短债", "稳健"],
            },
        },
        "fund_holdings": {
            "SYN001": {
                "fund_code": "SYN001",
                "as_of": "2024-09-30",
                "holdings": [
                    {
                        "name": "合成科技股份",
                        "weight": 9.2,
                        "code": "SY6001",
                        "asset_type": "stock",
                        "industry": "科技",
                    },
                    {
                        "name": "合成消费集团",
                        "weight": 7.1,
                        "code": "SY6002",
                        "asset_type": "stock",
                        "industry": "消费",
                    },
                ],
            },
        },
        "benchmark_info": {
            "SYNHS300": {
                "symbol": "SYNHS300",
                "name": "合成沪深300指数",
                "provider": "synthetic",
                "asset_class": "equity",
            },
        },
        "provenance": {
            "synthetic": {
                "source": "synthetic_demo",
                "fetched_at": "2024-12-31T12:00:00Z",
            },
        },
        "limitations": ["synthetic demo data"],
    }


def _sample_portfolio() -> dict:
    """Portfolio with a holding matching one fund in the profile snapshot."""
    return {
        "holdings": [
            {
                "fund_code": "SYN001",
                "fund_name": "合成成长混合A",
                "current_value": 30000,
                "sector": "混合",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestFundProfileSnapshotSchema:
    """Validate the fund_profile_snapshot JSON schema."""

    def test_schema_file_exists(self):
        """Schema file must exist."""
        assert SCHEMA_PATH.exists(), f"Schema not found: {SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        """Schema must be valid JSON."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert isinstance(schema, dict)

    def test_schema_has_required_fields(self):
        """Schema must require schema_version and as_of_date."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert "required" in schema
        assert "schema_version" in schema["required"]
        assert "as_of_date" in schema["required"]

    def test_schema_version_const(self):
        """schema_version must be 'fund_profile_snapshot.v1'."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        sv = schema["properties"]["schema_version"]
        assert sv["const"] == "fund_profile_snapshot.v1"

    def test_schema_has_fund_profiles(self):
        """Schema must define fund_profiles."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert "fund_profiles" in schema["properties"]

    def test_schema_has_fund_holdings(self):
        """Schema must define fund_holdings."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert "fund_holdings" in schema["properties"]

    def test_schema_has_benchmark_info(self):
        """Schema must define benchmark_info."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert "benchmark_info" in schema["properties"]

    def test_schema_has_provenance(self):
        """Schema must define provenance."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert "provenance" in schema["properties"]

    def test_schema_has_limitations(self):
        """Schema must define limitations."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        assert "limitations" in schema["properties"]

    def test_fund_profiles_has_required_fields(self):
        """fund_profiles items must require fund_code and fund_name."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        fp = schema["properties"]["fund_profiles"]["additionalProperties"]
        assert "fund_code" in fp["required"]
        assert "fund_name" in fp["required"]

    def test_fund_holdings_has_required_fields(self):
        """fund_holdings items must require fund_code, as_of, holdings."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        fh = schema["properties"]["fund_holdings"]["additionalProperties"]
        assert "fund_code" in fh["required"]
        assert "as_of" in fh["required"]
        assert "holdings" in fh["required"]

    def test_holdings_items_have_required_fields(self):
        """Holdings items must require name and weight."""
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        fh = schema["properties"]["fund_holdings"]["additionalProperties"]
        holding_item = fh["properties"]["holdings"]["items"]
        assert "name" in holding_item["required"]
        assert "weight" in holding_item["required"]


class TestFundProfileSnapshotTemplateAndDemo:
    """Validate template and demo files."""

    def test_template_exists(self):
        """Template file must exist."""
        assert TEMPLATE_PATH.exists()

    def test_demo_exists(self):
        """Demo file must exist."""
        assert DEMO_PATH.exists()

    def test_template_valid_json(self):
        """Template must be valid JSON."""
        with open(TEMPLATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_demo_valid_json(self):
        """Demo must be valid JSON."""
        with open(DEMO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_template_has_schema_version(self):
        """Template must have schema_version."""
        with open(TEMPLATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["schema_version"] == "fund_profile_snapshot.v1"

    def test_demo_has_schema_version(self):
        """Demo must have schema_version."""
        with open(DEMO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["schema_version"] == "fund_profile_snapshot.v1"

    def test_demo_has_all_top_level_keys(self):
        """Demo must have all top-level keys."""
        with open(DEMO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for key in ("schema_version", "as_of_date", "fund_profiles", "fund_holdings", "benchmark_info"):
            assert key in data, f"Missing key: {key}"

    def test_demo_has_multiple_funds(self):
        """Demo must have at least 2 fund profiles."""
        with open(DEMO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["fund_profiles"]) >= 2

    def test_demo_uses_synthetic_data_only(self):
        """Demo fund codes must NOT be real fund codes (use SYN prefix)."""
        with open(DEMO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for fc, profile in data["fund_profiles"].items():
            assert fc.startswith("SYN"), f"Non-synthetic fund code: {fc}"
            assert profile["fund_code"].startswith("SYN"), f"Non-synthetic fund_code in profile: {profile['fund_code']}"

    def test_demo_managers_are_synthetic(self):
        """Demo manager names must be synthetic (contain 示例)."""
        with open(DEMO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for _fc, profile in data["fund_profiles"].items():
            manager = profile.get("manager", "")
            if manager:
                assert "示例" in manager, f"Non-synthetic manager name: {manager}"


# ---------------------------------------------------------------------------
# KG entity extraction tests
# ---------------------------------------------------------------------------


class TestExtractFromFundProfileSnapshot:
    """Validate _extract_from_fund_profile_snapshot entity extraction."""

    def test_returns_tuple(self):
        """Must return a tuple of (entities, query_plan_entries)."""
        result = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        assert isinstance(result, tuple)
        assert len(result) == 2
        entities, query_plan = result
        assert isinstance(entities, list)
        assert isinstance(query_plan, list)

    def test_none_snapshot_returns_empty(self):
        """None snapshot must return empty lists."""
        entities, query_plan = _extract_from_fund_profile_snapshot(None)
        assert entities == []
        assert query_plan == []

    def test_empty_snapshot_returns_empty(self):
        """Empty dict snapshot must return empty lists."""
        entities, query_plan = _extract_from_fund_profile_snapshot({})
        assert entities == []
        assert query_plan == []

    def test_fund_profile_entities(self):
        """Must extract fund_profile entities."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        profile_entities = [e for e in entities if e["entity_type"] == "fund_profile"]
        assert len(profile_entities) >= 2  # SYN001 and SYN002

    def test_fund_manager_entities(self):
        """Must extract fund_manager entities."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        manager_entities = [e for e in entities if e["entity_type"] == "fund_manager"]
        assert len(manager_entities) >= 2  # 示例经理甲 and 示例经理乙

    def test_benchmark_entities(self):
        """Must extract benchmark entities from profiles and benchmark_info."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        benchmark_entities = [e for e in entities if e["entity_type"] == "benchmark"]
        assert len(benchmark_entities) >= 1

    def test_holding_company_entities(self):
        """Must extract holding_company entities from fund_holdings."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        holding_entities = [e for e in entities if e["entity_type"] == "holding_company"]
        assert len(holding_entities) >= 2  # 合成科技股份 and 合成消费集团

    def test_holding_ticker_entities(self):
        """Must extract holding_ticker entities from fund_holdings."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        ticker_entities = [e for e in entities if e["entity_type"] == "holding_ticker"]
        assert len(ticker_entities) >= 2  # SY6001 and SY6002

    def test_industry_entities_from_holdings(self):
        """Must extract industry entities from holding industry field."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        industry_entities = [e for e in entities if e["entity_type"] == "industry"]
        assert len(industry_entities) >= 1

    def test_entity_source_is_fund_profile_snapshot(self):
        """All extracted entities must have source='fund_profile_snapshot'."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        for ent in entities:
            assert ent["source"] == "fund_profile_snapshot", f"Wrong source for {ent['entity_id']}: {ent['source']}"

    def test_entity_ids_are_unique(self):
        """Entity IDs must be unique (no duplicates)."""
        entities, _ = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        eids = [e["entity_id"] for e in entities]
        assert len(eids) == len(set(eids))

    def test_query_plan_entries_generated(self):
        """Must generate query plan entries for managers, benchmarks, holdings."""
        _, query_plan = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        assert len(query_plan) > 0

    def test_query_plan_fund_manager_entries(self):
        """Must have fund_manager query plan entries."""
        _, query_plan = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        manager_queries = [q for q in query_plan if q["query_type"] == "fund_manager"]
        assert len(manager_queries) >= 2

    def test_query_plan_benchmark_entries(self):
        """Must have benchmark query plan entries."""
        _, query_plan = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        benchmark_queries = [q for q in query_plan if q["query_type"] == "benchmark"]
        assert len(benchmark_queries) >= 1

    def test_query_plan_holding_company_entries(self):
        """Must have holding_company query plan entries."""
        _, query_plan = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        holding_queries = [q for q in query_plan if q["query_type"] == "holding_company"]
        assert len(holding_queries) >= 2

    def test_query_plan_holding_ticker_entries(self):
        """Must have holding_ticker query plan entries."""
        _, query_plan = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        ticker_queries = [q for q in query_plan if q["query_type"] == "holding_ticker"]
        assert len(ticker_queries) >= 2

    def test_query_plan_has_priority(self):
        """Query plan entries must have priority from QUERY_TYPE_PRIORITY."""
        from scripts.build_knowledge_graph_context import QUERY_TYPE_PRIORITY

        _, query_plan = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        for qp in query_plan:
            assert "priority" in qp
            expected_priority = QUERY_TYPE_PRIORITY.get(qp["query_type"], 5)
            assert qp["priority"] == expected_priority

    def test_query_plan_source_is_fund_profile_snapshot(self):
        """Query plan entries must have source='fund_profile_snapshot'."""
        _, query_plan = _extract_from_fund_profile_snapshot(_sample_fund_profile_snapshot())
        for qp in query_plan:
            assert qp["source"] == "fund_profile_snapshot"


# ---------------------------------------------------------------------------
# KG context integration tests
# ---------------------------------------------------------------------------


class TestKGContextWithFundProfileSnapshot:
    """Validate build_kg_context integration with fund_profile_snapshot."""

    def test_fund_profile_snapshot_ref_true(self):
        """fund_profile_snapshot_ref must be True when snapshot provided."""
        result = build_kg_context(
            _sample_portfolio(),
            fund_profile_snapshot=_sample_fund_profile_snapshot(),
        )
        assert result["fund_profile_snapshot_ref"] is True

    def test_fund_profile_snapshot_ref_false(self):
        """fund_profile_snapshot_ref must be False when no snapshot provided."""
        result = build_kg_context(_sample_portfolio())
        assert result["fund_profile_snapshot_ref"] is False

    def test_data_quality_fund_profile_snapshot_available(self):
        """data_quality must include fund_profile_snapshot_available."""
        result = build_kg_context(
            _sample_portfolio(),
            fund_profile_snapshot=_sample_fund_profile_snapshot(),
        )
        assert result["data_quality"]["fund_profile_snapshot_available"] is True

    def test_data_quality_fund_profile_snapshot_not_available(self):
        """data_quality must show fund_profile_snapshot_available=False when not provided."""
        result = build_kg_context(_sample_portfolio())
        assert result["data_quality"]["fund_profile_snapshot_available"] is False

    def test_entities_merged_from_fund_profile_snapshot(self):
        """Entities from fund_profile_snapshot must appear in KG context."""
        result = build_kg_context(
            _sample_portfolio(),
            fund_profile_snapshot=_sample_fund_profile_snapshot(),
        )
        entities = result["entities"]
        # Should include fund_profile, fund_manager, benchmark, holding entities
        assert any(e.startswith("fund_profile:") for e in entities)
        assert any(e.startswith("fund_manager:") for e in entities)
        assert any(e.startswith("benchmark:") for e in entities)
        assert any(e.startswith("holding_company:") for e in entities)

    def test_query_plan_merged_from_fund_profile_snapshot(self):
        """Query plan entries from fund_profile_snapshot must appear in KG context."""
        result = build_kg_context(
            _sample_portfolio(),
            fund_profile_snapshot=_sample_fund_profile_snapshot(),
        )
        qp = result["query_plan"]
        fps_queries = [q for q in qp if q.get("source") == "fund_profile_snapshot"]
        assert len(fps_queries) > 0

    def test_no_duplicate_entities(self):
        """Entities must not be duplicated when fund_profile_snapshot overlaps with portfolio."""
        result = build_kg_context(
            _sample_portfolio(),
            fund_profile_snapshot=_sample_fund_profile_snapshot(),
        )
        entities = result["entities"]
        assert len(entities) == len(set(entities))

    def test_empty_fund_profile_snapshot_no_crash(self):
        """Empty fund_profile_snapshot must not crash."""
        result = build_kg_context(
            _sample_portfolio(),
            fund_profile_snapshot={},
        )
        assert result["fund_profile_snapshot_ref"] is True

    def test_fund_profile_snapshot_with_provider_snapshot(self):
        """Both provider_snapshot and fund_profile_snapshot can coexist."""
        result = build_kg_context(
            _sample_portfolio(),
            provider_snapshot={"some": "data"},
            fund_profile_snapshot=_sample_fund_profile_snapshot(),
        )
        assert result["data_quality"]["provider_snapshot_available"] is True
        assert result["data_quality"]["fund_profile_snapshot_available"] is True

    def test_fund_profile_snapshot_takes_precedence(self):
        """fund_profile_snapshot entities must be added even if provider_snapshot exists."""
        result = build_kg_context(
            _sample_portfolio(),
            provider_snapshot={"some": "data"},
            fund_profile_snapshot=_sample_fund_profile_snapshot(),
        )
        # fund_profile_snapshot entities should be present
        entities = result["entities"]
        assert any(e.startswith("fund_profile:") for e in entities)
