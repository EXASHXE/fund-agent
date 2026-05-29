"""全局默认策略参数，与 skills/fund-analyst/SKILL.md 保持一致"""
from src.infra.config.schema import (
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

# === 量化引擎全局可调参数 ===
# 这些参数支持从外部端口 / YAML 动态加载改写
QUANT_CONFIG = {
    # 索提诺比率最低可接受收益率（年化）
    # 用于动态调节下行风险特征的考核阈值
    # 默认 2.5% = 中国 1 年期国债收益率近似
    "SORTINO_MAR": 0.025,

    # 舆情时间指数衰减系数 λ
    # 控制新闻时效性的半衰期——值越大，旧新闻衰减越快
    # λ=0.200 → 半衰期约 3.5 天 (ln(2)/λ)
    # 高波动季可调高至 0.3-0.5；长主线牛市可调低至 0.1
    "NEWS_LAMBDA": 0.200,
}

# 风险收益率字典（底层引擎自适应不同币种）
RISK_FREE_RATE = {
    "CNY": 0.025,   # 中国 1 年期国债收益率近似
    "USD": 0.045,   # 美国联邦基金利率区间中值
}
