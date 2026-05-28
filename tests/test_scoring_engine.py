"""Test ScoreEngine: composite scoring orchestrator integrating all 5 sub-scores."""
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from src.analysis.scoring.types import CompositeScore, ScoreComponent, MarketRegime, score_level
from src.kg.graph import KnowledgeGraphBuilder


@pytest.fixture
def kg_builder():
    return KnowledgeGraphBuilder()


@pytest.fixture
def fund_data():
    """Full fund data with NAV, holdings, and performance metrics."""
    dates = pd.date_range(end="2026-05-27", periods=252, freq="B")
    returns = np.random.normal(0.0003, 0.012, 252)
    nav = 1.0 * (1 + pd.Series(returns)).cumprod()
    nav_df = pd.DataFrame({"单位净值": nav, "日增长率": returns * 100}, index=dates)

    return {
        "code": "110011",
        "name": "测试混合基金",
        "fund_type": "混合型",
        "basic": {"name": "测试基金", "fund_type": "混合型", "manager": "测试经理"},
        "nav": nav_df,
        "perf": {
            "近1年": {"sharpe_ratio": 1.2, "annual_volatility": 18.0},
            "近3年": {"max_drawdown": 15.0},
        },
        "completeness": "B",
        "holdings": [
            {"stock_code": "600519", "stock_name": "茅台", "industry": "食品饮料", "weight": 12.0},
            {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 10.0},
            {"stock_code": "300750", "stock_name": "宁德", "industry": "电力设备", "weight": 8.0},
            {"stock_code": "000333", "stock_name": "美的", "industry": "家用电器", "weight": 7.0},
            {"stock_code": "600036", "stock_name": "招行", "industry": "银行", "weight": 6.0},
        ],
        "sectors": [
            {"industry": "食品饮料", "sw_code": "801120", "weight": 22.0},
            {"industry": "电力设备", "sw_code": "801730", "weight": 8.0},
            {"industry": "家用电器", "sw_code": "801200", "weight": 7.0},
            {"industry": "银行", "sw_code": "801780", "weight": 6.0},
        ],
    }


@pytest.fixture
def kg_graph(fund_data, kg_builder):
    """Build KG from fund data."""
    return kg_builder.build_from_holdings(fund_data)


@pytest.fixture
def events():
    """Sample events with mixed sentiment."""
    return [
        {"type": "earnings_surprise", "polarity": 0.7, "magnitude": 0.6, "date": "2026-05-25"},
        {"type": "fund_flow", "polarity": 0.5, "magnitude": 0.4, "date": "2026-05-24"},
        {"type": "rate_change", "polarity": -0.3, "magnitude": 0.5, "date": "2026-05-23"},
    ]


class TestScoreEngineCompute:
    """Core ScoreEngine composite computation."""

    def test_returns_composite_score(self, fund_data, kg_graph, events):
        """Should return a valid CompositeScore."""
        from src.analysis.scoring.engine import ScoreEngine

        engine = ScoreEngine()
        result = engine.compute_composite("110011", fund_data, kg_graph, events)

        assert isinstance(result, CompositeScore)
        assert 0 <= result.composite <= 100
        assert isinstance(result.quant_score, ScoreComponent)
        assert isinstance(result.fundamental_score, ScoreComponent)
        assert isinstance(result.event_score, ScoreComponent)
        assert isinstance(result.position_score, ScoreComponent)
        assert isinstance(result.timing_score, ScoreComponent)

    def test_composite_is_weighted_combination(self, fund_data, kg_graph, events):
        """Composite should be a weighted sum of all 5 sub-scores per regime weights."""
        from src.analysis.scoring.engine import ScoreEngine

        engine = ScoreEngine()
        result = engine.compute_composite("110011", fund_data, kg_graph, events)

        w = result.weights_used
        expected = (
            result.quant_score.score * w["quant"]
            + result.fundamental_score.score * w["fundamental"]
            + result.event_score.score * w["event"]
            + result.position_score.score * w["position"]
            + result.timing_score.score * w["timing"]
        )
        assert abs(result.composite - expected) < 0.5, f"composite={result.composite}, expected={expected}"

    def test_weights_used_match_regime(self, fund_data, kg_graph, events):
        """Weights should correspond to the detected regime."""
        from src.analysis.scoring.engine import ScoreEngine

        engine = ScoreEngine()
        result = engine.compute_composite("110011", fund_data, kg_graph, events)

        expected = dict(result.regime.weights())
        for k in expected:
            assert abs(result.weights_used.get(k, 0) - expected[k]) < 0.01, f"{k}: {result.weights_used.get(k)} != {expected[k]}"

    def test_deduces_level_from_composite(self, fund_data, kg_graph, events):
        """Level should match the score_level() function output."""
        from src.analysis.scoring.engine import ScoreEngine

        engine = ScoreEngine()
        result = engine.compute_composite("110011", fund_data, kg_graph, events)

        expected_level = score_level(result.composite)
        assert result.level == expected_level

    def test_minimal_fund_data_still_works(self):
        """Engine should handle minimal fund data gracefully."""
        from src.analysis.scoring.engine import ScoreEngine

        engine = ScoreEngine()
        minimal_data = {"code": "110011", "basic": {"name": "测试", "fund_type": "混合"}}
        result = engine.compute_composite("110011", minimal_data, nx.DiGraph(), [])

        assert isinstance(result, CompositeScore)
        assert 0 <= result.composite <= 100
        assert result.level in ("green", "yellow", "orange", "red")

    def test_level_order_green_yellow_orange_red(self):
        """Verify level thresholds: green≥75, yellow≥50, orange≥30, red<30."""
        assert score_level(80) == "green"
        assert score_level(75) == "green"
        assert score_level(60) == "yellow"
        assert score_level(50) == "yellow"
        assert score_level(40) == "orange"
        assert score_level(30) == "orange"
        assert score_level(20) == "red"
        assert score_level(0) == "red"

    def test_no_events_no_kg_still_produces_result(self):
        """Engine should produce a result even with completely empty inputs."""
        from src.analysis.scoring.engine import ScoreEngine

        engine = ScoreEngine()
        result = engine.compute_composite("110011", {}, nx.DiGraph(), [])

        assert isinstance(result, CompositeScore)
        assert result.composite <= 100
        assert result.regime == MarketRegime.NORMAL  # default regime

    def test_llm_client_acceptance(self, fund_data, kg_graph, events):
        """Engine should accept llm_client parameter without error."""
        from src.analysis.scoring.engine import ScoreEngine

        engine = ScoreEngine(llm_client=None)
        result = engine.compute_composite("110011", fund_data, kg_graph, events, llm_client=None)
        assert isinstance(result, CompositeScore)
