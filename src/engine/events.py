"""
事件生成模块：从 YAML 持仓配置生成按时间排序的事件流。

支持 QDII 基金的 T+2 净值延迟确认。
"""
from datetime import date, timedelta
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional

from src.engine.calendar import is_trade_day, next_trade_day


class EventType(Enum):
    BUY = auto()
    CALIBRATE = auto()


@dataclass
class FundEvent:
    """基金事件"""
    event_type: EventType
    event_date: date
    amount: float = 0.0
    after_1500: bool = False
    actual_shares: float = 0.0


def generate_events(
    purchases: List[dict],
    dca_strategy: Optional[dict],
    calibrations: List[dict],
    today: date,
) -> List[FundEvent]:
    events: List[FundEvent] = []

    for p in purchases:
        d = _to_date(p.get("date"))
        if not d:
            continue
        events.append(FundEvent(
            event_type=EventType.BUY,
            event_date=d,
            amount=float(p.get("amount", 0)),
            after_1500=bool(p.get("after_1500", False)),
        ))

    if dca_strategy and dca_strategy.get("enabled"):
        dca_amount = float(dca_strategy.get("amount", 0))
        dca_freq = dca_strategy.get("frequency", "weekly")
        dca_start = _to_date(dca_strategy.get("start_date"))
        dca_dow = dca_strategy.get("day_of_week")

        if dca_amount > 0 and dca_start:
            dca_dates = _generate_dca_dates(dca_start, today, dca_freq, dca_dow)
            for dd in dca_dates:
                if not any(e.event_date == dd and abs(e.amount - dca_amount) < 0.01
                           for e in events if e.event_type == EventType.BUY):
                    events.append(FundEvent(
                        event_type=EventType.BUY,
                        event_date=dd,
                        amount=dca_amount,
                        after_1500=False,
                    ))

    for c in calibrations:
        d = _to_date(c.get("date"))
        if d and d <= today:
            events.append(FundEvent(
                event_type=EventType.CALIBRATE,
                event_date=d,
                actual_shares=float(c.get("actual_shares", 0)),
            ))

    events.sort(key=lambda e: e.event_date)
    return events


def resolve_nav_date(event_date: date, after_1500: bool, settle_delay: int = 1) -> date:
    """根据 T 日规则 + 结算延迟计算实际净值日。

    settle_delay: 1 = T+1 确认 (国内/混合/ETF/指数)
                 2 = T+2 确认 (QDII 海外基金)

    示例（均为交易日）：
    - 国内, 15:00 前: settle_delay=1 → 当日净值
    - 国内, 15:00 后: settle_delay=1 → 下一交易日净值
    - QDII, 15:00 前: settle_delay=2 → 下一交易日净值 (T+1)
    - QDII, 15:00 后: settle_delay=2 → 下两个交易日净值 (T+2)
    """
    if not is_trade_day(event_date):
        base = next_trade_day(event_date)
    elif after_1500:
        base = next_trade_day(event_date + timedelta(days=1))
    else:
        base = event_date

    nav_date = base
    for _ in range(settle_delay - 1):
        nav_date = next_trade_day(nav_date + timedelta(days=1))

    return nav_date


def _generate_dca_dates(
    start: date, end: date, frequency: str, day_of_week: Optional[str] = None
) -> List[date]:
    dates = []
    current = start

    while current <= end:
        actual = next_trade_day(current)
        if actual <= end and actual not in dates:
            dates.append(actual)

        if frequency == "daily":
            current = next_trade_day(current + timedelta(days=1))
        elif frequency == "weekly":
            current = _next_weekly(current, day_of_week)
        elif frequency == "biweekly":
            current = _next_weekly(current, day_of_week)
            current = _next_weekly(current + timedelta(days=1), day_of_week)
        elif frequency == "monthly":
            current = _next_monthly(current)
        else:
            break

    return dates


def _next_weekly(d: date, day_of_week: Optional[str]) -> date:
    dow_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}
    target_dow = dow_map.get(day_of_week, d.weekday()) if day_of_week else d.weekday()
    nxt = d + timedelta(days=7)
    days_ahead = target_dow - nxt.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return nxt + timedelta(days=days_ahead)


def _next_monthly(d: date) -> date:
    nxt = d + timedelta(days=31)
    return nxt.replace(day=d.day)


def _to_date(d) -> Optional[date]:
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        from datetime import datetime
        try:
            return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None
