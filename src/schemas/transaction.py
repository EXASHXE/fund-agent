"""Transaction and cost-basis schemas for personal portfolio analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FundTransaction:
    """A single fund transaction.

    action is canonical, type is backward-compatible alias.
    """
    transaction_id: str = ""
    fund_code: str = ""
    fund_name: str = ""
    action: str = ""  # BUY, SELL, DIVIDEND, FEE, TRANSFER_IN, TRANSFER_OUT
    date: str = ""
    amount: float = 0.0
    shares: float | None = None
    nav: float | None = None
    fee: float = 0.0
    notes: str = ""

    @property
    def type(self) -> str:
        """action is canonical, type is backward-compatible alias."""
        return self.action

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.action
        return d


@dataclass
class PositionCostBasis:
    """Weighted-average cost basis for a single fund position."""
    fund_code: str = ""
    total_shares: float = 0.0
    total_cost: float = 0.0
    average_cost_per_share: float = 0.0
    current_nav: float | None = None
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    transaction_count: int = 0
    method: str = "weighted_average"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TransactionLedgerSummary:
    """Summary of all transactions for a portfolio."""
    as_of_date: str = ""
    total_buys: float = 0.0
    total_sells: float = 0.0
    total_dividends: float = 0.0
    total_fees: float = 0.0
    net_flow: float = 0.0
    buy_count: int = 0
    sell_count: int = 0
    position_costs: dict[str, PositionCostBasis] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    cashflow_by_fund: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "total_buys": self.total_buys,
            "total_sells": self.total_sells,
            "total_dividends": self.total_dividends,
            "total_fees": self.total_fees,
            "net_flow": self.net_flow,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "position_costs": {k: v.to_dict() for k, v in self.position_costs.items()},
            "warnings": self.warnings,
            "cashflow_by_fund": self.cashflow_by_fund,
        }
