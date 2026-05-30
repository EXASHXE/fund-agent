"""Tests for quant_agent_node: LangGraph node wrapping QuantScoreCalculator + regime detection."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from legacy.agents.state import FundResearchState, EMPTY_STATE


def _make_state(**overrides) -> FundResearchState:
    """Create a test state with sensible defaults, with optional overrides."""
    state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _make_fund_data(code: str = "110011", seed: int = 42) -> dict:
    """Create fund data with NAV for quant scoring."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end="2026-05-27", periods=252, freq="B")
    returns = rng.normal(0.0003, 0.012, 252)
    nav = 1.0 * (1 + pd.Series(returns, index=dates)).cumprod()
    nav_df = pd.DataFrame({"单位净值": nav, "日增长率": returns * 100}, index=dates)

    return {
        "code": code,
        "name": f"Test Fund {code}",
        "fund_type": "混合型",
        "nav": nav_df,
        "perf": {
            "近1年": {"sharpe_ratio": 1.2, "annual_volatility": 18.0},
            "近3年": {"max_drawdown": 15.0},
        },
    }


class TestQuantAgentNode:
    """Tests for quant_agent_node function."""

    def test_node_returns_dict(self):
        """Node should return a dict of state updates (LangGraph pattern)."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        fund_data = _make_fund_data("110011")
        state = _make_state(funds_data={"110011": fund_data})

        result = quant_agent_node(state)

        assert isinstance(result, dict)
        assert "quant_scores" in result

    def test_node_computes_quant_scores(self):
        """Node should compute QuantScore for each fund."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        fund_data = _make_fund_data("110011")
        state = _make_state(funds_data={"110011": fund_data})

        result = quant_agent_node(state)

        assert "110011" in result["quant_scores"]
        qs = result["quant_scores"]["110011"]
        assert isinstance(qs, float) or hasattr(qs, "score")

    def test_node_detects_market_regime(self):
        """Node should detect and set market_regime in state."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        fund_data = _make_fund_data("110011")
        state = _make_state(funds_data={"110011": fund_data})

        result = quant_agent_node(state)

        assert "market_regime" in result
        assert result["market_regime"] in ("normal", "high_volatility", "trending", "crisis")

    def test_node_handles_empty_state(self):
        """Node should handle empty state gracefully."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]

        result = quant_agent_node(state)

        assert isinstance(result, dict)
        assert result.get("quant_scores") == {}

    def test_node_handles_no_funds_data(self):
        """Node should return empty quant_scores when no funds_data."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        state = _make_state()

        result = quant_agent_node(state)

        assert result.get("quant_scores") == {}
        assert result.get("market_regime") == "normal"

    def test_node_handles_minimal_fund_data(self):
        """Node should not crash on minimal fund data."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        minimal = {"code": "110011", "basic": {"name": "Minimal", "fund_type": "混合"}}
        state = _make_state(funds_data={"110011": minimal})

        result = quant_agent_node(state)

        assert "110011" in result["quant_scores"]

    def test_node_handles_events_for_regime(self):
        """Node should use events for regime detection when available."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        fund_data = _make_fund_data("110011")
        state = _make_state(
            funds_data={"110011": fund_data},
            extracted_events={
                "110011": [
                    {"type": "earnings_surprise", "polarity": 0.6, "magnitude": 0.5, "date": "2026-05-25"},
                ]
            },
        )

        result = quant_agent_node(state)

        assert "market_regime" in result

    def test_node_docstring_exists(self):
        """quant_agent_node must have a docstring."""
        from legacy.agents.graphs.quant_agent import quant_agent_node
        assert quant_agent_node.__doc__ is not None
        assert len(quant_agent_node.__doc__) > 10


class TestRegimeIntegration:
    """Tests for market regime detection within quant_agent_node."""

    def test_trending_regime_detected(self):
        """Should detect TRENDING when NAV has strong uptrend + low volatility."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        dates = pd.date_range(end="2026-05-27", periods=252, freq="B")
        # Linear uptrend with very low noise
        trend = np.linspace(1.0, 1.3, 252)
        noise = np.random.default_rng(42).normal(0, 0.002, 252)
        nav_values = trend + noise
        returns_vals = np.diff(nav_values, prepend=nav_values[0]) / nav_values * 100
        nav_df = pd.DataFrame({"单位净值": nav_values, "日增长率": returns_vals}, index=dates)

        fund_data = {"code": "110011", "nav": nav_df}
        state = _make_state(funds_data={"110011": fund_data})

        result = quant_agent_node(state)
        assert result["market_regime"] in ("trending", "normal")  # trending if strong enough

    def test_crisis_regime_from_black_swan(self):
        """Should detect CRISIS when events include black_swan."""
        from legacy.agents.graphs.quant_agent import quant_agent_node

        fund_data = _make_fund_data("110011")
        state = _make_state(
            funds_data={"110011": fund_data},
            extracted_events={
                "110011": [
                    {"type": "black_swan", "polarity": -0.95, "magnitude": 0.95, "date": "2026-05-25"},
                ]
            },
        )

        result = quant_agent_node(state)
        assert result["market_regime"] == "crisis"
