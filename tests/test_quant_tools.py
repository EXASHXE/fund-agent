"""Tests for src.tools.quant.metrics — pure quant wrapper functions."""

from __future__ import annotations

import math
import statistics

import pytest

from src.tools.quant.metrics import (
    calculate_hhi,
    calculate_max_drawdown,
    calculate_sharpe,
    calculate_sortino,
    calculate_volatility,
)


class TestQuantMetrics:
    """Test suite for quant/metrics.py wrapper functions."""

    # ------------------------------------------------------------------
    # calculate_sharpe
    # ------------------------------------------------------------------

    def test_sharpe_positive(self):
        """Sharpe ratio > 0 for consistently positive returns."""
        returns = [0.001, 0.002, 0.0015, 0.003, 0.0025] * 51  # ~255 entries
        result = calculate_sharpe(returns, risk_free_annual=0.02)
        assert result > 0.0
        assert isinstance(result, float)

    def test_sharpe_flat_returns(self):
        """All-zero returns → Sharpe ≤ 0 (excess = -risk_free_daily, but flat → std=0 → 0)."""
        returns = [0.0] * 252
        result = calculate_sharpe(returns, risk_free_annual=0.02)
        assert result == 0.0  # std dev = 0 → returns 0.0

    def test_sharpe_single_return(self):
        """Single return → 0.0 (insufficient data)."""
        assert calculate_sharpe([0.001]) == 0.0

    def test_sharpe_empty_returns(self):
        """Empty list → 0.0."""
        assert calculate_sharpe([]) == 0.0

    def test_sharpe_higher_risk_free(self):
        """Higher risk-free rate reduces Sharpe."""
        returns = [0.002, -0.001, 0.003, 0.001, -0.002] * 50  # 250 returns
        low = calculate_sharpe(returns, risk_free_annual=0.01)
        high = calculate_sharpe(returns, risk_free_annual=0.10)
        assert low > high

    # ------------------------------------------------------------------
    # calculate_sortino
    # ------------------------------------------------------------------

    def test_sortino_basic(self):
        """Sortino delegates to sortino_ratio, returns a float."""
        returns = [0.001] * 30  # need >= 20 per sortino_ratio threshold
        result = calculate_sortino(returns)
        assert isinstance(result, float)

    def test_sortino_custom_mar(self):
        """Sortino accepts custom MAR."""
        returns = [0.001 if i % 3 != 0 else -0.005 for i in range(30)]
        result_default = calculate_sortino(returns)
        result_custom = calculate_sortino(returns, mar_annual=0.05)
        assert isinstance(result_default, float)
        assert isinstance(result_custom, float)

    # ------------------------------------------------------------------
    # calculate_max_drawdown
    # ------------------------------------------------------------------

    def test_max_drawdown_uptrend(self):
        """Strictly uptrending NAV → 0.0 drawdown."""
        nav = [100.0, 101.0, 102.0, 103.0]
        assert calculate_max_drawdown(nav) == 0.0

    def test_max_drawdown_decline(self):
        """Declining NAV: (100 - 80) / 100 = 0.20."""
        nav = [100.0, 90.0, 80.0, 95.0]
        result = calculate_max_drawdown(nav)
        assert result == pytest.approx(0.2, abs=0.001)

    def test_max_drawdown_single_value(self):
        """Single value → 0.0."""
        assert calculate_max_drawdown([100.0]) == 0.0

    def test_max_drawdown_empty(self):
        """Empty list → 0.0."""
        assert calculate_max_drawdown([]) == 0.0

    def test_max_drawdown_recovery(self):
        """After a 50% dip, partial recovery still shows 50% max DD."""
        nav = [100.0, 50.0, 75.0]
        result = calculate_max_drawdown(nav)
        assert result == pytest.approx(0.5, abs=0.001)

    # ------------------------------------------------------------------
    # calculate_volatility
    # ------------------------------------------------------------------

    def test_volatility_known_values(self):
        """Alternating ±1 % daily returns produce ~15.9 % annualised vol."""
        returns = [0.01, -0.01] * 126  # 252 returns
        result = calculate_volatility(returns)
        expected_annual = statistics.stdev(returns) * math.sqrt(252)
        assert result == pytest.approx(expected_annual, rel=0.01)

    def test_volatility_single(self):
        """Single return → 0.0."""
        assert calculate_volatility([0.01]) == 0.0

    def test_volatility_zero(self):
        """All zero returns → 0.0."""
        assert calculate_volatility([0.0] * 252) == 0.0

    def test_volatility_empty(self):
        """Empty list → 0.0."""
        assert calculate_volatility([]) == 0.0

    # ------------------------------------------------------------------
    # calculate_hhi
    # ------------------------------------------------------------------

    def test_hhi_returns_float(self):
        """HHI delegates to compute_hhi and returns a non-negative float."""
        weights = [0.25, 0.25, 0.25, 0.25]
        result = calculate_hhi(weights)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_hhi_empty_list(self):
        """Empty weights → 0.0 (delegates to compute_hhi which returns None for empty DF)."""
        assert calculate_hhi([]) == 0.0

    def test_hhi_single_holding(self):
        """Single holding → valid float."""
        result = calculate_hhi([1.0])
        assert isinstance(result, float)
        assert result >= 0.0

    def test_hhi_diversified(self):
        """Many holdings → valid float."""
        result = calculate_hhi([0.1] * 10)
        assert isinstance(result, float)
        assert result >= 0.0
