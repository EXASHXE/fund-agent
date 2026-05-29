"""Test QuantScoreCalculator: data-driven quantitative scoring with dynamic regime weights."""
import pytest
import pandas as pd
import numpy as np
from legacy.analysis.scoring.quant import QuantScoreCalculator
from legacy.analysis.scoring.types import ScoreComponent, MarketRegime


@pytest.fixture
def fund_data_with_perf():
    """Minimal fund data with performance metrics."""
    dates = pd.date_range(end="2026-05-27", periods=252, freq="B")
    returns = np.random.normal(0.0005, 0.015, 252)  # ~12.6% annual return, ~24% vol
    nav = 1.0 * (1 + pd.Series(returns)).cumprod()
    nav_df = pd.DataFrame({"单位净值": nav, "日增长率": returns * 100}, index=dates)
    return {
        "code": "110011",
        "basic": {"name": "测试基金", "fund_type": "混合", "manager": "测试经理"},
        "nav": nav_df,
        "perf": {
            "近1年": {"sharpe_ratio": 1.2, "annual_volatility": 18.0},
            "近3年": {"sharpe_ratio": 0.9, "max_drawdown": 20.0},
        },
        "completeness": "A",
    }


@pytest.fixture
def calculator():
    return QuantScoreCalculator()


class TestQuantScoreCompute:
    """Core QuantScore computation."""

    def test_returns_score_component(self, calculator, fund_data_with_perf):
        result = calculator.compute(fund_data_with_perf, MarketRegime.NORMAL)
        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100
        assert isinstance(result.detail, dict)
        assert isinstance(result.weights, dict)
        assert 0 <= result.confidence <= 1.0

    def test_normal_regime_weights(self, calculator, fund_data_with_perf):
        result = calculator.compute(fund_data_with_perf, MarketRegime.NORMAL)
        assert "sharpe" in result.weights or "sortino" in result.weights or len(result.weights) > 0

    def test_different_regimes_produce_different_weights(self, calculator, fund_data_with_perf):
        normal = calculator.compute(fund_data_with_perf, MarketRegime.NORMAL)
        crisis = calculator.compute(fund_data_with_perf, MarketRegime.CRISIS)
        assert normal.weights != crisis.weights

    def test_detail_contains_key_metrics(self, calculator, fund_data_with_perf):
        result = calculator.compute(fund_data_with_perf, MarketRegime.NORMAL)
        detail_keys = list(result.detail.keys())
        # Should contain at least some metrics
        assert len(detail_keys) >= 3

    def test_high_confidence_for_complete_data(self, calculator, fund_data_with_perf):
        result = calculator.compute(fund_data_with_perf, MarketRegime.NORMAL)
        assert result.confidence >= 0.5


class TestQuantScoreFallback:
    """Fallback behavior when data is missing."""

    def test_empty_fund_data_returns_default_score(self, calculator):
        result = calculator.compute({}, MarketRegime.NORMAL)
        assert isinstance(result, ScoreComponent)
        assert result.score == 50.0
        assert result.confidence < 0.5

    def test_missing_nav_lowers_confidence(self, calculator):
        partial_data = {
            "code": "110011",
            "basic": {"name": "测试", "fund_type": "混合"},
            "perf": {"近1年": {}, "近3年": {}},
        }
        result = calculator.compute(partial_data, MarketRegime.NORMAL)
        assert result.confidence < 0.6

    def test_partial_metrics_still_computable(self, calculator):
        partial_data = {
            "code": "110011",
            "basic": {"name": "测试", "fund_type": "混合"},
            "perf": {
                "近1年": {"sharpe_ratio": 2.5},
                "近3年": {"max_drawdown": 10.0},
            },
            "completeness": "B",
        }
        result = calculator.compute(partial_data, MarketRegime.NORMAL)
        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100
