"""Tests for research_agent_node: wraps FundamentalScoreCalculator + EventScoreCalculator."""
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
    """Minimal KG for testing."""
    from src.kg.graph import KnowledgeGraphBuilder

    fund_data = {
        "code": "110011",
        "name": "Test Fund",
        "fund_type": "混合型",
        "holdings": [
            {"stock_code": "600519", "stock_name": "茅台", "industry": "食品饮料", "weight": 12.0},
            {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 10.0},
        ],
        "sectors": [
            {"industry": "食品饮料", "sw_code": "801120", "weight": 22.0},
        ],
    }
    builder = KnowledgeGraphBuilder()
    return builder.build_from_holdings(fund_data)


class TestResearchAgentNode:
    """Tests for research_agent_node function."""

    def test_node_returns_dict(self):
        """Node should return a dict of state updates."""
        from src.agents.graphs.research_agent import research_agent_node

        fund_data = {"code": "110011", "name": "Test Fund", "holdings": [], "sectors": []}
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=_make_kg(),
        )

        result = research_agent_node(state)

        assert isinstance(result, dict)
        assert "fundamental_scores" in result
        assert "event_scores" in result

    def test_node_computes_fundamental_scores(self):
        """Node should compute FundamentalScore for each fund."""
        from src.agents.graphs.research_agent import research_agent_node

        fund_data = {
            "code": "110011",
            "name": "Test Fund",
            "holdings": [
                {"stock_code": "600519", "stock_name": "茅台", "industry": "食品饮料", "weight": 12.0},
            ],
            "sectors": [
                {"industry": "食品饮料", "sw_code": "801120", "weight": 22.0},
            ],
        }
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=_make_kg(),
        )

        result = research_agent_node(state)

        assert "110011" in result["fundamental_scores"]
        fs = result["fundamental_scores"]["110011"]
        assert isinstance(fs, float) or hasattr(fs, "score")

    def test_node_computes_event_scores(self):
        """Node should compute EventScore for each fund when events are present."""
        from src.agents.graphs.research_agent import research_agent_node

        fund_data = {"code": "110011", "name": "Test Fund"}
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=_make_kg(),
            extracted_events={
                "110011": [
                    {"type": "earnings_surprise", "polarity": 0.7, "magnitude": 0.6, "date": "2026-05-25"},
                ]
            },
        )

        result = research_agent_node(state)

        assert "110011" in result["event_scores"]
        es = result["event_scores"]["110011"]
        assert isinstance(es, float) or hasattr(es, "score")

    def test_node_handles_empty_state(self):
        """Node should handle empty state gracefully."""
        from src.agents.graphs.research_agent import research_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]

        result = research_agent_node(state)

        assert isinstance(result, dict)
        assert result.get("fundamental_scores") == {}
        assert result.get("event_scores") == {}

    def test_node_handles_no_funds_data(self):
        """Node should return empty scores when no funds_data."""
        from src.agents.graphs.research_agent import research_agent_node

        state = _make_state(knowledge_graph=_make_kg())

        result = research_agent_node(state)

        assert result.get("fundamental_scores") == {}
        assert result.get("event_scores") == {}

    def test_node_handles_empty_kg(self):
        """Node should handle empty knowledge_graph."""
        from src.agents.graphs.research_agent import research_agent_node

        fund_data = {"code": "110011", "name": "Test Fund"}
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=nx.DiGraph(),
        )

        result = research_agent_node(state)

        assert "110011" in result["fundamental_scores"]

    def test_node_handles_multiple_funds(self):
        """Node should process multiple funds."""
        from src.agents.graphs.research_agent import research_agent_node

        fund_a = {"code": "110011", "name": "Fund A"}
        fund_b = {"code": "000001", "name": "Fund B"}
        state = _make_state(
            funds_data={"110011": fund_a, "000001": fund_b},
            knowledge_graph=_make_kg(),
        )

        result = research_agent_node(state)

        assert "110011" in result["fundamental_scores"]
        assert "000001" in result["fundamental_scores"]
        assert "110011" in result["event_scores"]
        assert "000001" in result["event_scores"]

    def test_node_docstring_exists(self):
        """research_agent_node must have a docstring."""
        from src.agents.graphs.research_agent import research_agent_node
        assert research_agent_node.__doc__ is not None
        assert len(research_agent_node.__doc__) > 10
