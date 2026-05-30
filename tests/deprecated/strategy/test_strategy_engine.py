"""Test StrategyEngine: top-level strategy analysis orchestrator."""
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from legacy.analysis.scoring.types import CompositeScore, ScoreComponent, MarketRegime
from legacy.strategy.schemas import StrategyAdvice, StrategyState, StrategyAction
from legacy.strategy.engine import StrategyEngine


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def _make_fund_data(code: str, name: str, seed: int = 42) -> dict:
    """Create realistic fund data with NAV series for regime detection."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end="2026-05-27", periods=252, freq="B")
    returns = rng.normal(0.0003, 0.012, 252)
    nav = 1.0 * (1 + pd.Series(returns)).cumprod()
    nav_df = pd.DataFrame({"单位净值": nav, "日增长率": returns * 100}, index=dates)

    return {
        "code": code,
        "name": name,
        "fund_type": "混合型",
        "basic": {"name": name, "fund_type": "混合型", "manager": "测试经理"},
        "nav": nav_df,
        "perf": {
            "近1年": {"sharpe_ratio": 1.2, "annual_volatility": 18.0},
            "近3年": {"max_drawdown": 15.0},
        },
        "holdings": [
            {"stock_code": "600519", "stock_name": "茅台", "industry": "食品饮料", "weight": 12.0},
            {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 10.0},
            {"stock_code": "300750", "stock_name": "宁德", "industry": "电力设备", "weight": 8.0},
            {"stock_code": "000333", "stock_name": "美的", "industry": "家用电器", "weight": 7.0},
        ],
        "sectors": [
            {"industry": "食品饮料", "sw_code": "801120", "weight": 22.0},
            {"industry": "电力设备", "sw_code": "801730", "weight": 8.0},
            {"industry": "家用电器", "sw_code": "801200", "weight": 7.0},
        ],
    }


@pytest.fixture
def fund_data():
    return _make_fund_data("110011", "测试混合基金", seed=42)


@pytest.fixture
def kg(fund_data):
    from src.graph.builder import KnowledgeGraphBuilder
    builder = KnowledgeGraphBuilder()
    return builder.build_from_holdings(fund_data)


@pytest.fixture
def favorable_events():
    return [
        {"type": "earnings_surprise", "polarity": 0.7, "magnitude": 0.6, "date": "2026-05-25"},
        {"type": "fund_flow", "polarity": 0.5, "magnitude": 0.4, "date": "2026-05-24"},
    ]


@pytest.fixture
def engine():
    return StrategyEngine()


class TestAnalyzeFund:
    """StrategyEngine.analyze_fund() returns StrategyAdvice."""

    def test_returns_strategy_advice(self, engine, fund_data, kg, favorable_events):
        result = engine.analyze_fund(
            fund_code="110011",
            fund_data=fund_data,
            kg=kg,
            events=favorable_events,
        )
        assert isinstance(result, StrategyAdvice)
        assert isinstance(result.action, StrategyAction)
        assert isinstance(result.state, StrategyState)
        assert 0.0 <= result.confidence <= 1.0
        assert result.stop_loss_pct is not None
        assert result.take_profit_pct is not None

    def test_accepts_current_state(self, engine, fund_data, kg, favorable_events):
        result = engine.analyze_fund(
            fund_code="110011",
            fund_data=fund_data,
            kg=kg,
            events=favorable_events,
            current_state=StrategyState.HOLD,
        )
        assert isinstance(result, StrategyAdvice)

    def test_llm_client_accepted(self, fund_data, kg, favorable_events):
        engine = StrategyEngine(llm_client=None)
        result = engine.analyze_fund(
            fund_code="110011",
            fund_data=fund_data,
            kg=kg,
            events=favorable_events,
        )
        assert isinstance(result, StrategyAdvice)

    def test_minimal_data_does_not_raise(self, engine):
        minimal_data = {"code": "110011", "basic": {"name": "测试", "fund_type": "混合"}}
        result = engine.analyze_fund(
            fund_code="110011",
            fund_data=minimal_data,
            kg=nx.DiGraph(),
            events=[],
        )
        assert isinstance(result, StrategyAdvice)


class TestAnalyzePortfolio:
    """StrategyEngine.analyze_portfolio() returns per-fund advice + summary."""

    def test_returns_portfolio_dict(self, engine, kg):
        fund1 = _make_fund_data("110011", "基金A", seed=42)
        fund2 = _make_fund_data("000001", "基金B", seed=99)
        fund_list = [fund1, fund2]

        result = engine.analyze_portfolio(fund_list, kg)

        assert isinstance(result, dict)
        assert "110011" in result
        assert "000001" in result
        assert "portfolio_summary" in result
        assert isinstance(result["110011"], StrategyAdvice)
        assert isinstance(result["000001"], StrategyAdvice)

    def test_portfolio_summary_has_required_keys(self, engine, kg):
        fund1 = _make_fund_data("110011", "基金A", seed=42)
        result = engine.analyze_portfolio([fund1], kg)

        summary = result["portfolio_summary"]
        assert "fund_count" in summary
        assert summary["fund_count"] == 1
        assert "avg_composite" in summary
        assert "regime" in summary
        assert "actions" in summary

    def test_portfolio_summary_aggregates_correctly(self, engine):
        fund1 = _make_fund_data("110011", "基金A", seed=42)
        fund2 = _make_fund_data("000001", "基金B", seed=99)
        g1 = nx.DiGraph(); g1.add_node("fund:110011")
        g2 = nx.DiGraph(); g2.add_node("fund:000001")

        # Build a unified KG
        kg = nx.DiGraph()
        kg.add_node("fund:110011")
        kg.add_node("fund:000001")

        result = engine.analyze_portfolio([fund1, fund2], kg)

        summary = result["portfolio_summary"]
        assert summary["fund_count"] == 2
        assert isinstance(summary["avg_composite"], (int, float))
        assert 0 <= summary["avg_composite"] <= 100
        assert "actions" in summary
