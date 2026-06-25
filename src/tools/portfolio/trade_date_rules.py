"""Trade date rules for fund transactions.

Models the 15:00 cutoff rule for mutual fund transactions in China:
- Submissions before 15:00 on trading day T → effective trade date = T
- Submissions at or after 15:00 on trading day T → effective trade date = T+1
- Submissions on non-trading days → effective trade date = next trading day

This module provides:
1. `compute_effective_trade_date()` — given a submitted_at timestamp, compute
   the effective trade date for NAV lookup
2. `compute_cutoff_status()` — classify a transaction's cutoff status
3. `CUTOFF_STATUS` enumeration — known cutoff status values
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any


# ── Constants ───────────────────────────────────────────────────────────

CUTOFF_TIME = time(15, 0)  # 15:00 Beijing time

# Known Chinese public holidays (2025-2026, simplified)
# In production, this should be replaced with a proper holiday calendar API
_HOLIDAYS_2025: frozenset[date] = frozenset({
    # New Year
    date(2025, 1, 1),
    # Spring Festival
    date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2), date(2025, 2, 3), date(2025, 2, 4),
    # Qingming
    date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 6),
    # Labor Day
    date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3), date(2025, 5, 4), date(2025, 5, 5),
    # Dragon Boat
    date(2025, 5, 31), date(2025, 6, 1), date(2025, 6, 2),
    # Mid-Autumn + National Day
    date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
    date(2025, 10, 4), date(2025, 10, 5), date(2025, 10, 6), date(2025, 10, 7), date(2025, 10, 8),
})

_HOLIDAYS_2026: frozenset[date] = frozenset({
    # New Year
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
    # Spring Festival (approximate)
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 21), date(2026, 2, 22),
    # Qingming
    date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6),
    # Labor Day
    date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3), date(2026, 5, 4), date(2026, 5, 5),
    # Dragon Boat
    date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21),
    # Mid-Autumn
    date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27),
    # National Day
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
    date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7),
})

ALL_HOLIDAYS = _HOLIDAYS_2025 | _HOLIDAYS_2026


# ── Cutoff status enumeration ───────────────────────────────────────────

CUTOFF_STATUS_BEFORE = "before_cutoff"
CUTOFF_STATUS_AFTER = "after_cutoff"
CUTOFF_STATUS_NON_TRADING_DAY = "non_trading_day"
CUTOFF_STATUS_UNKNOWN = "unknown_time"

VALID_CUTOFF_STATUSES = frozenset({
    CUTOFF_STATUS_BEFORE,
    CUTOFF_STATUS_AFTER,
    CUTOFF_STATUS_NON_TRADING_DAY,
    CUTOFF_STATUS_UNKNOWN,
})


# ── Core functions ──────────────────────────────────────────────────────


def is_trading_day(d: date) -> bool:
    """Return True if d is a weekday and not a known holiday."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d not in ALL_HOLIDAYS


def next_trading_day(d: date) -> date:
    """Return the next trading day on or after d."""
    current = d
    # Safety: don't loop more than 30 days
    for _ in range(30):
        if is_trading_day(current):
            return current
        current += timedelta(days=1)
    return current


def compute_cutoff_status(
    submitted_at: datetime | None,
    trade_date: date | None,
) -> str:
    """Compute the cutoff status for a transaction.

    Args:
        submitted_at: The exact submission timestamp (with time component).
        trade_date: The trade date from the transaction record.

    Returns:
        One of the VALID_CUTOFF_STATUSES values.
    """
    if submitted_at is None and trade_date is None:
        return CUTOFF_STATUS_UNKNOWN

    if submitted_at is not None:
        # We have exact time — use it
        if not is_trading_day(submitted_at.date()):
            return CUTOFF_STATUS_NON_TRADING_DAY
        if submitted_at.time() < CUTOFF_TIME:
            return CUTOFF_STATUS_BEFORE
        return CUTOFF_STATUS_AFTER

    # No submitted_at, only trade_date — we don't know the exact time
    return CUTOFF_STATUS_UNKNOWN


def compute_effective_trade_date(
    submitted_at: datetime | None = None,
    trade_date: date | None = None,
) -> date | None:
    """Compute the effective trade date for NAV lookup.

    Rules:
    - If submitted_at is available:
      - Before 15:00 on a trading day → effective date = submitted_at.date()
      - At or after 15:00 on a trading day → effective date = next trading day
      - On a non-trading day → effective date = next trading day
    - If only trade_date is available (no time component):
      - Return trade_date as-is (assume it's already the effective date)
    - If neither is available → return None

    Args:
        submitted_at: The exact submission timestamp.
        trade_date: The trade date from the transaction record.

    Returns:
        The effective trade date for NAV lookup, or None.
    """
    if submitted_at is not None:
        d = submitted_at.date()
        if not is_trading_day(d):
            return next_trading_day(d + timedelta(days=1))
        if submitted_at.time() >= CUTOFF_TIME:
            return next_trading_day(d + timedelta(days=1))
        return d

    if trade_date is not None:
        return trade_date

    return None


def annotate_transaction_with_cutoff(txn: dict[str, Any]) -> dict[str, Any]:
    """Annotate a transaction with cutoff status and effective trade date.

    Adds the following fields to the transaction dict:
    - cutoff_status: one of VALID_CUTOFF_STATUSES
    - effective_trade_date: the date to use for NAV lookup
    - nav_date_note: human-readable explanation

    Does NOT modify the original trade_date field.

    Args:
        txn: Transaction dict with optional 'submitted_at', 'trade_date' fields.

    Returns:
        The same dict with added cutoff fields.
    """
    submitted_at = _parse_datetime(txn.get("submitted_at"))
    trade_date = _parse_date(txn.get("trade_date"))

    cutoff_status = compute_cutoff_status(submitted_at, trade_date)
    effective_date = compute_effective_trade_date(submitted_at, trade_date)

    txn["cutoff_status"] = cutoff_status
    txn["effective_trade_date"] = effective_date.isoformat() if effective_date else None

    # Human-readable note
    if cutoff_status == CUTOFF_STATUS_BEFORE:
        txn["nav_date_note"] = "Submitted before 15:00 cutoff; NAV date = trade date"
    elif cutoff_status == CUTOFF_STATUS_AFTER:
        txn["nav_date_note"] = "Submitted at/after 15:00 cutoff; NAV date = next trading day"
    elif cutoff_status == CUTOFF_STATUS_NON_TRADING_DAY:
        txn["nav_date_note"] = "Submitted on non-trading day; NAV date = next trading day"
    else:
        txn["nav_date_note"] = "Submission time unknown; NAV date = trade_date (unadjusted)"

    return txn


# ── Internal helpers ────────────────────────────────────────────────────


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a datetime from various input formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return None


def _parse_date(value: Any) -> date | None:
    """Parse a date from various input formats."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            pass
    return None
