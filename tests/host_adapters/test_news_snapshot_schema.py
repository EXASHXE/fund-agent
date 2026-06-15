"""Validate news snapshot output schema.

Tests that the news snapshot produced by build_news_snapshot conforms to the
required output schema, including all mandatory top-level keys, provider_status
structure, query_plan structure, item structure, and data_quality markers.

Uses mock provider responses — no real API keys needed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_news_snapshot import build_news_snapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_kg_context() -> dict:
    """Return a minimal valid KG context for testing."""
    return {
        "snapshot_type": "knowledge_graph_context",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "portfolio_summary": {"holding_count": 2, "total_value": 100000},
        "entities": ["fund:002168", "sector:semiconductor"],
        "fund_entities": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "sector": "电子",
                "theme_tags": ["半导体"],
                "risk_bucket": "high",
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金",
                "sector": "债券",
                "theme_tags": ["短债"],
                "risk_bucket": "low",
            },
        ],
        "watch_topics": ["半导体", "短债"],
        "query_plan": [
            {
                "query_id": "abc123",
                "query": "半导体ETF",
                "entities": ["fund:002168"],
                "topic_tags": ["半导体"],
            },
        ],
        "missing_data": {
            "fund_code_missing": [],
            "units_missing": [],
            "nav_missing": [],
            "cost_basis_missing": [],
            "provider_snapshot_missing": True,
            "manual_transactions_missing": True,
        },
    }


def _mock_tavily_success(query: str, max_results: int):
    """Mock successful Tavily response."""
    return (
        [
            {
                "title": f"半导体行业分析: {query}",
                "url": f"https://example.com/news/{hash(query) % 1000}",
                "source": "test-source",
                "published_at": "2026-06-14T10:00:00+00:00",
                "summary": f"关于{query}的最新分析报告",
            },
        ],
        None,
    )


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestNewsSnapshotSchema:
    """Validate the top-level schema of news snapshot output."""

    def test_snapshot_type(self):
        """snapshot_type must be 'news_snapshot'."""
        with patch.dict(os.environ, {"TAVILY_API_KEY": ""}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert result["snapshot_type"] == "news_snapshot"

    def test_generated_at_present(self):
        """generated_at must be a non-empty ISO timestamp."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert result["generated_at"]
        assert "T" in result["generated_at"]

    def test_lookback_days_is_int(self):
        """lookback_days must be a positive integer."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert isinstance(result["lookback_days"], int)
        assert result["lookback_days"] > 0

    def test_provider_status_structure(self):
        """provider_status must contain all four providers with available+error."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        ps = result["provider_status"]
        for pname in ("tavily", "bocha", "serpapi", "finnhub"):
            assert pname in ps, f"Missing provider: {pname}"
            assert "available" in ps[pname], f"Missing 'available' for {pname}"
            assert "error" in ps[pname], f"Missing 'error' for {pname}"

    def test_query_plan_structure(self):
        """query_plan entries must have query_id, query, entities, topic_tags, provider_attempts, status."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        for qp in result["query_plan"]:
            assert "query_id" in qp
            assert "query" in qp
            assert "entities" in qp
            assert "topic_tags" in qp
            assert "provider_attempts" in qp
            assert "status" in qp
            assert qp["status"] in ("ok", "empty", "failed")

    def test_items_structure_with_mock(self):
        """When providers return items, each item must have all required fields."""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-key"}, clear=False):
            with patch("scripts.build_news_snapshot._provider_tavily", side_effect=_mock_tavily_success):
                result = build_news_snapshot(_sample_kg_context())
                if result["items"]:
                    item = result["items"][0]
                    required_fields = [
                        "id",
                        "provider",
                        "query",
                        "title",
                        "url",
                        "source",
                        "published_at",
                        "summary",
                        "language",
                        "related_entities",
                        "topic_tags",
                        "relevance_score",
                        "freshness_score",
                        "confidence",
                    ]
                    for field in required_fields:
                        assert field in item, f"Missing field: {field}"

    def test_data_quality_structure(self):
        """data_quality must have all required markers."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        dq = result["data_quality"]
        assert "news_snapshot_missing" in dq
        assert "provider_partial_failure" in dq
        assert "stale_news" in dq
        assert "low_coverage_topics" in dq

    def test_coverage_gaps_is_list(self):
        """coverage_gaps must be a list."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert isinstance(result["coverage_gaps"], list)

    def test_items_is_list(self):
        """items must be a list."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert isinstance(result["items"], list)

    def test_query_plan_capped_at_30(self):
        """query_plan must not exceed 30 entries."""
        with patch.dict(os.environ, {}, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert len(result["query_plan"]) <= 30

    def test_item_relevance_score_range(self):
        """relevance_score must be between 0 and 1."""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-key"}, clear=False):
            with patch("scripts.build_news_snapshot._provider_tavily", side_effect=_mock_tavily_success):
                result = build_news_snapshot(_sample_kg_context())
                for item in result["items"]:
                    assert 0.0 <= item["relevance_score"] <= 1.0

    def test_item_freshness_score_range(self):
        """freshness_score must be between 0 and 1."""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-key"}, clear=False):
            with patch("scripts.build_news_snapshot._provider_tavily", side_effect=_mock_tavily_success):
                result = build_news_snapshot(_sample_kg_context())
                for item in result["items"]:
                    assert 0.0 <= item["freshness_score"] <= 1.0
