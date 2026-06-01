"""Typed fund and personal portfolio analysis schemas.

These dataclasses are plain contract helpers for host-provided data. They do
not fetch data, call providers, or depend on analysis infrastructure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


RiskLevel = Literal["conservative", "moderate", "aggressive"]


@dataclass
class FundIdentity:
    fund_code: str
    name: str = ""
    fund_type: str = ""
    manager: str = ""
    benchmark: str = ""
    currency: str = "CNY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NavPoint:
    date: str
    nav: float
    accumulated_nav: float | None = None
    daily_return: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FundHolding:
    name: str
    weight: float
    code: str | None = None
    asset_type: str | None = None
    industry: str | None = None
    region: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioPosition:
    fund_code: str
    fund_name: str
    current_value: float
    total_cost: float
    shares: float | None = None
    pending_amount: float = 0.0
    target_weight: float | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioSnapshot:
    as_of_date: str
    total_value: float
    cash_available: float
    positions: list[PortfolioPosition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "total_value": self.total_value,
            "cash_available": self.cash_available,
            "positions": [position.to_dict() for position in self.positions],
        }


@dataclass
class UserRiskProfile:
    risk_level: RiskLevel = "moderate"
    max_single_fund_weight: float = 0.2
    max_theme_weight: float = 0.35
    max_trade_pct: float = 0.1
    liquidity_reserve_pct: float = 0.1
    short_term_trade_budget_pct: float = 0.1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RebalanceConstraint:
    max_buy_amount: float | None = None
    max_sell_amount: float | None = None
    min_trade_amount: float = 0.0
    forbidden_actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FundAnalysisReport:
    fund_metrics: dict[str, Any] = field(default_factory=dict)
    portfolio_metrics: dict[str, Any] = field(default_factory=dict)
    exposures: dict[str, Any] = field(default_factory=dict)
    concentration: dict[str, Any] = field(default_factory=dict)
    risk_flags: list[dict[str, Any]] = field(default_factory=list)
    suggested_watchlist: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_metrics": self.fund_metrics,
            "portfolio_metrics": self.portfolio_metrics,
            "exposures": self.exposures,
            "concentration": self.concentration,
            "risk_flags": self.risk_flags,
            "suggested_watchlist": self.suggested_watchlist,
            "warnings": self.warnings,
        }
