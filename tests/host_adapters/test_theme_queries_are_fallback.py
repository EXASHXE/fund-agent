"""Validate that theme queries are only generated as fallback when no fund-specific queries cover the topic.

When fund_name or fund_code queries already cover a topic (e.g., "半导体ETF"
covers "半导体"), the news snapshot should NOT also generate _THEME_QUERIES
expansions for that same topic in the legacy path.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_knowledge_graph_context import build_kg_context  # noqa: E402
from scripts.build_news_snapshot import _build_query_plan  # noqa: E402


def _portfolio_with_semi_conductor() -> dict:
    """Portfolio with a semiconductor fund."""
    return {
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "sector": "电子",
                "theme": "半导体",
            },
        ],
    }


def _portfolio_with_multiple_themes() -> dict:
    """Portfolio covering multiple watch topics."""
    return {
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "sector": "电子",
                "theme": "半导体",
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金A",
                "current_value": 20000,
                "sector": "债券",
                "theme": "短债",
            },
        ],
    }


class TestThemeQueriesAreFallback:
    """Theme queries should only appear as fallback when no fund-specific queries cover the topic."""

    def test_kg_context_has_fund_name_queries_for_covered_topics(self):
        """KG context must have fund_name queries for holdings that cover watch topics."""
        result = build_kg_context(_portfolio_with_semi_conductor())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        assert len(fund_name_queries) > 0
        # The fund_name query for 半导体ETF covers the 半导体 topic
        semi_queries = [qp for qp in fund_name_queries if "半导体" in qp.get("query", "")]
        assert len(semi_queries) > 0

    def test_kg_context_has_fund_code_queries(self):
        """KG context must have fund_code queries for each holding with a code."""
        result = build_kg_context(_portfolio_with_semi_conductor())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        assert len(fund_code_queries) > 0

    def test_news_snapshot_expands_fund_name_query(self):
        """News snapshot must expand fund_name query type into search queries."""
        kg_ctx = build_kg_context(_portfolio_with_semi_conductor())
        queries = _build_query_plan(kg_ctx, _portfolio_with_semi_conductor())
        # There should be queries that include the fund name + "基金 行情"
        fund_name_search_queries = [
            q for q in queries if q.get("query_type") == "fund_name" and "基金" in q.get("query", "")
        ]
        assert len(fund_name_search_queries) > 0

    def test_news_snapshot_expands_fund_code_query(self):
        """News snapshot must expand fund_code query type into search queries."""
        kg_ctx = build_kg_context(_portfolio_with_semi_conductor())
        queries = _build_query_plan(kg_ctx, _portfolio_with_semi_conductor())
        # There should be queries that include the fund code + "基金 净值"
        fund_code_search_queries = [
            q for q in queries if q.get("query_type") == "fund_code" and "基金" in q.get("query", "")
        ]
        assert len(fund_code_search_queries) > 0

    def test_theme_fallback_queries_have_lower_priority(self):
        """Theme fallback queries must have priority > fund_name/fund_code (priority 2)."""
        kg_ctx = build_kg_context(_portfolio_with_multiple_themes())
        queries = _build_query_plan(kg_ctx, _portfolio_with_multiple_themes())
        fund_specific = [q for q in queries if q["query_type"] in ("fund_name", "fund_code")]
        theme_fallback = [q for q in queries if q["query_type"] == "theme_fallback"]
        if fund_specific and theme_fallback:
            max_fund_priority = max(q["priority"] for q in fund_specific)
            min_fallback_priority = min(q["priority"] for q in theme_fallback)
            assert max_fund_priority < min_fallback_priority

    def test_covered_topics_no_theme_fallback_in_kg(self):
        """Topics covered by fund-specific queries should NOT appear as theme_fallback in KG context."""
        result = build_kg_context(_portfolio_with_semi_conductor())
        # 半导体 is covered by the holding, so it should not be in theme_fallback
        fallback_topics = [
            qp
            for qp in result["query_plan"]
            if qp["query_type"] == "theme_fallback" and "半导体" in qp.get("query", "")
        ]
        # 半导体 should be covered by the fund's theme_tags, not a fallback
        assert len(fallback_topics) == 0

    def test_uncovered_topics_have_theme_fallback(self):
        """Topics NOT covered by any holding should still appear as theme_fallback."""
        result = build_kg_context(_portfolio_with_semi_conductor())
        # 半导体 is covered, but e.g. CPO is not
        cpo_fallback = [
            qp for qp in result["query_plan"] if qp["query_type"] == "theme_fallback" and qp.get("query") == "CPO"
        ]
        assert len(cpo_fallback) > 0
