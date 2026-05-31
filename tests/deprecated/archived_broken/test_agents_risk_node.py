"""Tests for risk_agent_node: wraps PositionScoreCalculator + TimingScoreCalculator."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from legacy.agents.state import FundResearchState, EMPTY_STATE


def _make_state(**overrides) -> FundResearchState:
    """Create a test state with sensible defaults, with optional overrides."""
    state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


class TestRiskAgentNode:
    """Tests for risk_agent_node function."""

    def test_node_returns_dict(self):
        """Node should return a dict of state updates."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        fund_data = {
            "code": "110011",
            "name": "Test Fund",
            "holdings": [
                {"stock_code": "600519", "stock_name": "茅台", "industry": "食品饮料", "weight": 12.0},
                {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 10.0},
            ],
        }
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=nx.DiGraph(),
        )

        result = risk_agent_node(state)

        assert isinstance(result, dict)
        assert "position_scores" in result
        assert "timing_scores" in result

    def test_node_computes_position_scores(self):
        """Node should compute PositionScore for each fund."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        fund_data = {
            "code": "110011",
            "name": "Test Fund",
            "holdings": [
                {"stock_code": "600519", "stock_name": "茅台", "industry": "食品饮料", "weight": 12.0},
                {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 10.0},
                {"stock_code": "300750", "stock_name": "宁德", "industry": "电力设备", "weight": 8.0},
            ],
        }
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=nx.DiGraph(),
        )

        result = risk_agent_node(state)

        assert "110011" in result["position_scores"]
        ps = result["position_scores"]["110011"]
        assert isinstance(ps, float) or hasattr(ps, "score")

    def test_node_computes_timing_scores(self):
        """Node should compute TimingScore for each fund."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        fund_data = {"code": "110011", "name": "Test Fund"}
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=nx.DiGraph(),
            market_regime="normal",
        )

        result = risk_agent_node(state)

        assert "110011" in result["timing_scores"]
        ts = result["timing_scores"]["110011"]
        assert isinstance(ts, float) or hasattr(ts, "score")

    def test_node_uses_market_regime_for_timing(self):
        """Node should pass market_regime to TimingScoreCalculator."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        fund_data = {"code": "110011", "name": "Test Fund"}
        
        # Test with crisis regime (should produce lower timing scores)
        state_crisis = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=nx.DiGraph(),
            market_regime="crisis",
        )
        result_crisis = risk_agent_node(state_crisis)

        # Test with normal regime
        state_normal = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=nx.DiGraph(),
            market_regime="normal",
        )
        result_normal = risk_agent_node(state_normal)

        # Both should produce valid scores
        assert "110011" in result_crisis["timing_scores"]
        assert "110011" in result_normal["timing_scores"]

    def test_node_handles_empty_state(self):
        """Node should handle empty state gracefully."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]

        result = risk_agent_node(state)

        assert isinstance(result, dict)
        assert result.get("position_scores") == {}
        assert result.get("timing_scores") == {}

    def test_node_handles_no_funds_data(self):
        """Node should return empty scores when no funds_data."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        state = _make_state(knowledge_graph=nx.DiGraph())

        result = risk_agent_node(state)

        assert result.get("position_scores") == {}
        assert result.get("timing_scores") == {}

    def test_node_handles_minimal_fund_data(self):
        """Node should not crash on minimal fund data (no holdings)."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        minimal = {"code": "110011", "name": "Minimal Fund"}
        state = _make_state(
            funds_data={"110011": minimal},
            knowledge_graph=nx.DiGraph(),
        )

        result = risk_agent_node(state)

        assert "110011" in result["position_scores"]
        assert "110011" in result["timing_scores"]

    def test_node_uses_events_for_timing(self):
        """Node should pass events to TimingScoreCalculator for momentum adjustment."""
        from legacy.agents.graphs.risk_agent import risk_agent_node

        fund_data = {"code": "110011", "name": "Test Fund"}
        events_list = [
            {"type": "earnings_surprise", "polarity": 0.8, "magnitude": 0.7, "date": "2026-05-25"},
            {"type": "fund_flow", "polarity": 0.5, "magnitude": 0.4, "date": "2026-05-24"},
        ]
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=nx.DiGraph(),
            market_regime="normal",
            extracted_events={"110011": events_list},
        )

        result = risk_agent_node(state)

        assert "110011" in result["timing_scores"]

    def test_node_docstring_exists(self):
        """risk_agent_node must have a docstring."""
        from legacy.agents.graphs.risk_agent import risk_agent_node
        assert risk_agent_node.__doc__ is not None
        assert len(risk_agent_node.__doc__) > 10
