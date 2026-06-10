"""Safe numeric parsing helpers for fund_analysis.

Provides _safe_float and _safe_int for host-injected numeric fields
that may be malformed strings. These helpers prevent crashes from
invalid fee_pct, holding_days, or other numeric inputs.
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
