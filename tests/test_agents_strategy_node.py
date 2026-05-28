"""Tests for strategy_agent_node: wraps StrategyEngine + ScoreEngine for final decisions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from src.agents.state import FundResearchState, EMPTY_STATE


def _make_state(**overrides) -> FundResearchState:
    """Create a test state with sensible defaults, with optional overrides."""
    state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _make_fund_data(code: str = "110011", seed: int = 42) -> dict:
    """Create fund data with NAV."""
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
        "holdings": [
            {"stock_code": "600519", "stock_name": "茅台", "industry": "食品饮料", "weight": 12.0},
            {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 10.0},
        ],
        "sectors": [
            {"industry": "食品饮料", "sw_code": "801120", "weight": 22.0},
        ],
    }


def _make_kg() -> nx.DiGraph:
    """Minimal KG."""
    from src.kg.graph import KnowledgeGraphBuilder
    builder = KnowledgeGraphBuilder()
    return builder.build_from_holdings(_make_fund_data())


class TestStrategyAgentNode:
    """Tests for strategy_agent_node function."""

    def test_node_returns_dict(self):
        """Node should return a dict of state updates."""
        from src.agents.graphs.strategy_agent import strategy_agent_node

        fund_data = _make_fund_data("110011")
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=_make_kg(),
        )

        result = strategy_agent_node(state)

        assert isinstance(result, dict)
        assert "strategies" in result
        assert "risk_assessments" in result
        assert "final_scores" in result

    def test_node_uses_existing_scores(self):
        """Node should use existing scores from state when available."""
        from src.agents.graphs.strategy_agent import strategy_agent_node
        from src.analysis.scoring.types import ScoreComponent, MarketRegime

        fund_data = _make_fund_data("110011")

        # Pre-populated scores (ScoreComponent instances)
        quant = ScoreComponent(score=75.0, detail={}, weights={}, confidence=0.8)
        fundamental = ScoreComponent(score=65.0, detail={}, weights={}, confidence=0.7)
        event = ScoreComponent(score=55.0, detail={}, weights={}, confidence=0.6)
        position = ScoreComponent(score=70.0, detail={}, weights={}, confidence=0.75)
        timing = ScoreComponent(score=60.0, detail={}, weights={}, confidence=0.65)

        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=_make_kg(),
            quant_scores={"110011": quant},
            fundamental_scores={"110011": fundamental},
            event_scores={"110011": event},
            position_scores={"110011": position},
            timing_scores={"110011": timing},
            market_regime="normal",
        )

        result = strategy_agent_node(state)

        assert "110011" in result["strategies"]
        assert "110011" in result["risk_assessments"]
        assert "110011" in result["final_scores"]

    def test_node_handles_empty_state(self):
        """Node should handle empty state gracefully."""
        from src.agents.graphs.strategy_agent import strategy_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]

        result = strategy_agent_node(state)

        assert isinstance(result, dict)
        assert result.get("strategies") == {}
        assert result.get("risk_assessments") == {}
        assert result.get("final_scores") == {}

    def test_node_handles_no_funds_data(self):
        """Node should return empty when no funds_data."""
        from src.agents.graphs.strategy_agent import strategy_agent_node

        state = _make_state(knowledge_graph=_make_kg())

        result = strategy_agent_node(state)

        assert result.get("strategies") == {}
        assert result.get("final_scores") == {}

    def test_node_handles_partial_scores(self):
        """Node should gracefully handle missing score components."""
        from src.agents.graphs.strategy_agent import strategy_agent_node

        fund_data = _make_fund_data("110011")
        # Only quant scores provided, others missing
        from src.analysis.scoring.types import ScoreComponent
        quant = ScoreComponent(score=75.0, detail={}, weights={}, confidence=0.8)

        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=_make_kg(),
            quant_scores={"110011": quant},
        )

        result = strategy_agent_node(state)

        assert "110011" in result["strategies"]

    def test_node_computes_portfolio_strategy(self):
        """Node should compute portfolio-level strategy summary."""
        from src.agents.graphs.strategy_agent import strategy_agent_node

        fund_a = _make_fund_data("110011", seed=42)
        fund_b = _make_fund_data("000001", seed=99)
        state = _make_state(
            funds_data={"110011": fund_a, "000001": fund_b},
            knowledge_graph=_make_kg(),
        )

        result = strategy_agent_node(state)

        assert "portfolio_strategy" in result
        assert isinstance(result["portfolio_strategy"], dict)

    def test_node_gets_risk_assessments(self):
        """Node should populate risk_assessments per fund."""
        from src.agents.graphs.strategy_agent import strategy_agent_node

        fund_data = _make_fund_data("110011")
        state = _make_state(
            funds_data={"110011": fund_data},
            knowledge_graph=_make_kg(),
        )

        result = strategy_agent_node(state)

        assert "110011" in result["risk_assessments"]
        risk = result["risk_assessments"]["110011"]
        assert isinstance(risk, dict)

    def test_node_docstring_exists(self):
        """strategy_agent_node must have a docstring."""
        from src.agents.graphs.strategy_agent import strategy_agent_node
        assert strategy_agent_node.__doc__ is not None
        assert len(strategy_agent_node.__doc__) > 10
