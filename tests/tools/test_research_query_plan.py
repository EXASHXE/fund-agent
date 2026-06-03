"""Tests for src.tools.research.query_plan."""

from __future__ import annotations

import json

import pytest

from src.tools.research.query_plan import build_research_query_plan


class TestBuildResearchQueryPlan:
    def test_holdings_and_themes_generate_queries(self):
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "Test Fund"},
            ],
            holdings={
                "110011": [
                    {"name": "Company A", "weight": 0.08, "industry": "tech", "region": "CN"},
                ]
            },
            fund_profiles={
                "110011": {"fund_code": "110011", "name": "Test Fund", "fund_type": "equity"},
            },
            themes=["AI"],
            industries=["tech"],
        )
        assert len(result["news_queries"]) > 0
        assert len(result["entities"]) > 0
        assert "AI" in result["themes"]
        assert "tech" in result["industries"]

    def test_required_capabilities_include_mcp(self):
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "Test Fund"},
            ],
            themes=["AI"],
        )
        assert "web_search" in result["required_capabilities"]
        assert "financial_news" in result["required_capabilities"]

    def test_no_network_imports(self):
        from src.tools.research.query_plan import __dict__ as mod_dict
        forbidden_modules = ("requests", "httpx", "urllib.request", "urllib3")
        for key in mod_dict:
            assert "requests" not in key and "httpx" not in key, \
                f"Network-related symbol '{key}' found in query_plan module"

    def test_no_provider_imports(self):
        import sys
        forbidden = ("tavily", "finnhub", "exa", "firecrawl", "akshare", "openai", "anthropic")
        for mod_name in forbidden:
            assert mod_name not in sys.modules, f"Provider {mod_name} should not be imported"

    def test_deterministic_order(self):
        result1 = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "B Fund"},
                {"fund_code": "000001", "fund_name": "A Fund"},
            ],
        )
        result2 = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "B Fund"},
                {"fund_code": "000001", "fund_name": "A Fund"},
            ],
        )
        assert result1["news_queries"] == result2["news_queries"]
        assert result1["entities"] == result2["entities"]

    def test_query_count_capped(self):
        many_positions = [
            {"fund_code": f"F{i:04d}", "fund_name": f"Fund {i}"}
            for i in range(50)
        ]
        result = build_research_query_plan(
            portfolio_positions=many_positions,
            options={"max_news_queries": 10},
        )
        assert len(result["news_queries"]) <= 10

    def test_empty_input_returns_empty_plan(self):
        result = build_research_query_plan()
        assert result["news_queries"] == []
        assert result["sentiment_queries"] == []
        assert len(result["warnings"]) > 0

    def test_json_serializable(self):
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "Test Fund"},
            ],
            themes=["AI"],
        )
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert isinstance(parsed["news_queries"], list)

    def test_deduplicate_news_queries(self):
        """Duplicate holdings across funds should not produce duplicate queries."""
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "Fund A"},
                {"fund_code": "000001", "fund_name": "Fund B"},
            ],
            holdings={
                "110011": [{"name": "Company X", "weight": 0.08, "industry": "tech"}],
                "000001": [{"name": "Company X", "weight": 0.05, "industry": "tech"}],
            },
        )
        # Company X should appear only once in news_queries
        x_count = sum(1 for q in result["news_queries"] if "Company X" in q)
        assert x_count == 1, f"Expected 1 Company X query, got {x_count}"

    def test_query_budget_summary(self):
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": f"F{i:04d}", "fund_name": f"Fund{i}"}
                for i in range(50)
            ],
            options={"max_news_queries": 5},
        )
        assert "query_budget_summary" in result
        budget = result["query_budget_summary"]
        assert budget["max_news_queries"] == 5
        assert budget["generated_news_queries"] <= 5
        assert budget["dropped_news_queries"] > 0

    def test_sorted_by_value_descending(self):
        """Positions sorted by current_value should prioritize high-value funds."""
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "small", "fund_name": "Small Fund", "current_value": 100},
                {"fund_code": "large", "fund_name": "Large Fund", "current_value": 100000},
            ],
            options={"max_news_queries": 1},
        )
        assert len(result["news_queries"]) == 1
        # High-current-value fund should be queried first (fund_code "large")
        assert "large" in result["news_queries"][0].lower()

    def test_per_fund_holding_limit(self):
        many_holdings = [
            {"name": f"Stock {i}", "weight": 0.1 - i * 0.01}
            for i in range(10)
        ]
        result = build_research_query_plan(
            portfolio_positions=[{"fund_code": "110011", "fund_name": "Test"}],
            holdings={"110011": many_holdings},
            options={"per_fund_holding_limit": 3, "max_news_queries": 30},
        )
        # Only top 3 holdings should generate queries
        hq_count = sum(1 for q in result["news_queries"] if "Stock" in q)
        assert hq_count <= 3

    def test_empty_input_required_capabilities_empty(self):
        result = build_research_query_plan()
        assert result["required_capabilities"] == []


    def test_manager_news_included_when_opted_in(self):
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "Test Fund"},
            ],
            fund_profiles={
                "110011": {"fund_code": "110011", "name": "Test Fund", "manager": "Manager X"},
            },
            options={"include_manager_news": True},
        )
        query_text = " ".join(result["news_queries"])
        assert "Manager X" in query_text

    def test_kg_context_enriches_entities(self):
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "Test Fund"},
            ],
            kg_context={"entities": [{"name": "Extra Entity"}]},
        )
        assert "Extra Entity" in result["entities"]

    def test_macro_queries_when_opted_in(self):
        result = build_research_query_plan(
            portfolio_positions=[
                {"fund_code": "110011", "fund_name": "Test Fund"},
            ],
            options={"include_macro_news": True},
        )
        query_text = " ".join(result["news_queries"])
        assert "宏观经济" in query_text
