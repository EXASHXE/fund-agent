"""Pure date utility functions: business day checks, DCA date calculation, date conversion.

All functions are pure: no IO, no network, no LLM dependencies.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional


def is_business_day(d: date) -> bool:
    """Check if a date is a business day (simplified: Mon-Fri, no holiday calendar)."""
    return d.weekday() < 5


def next_business_day(d: date) -> date:
    """Get the next business day after *d* (exclusive of *d* itself)."""
    nxt = d + timedelta(days=1)
    while not is_business_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def next_dca_date(current: date, frequency: str, day_of_week: str = None) -> date:
    """Calculate the next DCA (dollar-cost averaging) date.

    Args:
        current: Current reference date.
        frequency: One of "daily", "weekly", "biweekly", "monthly".
        day_of_week: Optional day name for weekly frequency ("mon"-"fri").

    Returns:
        The next DCA date, always a business day.
    """
    if frequency == "daily":
        nxt = current + timedelta(days=1)
        while not is_business_day(nxt):
            nxt += timedelta(days=1)
        return nxt
    elif frequency == "weekly":
        if day_of_week:
            dow_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}
            target_dow = dow_map.get(day_of_week, current.weekday())
            nxt = current + timedelta(days=7)
            days_ahead = target_dow - nxt.weekday()
            if days_ahead < 0:
                days_ahead += 7
            nxt = nxt + timedelta(days=days_ahead)
        else:
            nxt = current + timedelta(days=7)
        return nxt
    elif frequency == "biweekly":
        nxt = current + timedelta(days=14)
        while not is_business_day(nxt):
            nxt += timedelta(days=1)
        return nxt
    elif frequency == "monthly":
        nxt = current + timedelta(days=30)
        while not is_business_day(nxt):
            nxt += timedelta(days=1)
        return nxt
    else:
        return current + timedelta(days=7)


def to_date(d) -> Optional[date]:
    """Safely convert various types to a ``date`` object.

    Accepts: ``date``, ``datetime``, ISO-format ``str`` (``"YYYY-MM-DD"``).
    Returns ``None`` for unparseable or ``None`` input.
    """
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None
