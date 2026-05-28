"""Test StopLogic: regime-aware stop-loss and take-profit computation."""
import pytest

from src.analysis.scoring.types import MarketRegime
from src.strategy.stop_logic import StopLogic


class TestStopLogicDefaults:
    """Regime-based default stop-loss and take-profit thresholds."""

    def test_normal_stop_loss(self):
        sl = StopLogic()
        assert sl.compute_stop_loss(MarketRegime.NORMAL, {}) == 15.0

    def test_normal_take_profit(self):
        sl = StopLogic()
        assert sl.compute_take_profit(MarketRegime.NORMAL, {}) == 25.0

    def test_high_volatility_stop_loss(self):
        sl = StopLogic()
        assert sl.compute_stop_loss(MarketRegime.HIGH_VOLATILITY, {}) == 10.0

    def test_high_volatility_take_profit(self):
        sl = StopLogic()
        assert sl.compute_take_profit(MarketRegime.HIGH_VOLATILITY, {}) == 20.0

    def test_trending_stop_loss(self):
        sl = StopLogic()
        assert sl.compute_stop_loss(MarketRegime.TRENDING, {}) == 12.0

    def test_trending_take_profit(self):
        sl = StopLogic()
        assert sl.compute_take_profit(MarketRegime.TRENDING, {}) == 30.0

    def test_crisis_stop_loss(self):
        sl = StopLogic()
        assert sl.compute_stop_loss(MarketRegime.CRISIS, {}) == 8.0

    def test_crisis_take_profit(self):
        sl = StopLogic()
        assert sl.compute_take_profit(MarketRegime.CRISIS, {}) == 15.0


class TestShouldStopLoss:
    """Stop-loss trigger logic."""

    def test_should_stop_loss_when_exceeded(self):
        sl = StopLogic()
        # Normal regime: 15% stop loss. Entry at 100, current at 84 = -16%.
        assert sl.should_stop_loss(current_price=84.0, entry_price=100.0, regime=MarketRegime.NORMAL) is True

    def test_should_not_stop_loss_when_within_threshold(self):
        sl = StopLogic()
        # Normal regime: 15% stop loss. Entry at 100, current at 90 = -10%.
        assert sl.should_stop_loss(current_price=90.0, entry_price=100.0, regime=MarketRegime.NORMAL) is False

    def test_should_stop_loss_at_exact_threshold(self):
        sl = StopLogic()
        # Normal regime: 15%. Entry at 100, current at 85 = -15% exactly.
        assert sl.should_stop_loss(current_price=85.0, entry_price=100.0, regime=MarketRegime.NORMAL) is True

    def test_crisis_regime_tighter_stop_loss(self):
        sl = StopLogic()
        # Crisis: 8%. Entry at 100, current at 93 = -7% (within threshold).
        assert sl.should_stop_loss(current_price=93.0, entry_price=100.0, regime=MarketRegime.CRISIS) is False
        # Entry at 100, current at 91 = -9% (exceeds threshold).
        assert sl.should_stop_loss(current_price=91.0, entry_price=100.0, regime=MarketRegime.CRISIS) is True


class TestShouldTakeProfit:
    """Take-profit trigger logic."""

    def test_should_take_profit_when_exceeded(self):
        sl = StopLogic()
        # Normal regime: 25% take profit. Entry at 100, current at 126 = +26%.
        assert sl.should_take_profit(current_price=126.0, entry_price=100.0, regime=MarketRegime.NORMAL) is True

    def test_should_not_take_profit_when_within_threshold(self):
        sl = StopLogic()
        # Normal regime: 25%. Entry at 100, current at 120 = +20%.
        assert sl.should_take_profit(current_price=120.0, entry_price=100.0, regime=MarketRegime.NORMAL) is False

    def test_should_take_profit_at_exact_threshold(self):
        sl = StopLogic()
        # Normal regime: 25%. Entry at 100, current at 125 = +25%.
        assert sl.should_take_profit(current_price=125.0, entry_price=100.0, regime=MarketRegime.NORMAL) is True

    def test_trending_regime_wider_take_profit(self):
        sl = StopLogic()
        # Trending: 30%. Entry at 100, current at 129 = +29% (within).
        assert sl.should_take_profit(current_price=129.0, entry_price=100.0, regime=MarketRegime.TRENDING) is False
        # Entry at 100, current at 131 = +31% (exceeds).
        assert sl.should_take_profit(current_price=131.0, entry_price=100.0, regime=MarketRegime.TRENDING) is True
