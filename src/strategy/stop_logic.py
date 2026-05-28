"""StopLogic: regime-aware stop-loss and take-profit thresholds."""
from __future__ import annotations

from src.analysis.scoring.types import MarketRegime

# Regime-based default thresholds (percentage)
_STOP_LOSS_DEFAULTS: dict[MarketRegime, float] = {
    MarketRegime.NORMAL: 15.0,
    MarketRegime.HIGH_VOLATILITY: 10.0,
    MarketRegime.TRENDING: 12.0,
    MarketRegime.CRISIS: 8.0,
}

_TAKE_PROFIT_DEFAULTS: dict[MarketRegime, float] = {
    MarketRegime.NORMAL: 25.0,
    MarketRegime.HIGH_VOLATILITY: 20.0,
    MarketRegime.TRENDING: 30.0,
    MarketRegime.CRISIS: 15.0,
}


class StopLogic:
    """Compute regime-aware stop-loss and take-profit thresholds."""

    def compute_stop_loss(self, regime: MarketRegime, fund_data: dict) -> float:
        """Return stop-loss percentage for the given regime."""
        return _STOP_LOSS_DEFAULTS.get(regime, 15.0)

    def compute_take_profit(self, regime: MarketRegime, fund_data: dict) -> float:
        """Return take-profit percentage for the given regime."""
        return _TAKE_PROFIT_DEFAULTS.get(regime, 25.0)

    def should_stop_loss(self, current_price: float, entry_price: float, regime: MarketRegime) -> bool:
        """Check if current drawdown exceeds the regime stop-loss threshold."""
        if current_price <= 0 or entry_price <= 0:
            return False
        drawdown_pct = (1.0 - current_price / entry_price) * 100.0
        return drawdown_pct >= self.compute_stop_loss(regime, {})

    def should_take_profit(self, current_price: float, entry_price: float, regime: MarketRegime) -> bool:
        """Check if current return exceeds the regime take-profit threshold."""
        if current_price <= 0 or entry_price <= 0:
            return False
        profit_pct = (current_price / entry_price - 1.0) * 100.0
        return profit_pct >= self.compute_take_profit(regime, {})
