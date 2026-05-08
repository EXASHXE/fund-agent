"""Pydantic schema：PortfolioConfig, FundHolding, DCAStrategy 等"""
from pydantic import BaseModel, Field, model_validator
from enum import Enum
from typing import Optional
from datetime import date


class RiskTolerance(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class FundType(str, Enum):
    DOMESTIC = "domestic"
    QDII = "qdii"
    ETF = "etf"
    INDEX = "index"


class DCAFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class Purchase(BaseModel):
    date: date
    amount: float = Field(gt=0, description="买入金额(元)")
    nav: Optional[float] = Field(default=None, description="买入净值，null=自动获取")
    after_1500: bool = Field(default=False, description="是否在15:00后下单，true则顺延至下一交易日确认")


class DCAStrategy(BaseModel):
    enabled: bool = False
    frequency: DCAFrequency = DCAFrequency.WEEKLY
    amount: float = Field(gt=0, description="每期定投金额(元)")
    day_of_week: Optional[str] = Field(
        default=None,
        pattern=r"^(mon|tue|wed|thu|fri)$"
    )
    start_date: Optional[date] = None


class Calibration(BaseModel):
    """真实份额校准点：用于纠正系统模拟的累计偏差"""
    cal_date: date = Field(description="校准日期")
    actual_shares: float = Field(gt=0, description="当日的真实总份额")


class FundHolding(BaseModel):
    code: str = Field(pattern=r"^\d{6}$", description="6位基金代码")
    name: str = Field(default="", description="基金名称，空字符串=自动查询")
    type: FundType = Field(default=FundType.DOMESTIC)
    currency: str = Field(default="CNY")
    fee_rate: float = Field(default=0.0015, ge=0, description="申购费率")
    avg_cost: Optional[float] = Field(default=None, description="持仓成本价(元/份)")
    shares: Optional[float] = Field(default=None, description="当前持有份额")
    pending_amount: float = Field(default=0.0, ge=0, description="待确认金额(元)")
    settle_delay: int = Field(default=1, description="净值确认延迟(t+1=国内, t+2=QDII)")
    purchases: list[Purchase] = Field(default_factory=list)
    dca: Optional[DCAStrategy] = None
    calibrations: list[Calibration] = Field(default_factory=list, description="份额校准点")


class ScoringParams(BaseModel):
    macro_weight: float = Field(default=0.20, ge=0, le=1)
    meso_weight: float = Field(default=0.30, ge=0, le=1)
    micro_weight: float = Field(default=0.50, ge=0, le=1)


class StopProfitLossParams(BaseModel):
    profit_multiplier: float = Field(default=2.0, gt=0)
    loss_multiplier: float = Field(default=1.5, gt=0)


class RebalanceParams(BaseModel):
    max_single_position: float = Field(default=0.30, ge=0, le=1)
    correlation_alert: float = Field(default=0.75, ge=0, le=1)


class StrategyParams(BaseModel):
    scoring: ScoringParams = Field(default_factory=ScoringParams)
    stop_profit_loss: StopProfitLossParams = Field(default_factory=StopProfitLossParams)
    rebalance: RebalanceParams = Field(default_factory=RebalanceParams)


class UserProfile(BaseModel):
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    investment_horizon: str = Field(default="3-5年")
    target_return: float = Field(default=0.10, gt=0)
    max_drawdown_tolerance: float = Field(default=0.20, gt=0)


class PortfolioConfig(BaseModel):
    profile: UserProfile = Field(default_factory=UserProfile)
    holdings: list[FundHolding] = Field(default_factory=list)
    strategy: StrategyParams = Field(default_factory=StrategyParams)
    watchlist: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_holdings_not_empty(self):
        if not self.holdings:
            raise ValueError("holdings 列表不能为空，至少需要一只基金")
        return self
