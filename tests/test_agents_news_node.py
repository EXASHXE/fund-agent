"""Tests for news_agent_node: LangGraph node wrapping NewsPipeline."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from src.agents.state import FundResearchState, EMPTY_STATE


def _make_state(**overrides) -> FundResearchState:
    """Create a test state with sensible defaults, with optional overrides."""
    state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _make_kg() -> nx.DiGraph:
    """Create a minimal KG for testing."""
    g = nx.DiGraph()
    g.add_node("fund:110011", data={"code": "110011"})
    g.add_node("stock:600519", data={"code": "600519", "name": "茅台"})
    g.add_node("stock:000858", data={"code": "000858", "name": "五粮液"})
    g.add_edge("fund:110011", "stock:600519")
    g.add_edge("fund:110011", "stock:000858")
    return g


def _mock_pipeline_result(fund_codes: list[str]) -> dict:
    """Return a mock NewsPipeline.run() result dict."""
    return {
        code: {
            "search_plan": {
                "fund_code": code,
                "stocks": ["600519", "000858"],
                "heavy_holdings": ["600519"],
            },
            "classified_news": [
                {"title": f"News for {code}", "layer": "heavy_holding"}
            ],
            "scored_news": [
                {"title": f"Scored news for {code}", "relevance_score": 0.85}
            ],
            "research_summaries": [
                {"fund_code": code, "what": "Test event", "confidence": 0.7}
            ],
            "events": [
                {"type": "earnings_surprise", "polarity": 0.6, "magnitude": 0.5, "date": "2026-05-25", "id": "evt-1"}
            ],
            "raw_news_count": 5,
            "stages_completed": ["entity_extraction", "targeted_retrieval"],
        }
        for code in fund_codes
    }


class TestNewsAgentNode:
    """Tests for news_agent_node function."""

    def test_node_returns_dict(self):
        """Node should return a dict of state updates (LangGraph pattern)."""
        from src.agents.graphs.news_agent import news_agent_node

        state = _make_state(
            funds_data={"110011": {"code": "110011", "name": "Test"}},
            knowledge_graph=_make_kg(),
        )

        with patch("src.agents.graphs.news_agent.NewsPipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = _mock_pipeline_result(["110011"])
            mock_pipeline_cls.return_value = mock_pipeline

            result = news_agent_node(state)

        assert isinstance(result, dict)
        assert "search_plans" in result

    def test_node_populates_news_fields(self):
        """Node should populate search_plans, classified_news, scored_news, etc."""
        from src.agents.graphs.news_agent import news_agent_node

        state = _make_state(
            funds_data={"110011": {"code": "110011", "name": "Test"}},
            knowledge_graph=_make_kg(),
        )

        with patch("src.agents.graphs.news_agent.NewsPipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = _mock_pipeline_result(["110011"])
            mock_pipeline_cls.return_value = mock_pipeline

            result = news_agent_node(state)

        assert "110011" in result["search_plans"]
        assert "110011" in result["raw_news"]
        assert "110011" in result["classified_news"]
        assert "110011" in result["scored_news"]
        assert "110011" in result["research_summaries"]
        assert "110011" in result["extracted_events"]

    def test_node_handles_empty_state(self):
        """Node should handle empty state gracefully, returning empty updates."""
        from src.agents.graphs.news_agent import news_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]

        with patch("src.agents.graphs.news_agent.NewsPipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = {}
            mock_pipeline_cls.return_value = mock_pipeline

            result = news_agent_node(state)

        # Should not crash, return empty updates
        assert isinstance(result, dict)

    def test_node_handles_no_funds_data(self):
        """Node should handle state without funds_data gracefully."""
        from src.agents.graphs.news_agent import news_agent_node

        state = _make_state(knowledge_graph=_make_kg())

        with patch("src.agents.graphs.news_agent.NewsPipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = {}
            mock_pipeline_cls.return_value = mock_pipeline

            result = news_agent_node(state)

        assert isinstance(result, dict)
        assert result.get("search_plans") == {}

    def test_node_does_not_fetch_market_news_without_kg_fund_node(self):
        """Node should not run broad market retrieval when KG has no fund node."""
        from src.agents.graphs.news_agent import news_agent_node

        state = _make_state(
            funds_data={"110011": {"code": "110011", "name": "Test"}},
            knowledge_graph=nx.DiGraph(),
        )

        with patch("src.news.retriever.Retriever.retrieve_market_news") as mock_market:
            result = news_agent_node(state)

        mock_market.assert_not_called()
        assert result["search_plans"]["110011"].fund_code == "110011"
        assert result["scored_news"]["110011"] == []

    def test_node_handles_multiple_funds(self):
        """Node should process multiple funds from funds_data."""
        from src.agents.graphs.news_agent import news_agent_node

        state = _make_state(
            funds_data={
                "110011": {"code": "110011", "name": "Fund A"},
                "000001": {"code": "000001", "name": "Fund B"},
            },
            knowledge_graph=_make_kg(),
        )

        with patch("src.agents.graphs.news_agent.NewsPipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = _mock_pipeline_result(["110011", "000001"])
            mock_pipeline_cls.return_value = mock_pipeline

            result = news_agent_node(state)

        assert "110011" in result["search_plans"]
        assert "000001" in result["search_plans"]

    def test_node_converts_kg_dict_to_nx_graph(self):
        """Node should handle knowledge_graph as dict (serialized form) by converting to nx.DiGraph."""
        from src.agents.graphs.news_agent import news_agent_node

        # knowledge_graph stored as dict (serialized)
        kg_dict = {
            "nodes": [
                {"id": "fund:110011", "type": "fund"},
                {"id": "stock:600519", "type": "stock"},
            ],
            "edges": [
                {"source": "fund:110011", "target": "stock:600519", "type": "holds"},
            ],
        }

        state = _make_state(
            funds_data={"110011": {"code": "110011", "name": "Test"}},
            knowledge_graph=kg_dict,
        )

        with patch("src.agents.graphs.news_agent.NewsPipeline") as mock_pipeline_cls:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = _mock_pipeline_result(["110011"])
            mock_pipeline_cls.return_value = mock_pipeline

            result = news_agent_node(state)

        assert "110011" in result.get("search_plans", {})

    def test_node_docstring_exists(self):
        """news_agent_node must have a docstring."""
        from src.agents.graphs.news_agent import news_agent_node
        assert news_agent_node.__doc__ is not None
        assert len(news_agent_node.__doc__) > 10
