"""Validate that fund_name and fund_code query plan entries have priority 2.

These queries must always be generated from portfolio_input (not dependent
on provider_snapshot or fund_profile_snapshot) and must have priority=2.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_knowledge_graph_context import QUERY_TYPE_PRIORITY, build_kg_context  # noqa: E402


def _portfolio_two_holdings() -> dict:
    """Portfolio with two holdings, no provider data."""
    return {
        "holdings": [
            {
                "fund_code": "002168",
                "fund_name": "半导体ETF",
                "current_value": 30000,
                "sector": "电子",
            },
            {
                "fund_code": "007540",
                "fund_name": "短债基金A",
                "current_value": 20000,
                "sector": "债券",
            },
        ],
    }


class TestFundNameFundCodeQueryPlanPriority:
    """fund_name and fund_code query plan entries must have priority 2."""

    def test_fund_name_in_query_type_priority(self):
        """fund_name must be in QUERY_TYPE_PRIORITY dict."""
        assert "fund_name" in QUERY_TYPE_PRIORITY

    def test_fund_code_in_query_type_priority(self):
        """fund_code must be in QUERY_TYPE_PRIORITY dict."""
        assert "fund_code" in QUERY_TYPE_PRIORITY

    def test_fund_name_priority_is_2(self):
        """fund_name priority must be 2."""
        assert QUERY_TYPE_PRIORITY["fund_name"] == 2

    def test_fund_code_priority_is_2(self):
        """fund_code priority must be 2."""
        assert QUERY_TYPE_PRIORITY["fund_code"] == 2

    def test_fund_name_query_plan_entry_generated(self):
        """fund_name query plan entry must be generated for each holding with fund_name."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        assert len(fund_name_queries) >= 2  # one per holding

    def test_fund_code_query_plan_entry_generated(self):
        """fund_code query plan entry must be generated for each holding with fund_code."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        assert len(fund_code_queries) >= 2  # one per holding

    def test_fund_name_query_priority_is_2(self):
        """fund_name query plan entries must have priority=2."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        for qp in fund_name_queries:
            assert qp["priority"] == 2

    def test_fund_code_query_priority_is_2(self):
        """fund_code query plan entries must have priority=2."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        for qp in fund_code_queries:
            assert qp["priority"] == 2

    def test_fund_name_query_entities_format(self):
        """fund_name query plan entities must use 'fund_name:{name}' format."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        for qp in fund_name_queries:
            assert any(e.startswith("fund_name:") for e in qp["entities"])

    def test_fund_code_query_entities_format(self):
        """fund_code query plan entities must use 'fund:{code}' format."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        for qp in fund_code_queries:
            assert any(e.startswith("fund:") for e in qp["entities"])

    def test_fund_name_query_source_is_portfolio_input(self):
        """fund_name query plan entries must have source='portfolio_input'."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        for qp in fund_name_queries:
            assert qp["source"] == "portfolio_input"

    def test_fund_code_query_source_is_portfolio_input(self):
        """fund_code query plan entries must have source='portfolio_input'."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        for qp in fund_code_queries:
            assert qp["source"] == "portfolio_input"

    def test_fund_name_queries_generated_without_provider(self):
        """fund_name queries must be generated even without provider_snapshot."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        assert len(fund_name_queries) >= 2

    def test_fund_code_queries_generated_without_provider(self):
        """fund_code queries must be generated even without provider_snapshot."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        assert len(fund_code_queries) >= 2

    def test_fund_name_queries_not_fallback(self):
        """fund_name queries must not be marked as fallback."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        for qp in fund_name_queries:
            assert qp["fallback"] is False

    def test_fund_code_queries_not_fallback(self):
        """fund_code queries must not be marked as fallback."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        for qp in fund_code_queries:
            assert qp["fallback"] is False

    def test_fund_name_query_reason_mentions_portfolio(self):
        """fund_name query reason must mention portfolio."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_name_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_name"]
        for qp in fund_name_queries:
            assert "portfolio" in qp["reason"].lower() or "Fund name from portfolio" in qp["reason"]

    def test_fund_code_query_reason_mentions_portfolio(self):
        """fund_code query reason must mention portfolio."""
        result = build_kg_context(_portfolio_two_holdings())
        fund_code_queries = [qp for qp in result["query_plan"] if qp["query_type"] == "fund_code"]
        for qp in fund_code_queries:
            assert "portfolio" in qp["reason"].lower() or "Fund code from portfolio" in qp["reason"]

    def test_fund_name_queries_before_provider_dependent_queries(self):
        """fund_name queries (priority 2) must appear before provider-dependent queries of same or lower priority."""
        result = build_kg_context(_portfolio_two_holdings())
        # fund_name queries should appear before sector (priority 3) and theme (priority 3)
        query_types_by_order = [qp["query_type"] for qp in result["query_plan"]]
        fund_name_indices = [i for i, t in enumerate(query_types_by_order) if t == "fund_name"]
        sector_indices = [i for i, t in enumerate(query_types_by_order) if t == "sector"]
        if fund_name_indices and sector_indices:
            assert min(fund_name_indices) < max(sector_indices)
