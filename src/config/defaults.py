"""全局默认策略参数，与 skills/fund-analyst/SKILL.md 保持一致"""
from src.config.schema import (
    ScoringParams, StopProfitLossParams, RebalanceParams,
    StrategyParams, UserProfile
)

DEFAULT_STRATEGY = StrategyParams(
    scoring=ScoringParams(macro_weight=0.20, meso_weight=0.30, micro_weight=0.50),
    stop_profit_loss=StopProfitLossParams(profit_multiplier=2.0, loss_multiplier=1.5),
    rebalance=RebalanceParams(max_single_position=0.30, correlation_alert=0.75),
)

DEFAULT_PROFILE = UserProfile()

FALLBACK_VALUES = {
    "annual_volatility": 20.0,
    "max_drawdown": 25.0,
    "sharpe_ratio": 0.5,
    "alpha": 0.0,
    "beta": 1.0,
}
