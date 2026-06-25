"""Safe numeric parsing helpers for fund_analysis.

Provides _safe_float and _safe_int for host-injected numeric fields
that may be malformed strings. These helpers prevent crashes from
invalid fee_pct, holding_days, or other numeric inputs.

Also provides _has_valuation and _position_current_value to enforce
the rule that current_value=None / cashflow_only positions must NOT
be silently converted to 0.0.
"""

from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _has_valuation(pos: dict[str, Any]) -> bool:
    """Check whether a position has a real current_value (not None/missing).

    Positions with valuation_type=cashflow_only, none, or identity_mismatch
    must be excluded from P&L, contribution, HHI, and risk calculations.
    """
    cv = pos.get("current_value")
    if cv is None:
        return False
    vt = pos.get("valuation_type")
    if vt in ("cashflow_only", "none"):
        return False
    return True


def _position_current_value(pos: dict[str, Any]) -> float | None:
    """Get current_value from a position, returning None if unavailable.

    Unlike float(pos.get("current_value", 0) or 0), this preserves None
    for cashflow_only / valuation_blocked positions instead of converting
    to 0.0.
    """
    if not _has_valuation(pos):
        return None
    try:
        return float(pos["current_value"])
    except (TypeError, ValueError):
        return None
