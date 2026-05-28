"""Test dynamic factor weights: regime-based weight mapping and enhanced factor matrix."""
from src.analysis.scoring.factors import get_regime_weights, compute_factor_matrix
from src.analysis.scoring.types import MarketRegime


class TestGetRegimeWeights:
    """Regime-to-weight-dict mapping."""

    def test_normal_regime_weights_match_spec(self):
        weights = get_regime_weights(MarketRegime.NORMAL)
        assert weights["quant"] == pytest.approx(0.40)
        assert weights["fundamental"] == pytest.approx(0.20)
        assert weights["event"] == pytest.approx(0.15)
        assert weights["position"] == pytest.approx(0.15)
        assert weights["timing"] == pytest.approx(0.10)
        total = sum(weights.values())
        assert total == pytest.approx(1.0)

    def test_high_volatility_regime_weights_match_spec(self):
        weights = get_regime_weights(MarketRegime.HIGH_VOLATILITY)
        assert weights["quant"] == pytest.approx(0.25)
        assert weights["event"] == pytest.approx(0.30)
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_trending_regime_weights_match_spec(self):
        weights = get_regime_weights(MarketRegime.TRENDING)
        assert weights["quant"] == pytest.approx(0.35)
        assert weights["fundamental"] == pytest.approx(0.25)
        assert weights["event"] == pytest.approx(0.10)
        assert weights["timing"] == pytest.approx(0.15)
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_crisis_regime_weights_match_spec(self):
        weights = get_regime_weights(MarketRegime.CRISIS)
        assert weights["quant"] == pytest.approx(0.15)
        assert weights["event"] == pytest.approx(0.40)
        assert weights["position"] == pytest.approx(0.25)
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_all_regimes_sum_to_one(self):
        for regime in MarketRegime:
            weights = get_regime_weights(regime)
            total = sum(weights.values())
            assert total == pytest.approx(1.0), f"{regime} weights sum to {total}"


class TestComputeFactorMatrix:
    """Enhanced factor matrix from fund data, KG, and events."""

    def test_returns_expected_structure(self):
        fund_data = {"code": "110011", "basic": {"name": "测试基金", "fund_type": "混合"}}
        kg = None
        events = []
        matrix = compute_factor_matrix(fund_data, kg, events)
        assert "quant" in matrix
        assert "fundamental" in matrix
        assert "event" in matrix
        assert "position" in matrix
        assert "timing" in matrix

    def test_empty_fund_data_gives_default_matrix(self):
        matrix = compute_factor_matrix({}, None, [])
        assert isinstance(matrix, dict)
        assert len(matrix) == 5  # five dimensions

    def test_matrix_values_are_normalized_0_1(self):
        fund_data = {"code": "110011", "basic": {"name": "测试", "fund_type": "混合"}}
        matrix = compute_factor_matrix(fund_data, None, [])
        for dim, value in matrix.items():
            assert 0.0 <= value <= 1.0, f"{dim} = {value} not in [0,1]"

    def test_fund_data_with_features_influences_quant(self):
        fund_data = {
            "code": "110011",
            "basic": {"name": "测试", "fund_type": "混合"},
            "perf": {
                "近1年": {"sharpe_ratio": 2.0, "annual_volatility": 10.0},
                "近3年": {"sharpe_ratio": 1.5, "max_drawdown": 15.0},
            },
        }
        matrix = compute_factor_matrix(fund_data, None, [])
        assert matrix["quant"] > 0.5  # good sharpe → high quant factor

    def test_events_with_negative_polarity_lower_event_factor(self):
        fund_data = {"code": "110011", "basic": {"name": "测试", "fund_type": "混合"}}
        negative_events = [
            {"type": "earnings_miss", "polarity": -0.8, "magnitude": 0.7},
            {"type": "rate_change", "polarity": -0.5, "magnitude": 0.5},
        ]
        positive_events = [
            {"type": "earnings_surprise", "polarity": 0.8, "magnitude": 0.7},
            {"type": "tech_breakthrough", "polarity": 0.6, "magnitude": 0.5},
        ]
        neg_matrix = compute_factor_matrix(fund_data, None, negative_events)
        pos_matrix = compute_factor_matrix(fund_data, None, positive_events)
        assert neg_matrix["event"] < pos_matrix["event"]


import pytest
