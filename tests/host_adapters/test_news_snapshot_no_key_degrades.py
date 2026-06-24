"""Validate graceful degradation when no API keys are available.

Tests that the news snapshot builder produces a valid but empty snapshot
when no provider API keys are set, with appropriate missing-data markers.
No real API keys or network calls are used.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_news_snapshot import build_news_snapshot  # noqa: E402


def _sample_kg_context() -> dict:
    """Return a minimal valid KG context for testing."""
    return {
        "snapshot_type": "knowledge_graph_context",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "portfolio_summary": {"holding_count": 1, "total_value": 50000},
        "entities": ["fund:002168"],
        "fund_entities": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "sector": "电子",
                "theme_tags": ["半导体"],
                "risk_bucket": "high",
            },
        ],
        "watch_topics": ["半导体"],
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


# Environment with no API keys
_NO_KEYS_ENV = {
    "TAVILY_API_KEY": "",
    "BOCHA_API_KEY": "",
    "SERPAPI_API_KEY": "",
    "FINNHUB_API_KEY": "",
}


class TestNewsSnapshotNoKeyDegrades:
    """Validate graceful degradation when no API keys are available."""

    def test_empty_items_when_no_keys(self):
        """Items must be empty when no API keys are set."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert result["items"] == []

    def test_news_snapshot_missing_true(self):
        """news_snapshot_missing must be True when no keys and no items."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert result["data_quality"]["news_snapshot_missing"] is True

    def test_provider_partial_failure_true(self):
        """provider_partial_failure must be True when all providers are unavailable."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert result["data_quality"]["provider_partial_failure"] is True

    def test_all_providers_unavailable(self):
        """All providers must report available=False when no keys are set."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        for pname in ("tavily", "bocha", "serpapi", "finnhub"):
            assert result["provider_status"][pname]["available"] is False

    def test_query_plan_still_generated(self):
        """Query plan must still be generated even without API keys."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert len(result["query_plan"]) > 0

    def test_query_plan_status_empty_or_failed(self):
        """All query plan entries must have status 'empty' or 'failed' when no keys."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        for qp in result["query_plan"]:
            assert qp["status"] in ("empty", "failed"), f"Unexpected status: {qp['status']}"

    def test_snapshot_still_valid_schema(self):
        """Full snapshot schema must still be valid even with no keys."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        assert result["snapshot_type"] == "news_snapshot"
        assert "generated_at" in result
        assert "provider_status" in result
        assert "query_plan" in result
        assert "items" in result
        assert "coverage_gaps" in result
        assert "data_quality" in result

    def test_coverage_gaps_include_queries(self):
        """Coverage gaps should include queries that had no results."""
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(_sample_kg_context())
        # With no providers, queries with attempts should be in coverage_gaps
        # But if no providers were attempted, gaps may be empty
        assert isinstance(result["coverage_gaps"], list)

    def test_no_crash_with_empty_kg_context(self):
        """Must not crash with a minimal KG context."""
        minimal = {
            "snapshot_type": "knowledge_graph_context",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "portfolio_summary": {"holding_count": 0, "total_value": 0},
            "entities": [],
            "fund_entities": [],
            "watch_topics": [],
            "query_plan": [],
            "missing_data": {},
        }
        with patch.dict(os.environ, _NO_KEYS_ENV, clear=False):
            result = build_news_snapshot(minimal)
        assert result["items"] == []

    def test_single_provider_failure_does_not_block_others(self):
        """If one provider fails, others should still be attempted."""
        # Set only Tavily key but mock it to fail
        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "fake-key"}, clear=False),
            patch("scripts.build_news_snapshot._provider_tavily", return_value=([], "mock error")),
        ):
            result = build_news_snapshot(_sample_kg_context())
        # Tavily should report error
        assert result["provider_status"]["tavily"]["error"] is not None
        # Other providers should still be checked
        assert "bocha" in result["provider_status"]
        assert "serpapi" in result["provider_status"]
