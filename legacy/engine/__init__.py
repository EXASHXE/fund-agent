"""
事件驱动基金收益计算引擎。

使用交易日历 + T+1顺延规则 + 份额校准 + XIRR 计算真实年化收益。
"""
from legacy.engine.calculator import compute_fund, compute_portfolio
from legacy.engine.calendar import get_trade_calendar, is_trade_day, next_trade_day

__all__ = ["compute_fund", "compute_portfolio", "get_trade_calendar", "is_trade_day", "next_trade_day"]
