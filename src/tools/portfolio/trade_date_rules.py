"""Trade date rules for fund transactions.

Models the 15:00 cutoff rule for mutual fund transactions in China:
- Submissions before 15:00 on trading day T → effective trade date = T
- Submissions at or after 15:00 on trading day T → effective trade date = T+1
- Submissions on non-trading days → effective trade date = next trading day

Also models confirmation and settlement date rules:
- domestic_fund_t1: confirm T+1, settle T+1
- qdii_t2: confirm T+2, settle T+2 (NAV may lag)
- money_market_t1: confirm T+1, settle T+0/T+1
- bond_fund_t1: confirm T+1, settle T+1
- unknown: no date inference allowed

This module provides:
1. `compute_effective_trade_date()` — given a submitted_at timestamp, compute
   the effective trade date for NAV lookup
2. `compute_cutoff_status()` — classify a transaction's cutoff status
3. `compute_confirm_date()` — compute confirmation date from trade date + rule profile
4. `compute_settlement_date()` — compute settlement date
5. `annotate_transaction_with_dates()` — full date annotation
6. `CUTOFF_STATUS` enumeration — known cutoff status values
7. `RULE_PROFILE` enumeration — known rule profiles
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


# ── Rule profile enumeration (M7.9) ──────────────────────────────────────

RULE_PROFILE_DOMESTIC_T1 = "domestic_fund_t1"
RULE_PROFILE_QDII_T2 = "qdii_t2"
RULE_PROFILE_MONEY_MARKET_T1 = "money_market_t1"
RULE_PROFILE_BOND_T1 = "bond_fund_t1"
RULE_PROFILE_UNKNOWN = "unknown"

VALID_RULE_PROFILES = frozenset({
    RULE_PROFILE_DOMESTIC_T1,
    RULE_PROFILE_QDII_T2,
    RULE_PROFILE_MONEY_MARKET_T1,
    RULE_PROFILE_BOND_T1,
    RULE_PROFILE_UNKNOWN,
})

# Confirm/settlement offsets by rule profile
_RULE_PROFILE_OFFSETS: dict[str, dict[str, int]] = {
    RULE_PROFILE_DOMESTIC_T1: {"confirm_offset": 1, "settlement_offset": 1},
    RULE_PROFILE_QDII_T2: {"confirm_offset": 2, "settlement_offset": 2},
    RULE_PROFILE_MONEY_MARKET_T1: {"confirm_offset": 1, "settlement_offset": 1},
    RULE_PROFILE_BOND_T1: {"confirm_offset": 1, "settlement_offset": 1},
    RULE_PROFILE_UNKNOWN: {"confirm_offset": 0, "settlement_offset": 0},
}


def infer_rule_profile(
    fund_code: str | None = None,
    fund_name: str | None = None,
    is_qdii_like: bool = False,
) -> str:
    """Infer rule profile from fund characteristics.

    Uses is_qdii_like flag and name heuristics to determine the rule profile.
    Returns RULE_PROFILE_UNKNOWN if cannot determine.
    """
    if is_qdii_like:
        return RULE_PROFILE_QDII_T2

    name = (fund_name or "").lower()
    if "qdii" in name or "QDII" in (fund_name or ""):
        return RULE_PROFILE_QDII_T2
    if "货币" in (fund_name or ""):
        return RULE_PROFILE_MONEY_MARKET_T1
    if "债" in (fund_name or ""):
        return RULE_PROFILE_BOND_T1

    # Default to domestic T+1 for any fund with a valid code
    if fund_code and fund_code.isdigit() and len(fund_code) == 6:
        return RULE_PROFILE_DOMESTIC_T1

    return RULE_PROFILE_UNKNOWN


def compute_confirm_date(
    effective_trade_date: date | None,
    rule_profile: str = RULE_PROFILE_DOMESTIC_T1,
) -> date | None:
    """Compute confirmation date from effective trade date and rule profile.

    Confirmation date is the date when the fund company confirms the
    transaction and the units are allocated.

    Args:
        effective_trade_date: The effective trade date.
        rule_profile: The rule profile for the fund.

    Returns:
        The confirmation date, or None if effective_trade_date is None
        or rule_profile is unknown.
    """
    if effective_trade_date is None:
        return None
    if rule_profile == RULE_PROFILE_UNKNOWN:
        return None

    offsets = _RULE_PROFILE_OFFSETS.get(rule_profile, {})
    confirm_offset = offsets.get("confirm_offset", 0)
    if confirm_offset == 0:
        return None

    # Skip non-trading days for offset
    current = effective_trade_date
    remaining = confirm_offset
    for _ in range(30):  # safety limit
        current += timedelta(days=1)
        if is_trading_day(current):
            remaining -= 1
            if remaining == 0:
                return current
    return current


def compute_settlement_date(
    effective_trade_date: date | None,
    rule_profile: str = RULE_PROFILE_DOMESTIC_T1,
) -> date | None:
    """Compute settlement date from effective trade date and rule profile.

    Settlement date is when the money actually changes hands.

    Args:
        effective_trade_date: The effective trade date.
        rule_profile: The rule profile for the fund.

    Returns:
        The settlement date, or None if effective_trade_date is None
        or rule_profile is unknown.
    """
    if effective_trade_date is None:
        return None
    if rule_profile == RULE_PROFILE_UNKNOWN:
        return None

    offsets = _RULE_PROFILE_OFFSETS.get(rule_profile, {})
    settlement_offset = offsets.get("settlement_offset", 0)
    if settlement_offset == 0:
        return None

    # Skip non-trading days for offset
    current = effective_trade_date
    remaining = settlement_offset
    for _ in range(30):  # safety limit
        current += timedelta(days=1)
        if is_trading_day(current):
            remaining -= 1
            if remaining == 0:
                return current
    return current


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


def annotate_transaction_with_dates(
    txn: dict[str, Any],
    rule_profile: str | None = None,
) -> dict[str, Any]:
    """Annotate a transaction with full date information (M7.9).

    Adds all date fields:
    - submitted_at, submitted_date, submitted_time
    - cutoff_time (15:00)
    - effective_trade_date
    - confirm_date
    - settlement_date
    - rule_profile

    Also calls annotate_transaction_with_cutoff for cutoff fields.

    Args:
        txn: Transaction dict with optional 'submitted_at', 'trade_date' fields.
        rule_profile: Override rule profile. If None, inferred from fund data.

    Returns:
        The same dict with added date fields.
    """
    # First apply cutoff annotation
    txn = annotate_transaction_with_cutoff(txn)

    submitted_at = _parse_datetime(txn.get("submitted_at"))

    # submitted_at, submitted_date, submitted_time
    if submitted_at is not None:
        txn["submitted_at"] = submitted_at.isoformat()
        txn["submitted_date"] = submitted_at.date().isoformat()
        txn["submitted_time"] = submitted_at.time().isoformat()
    else:
        txn["submitted_at"] = txn.get("submitted_at")
        txn["submitted_date"] = None
        txn["submitted_time"] = None

    txn["cutoff_time"] = CUTOFF_TIME.isoformat()

    # Rule profile
    if rule_profile is None:
        rule_profile = infer_rule_profile(
            fund_code=txn.get("fund_code"),
            fund_name=txn.get("fund_name"),
            is_qdii_like=txn.get("is_qdii_like", False),
        )
    txn["rule_profile"] = rule_profile

    # Effective trade date
    effective_date = _parse_date(txn.get("effective_trade_date"))

    # Confirm date
    confirm_date = compute_confirm_date(effective_date, rule_profile)
    txn["confirm_date"] = confirm_date.isoformat() if confirm_date else None

    # Settlement date
    settlement_date = compute_settlement_date(effective_date, rule_profile)
    txn["settlement_date"] = settlement_date.isoformat() if settlement_date else None

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
