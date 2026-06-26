"""NAV coverage quality diagnostics for portfolio reconstruction.

Analyzes trade-date NAV coverage, valuation quality, stale NAV, and
QDII-like detection for each fund position. No network calls, no private
data in output — counts and status labels only.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Sequence

# Stale NAV thresholds (calendar days)
DOMESTIC_STALE_THRESHOLD_DAYS = 7
QDII_STALE_THRESHOLD_DAYS = 10

# Actions that require trade-date NAV for unit estimation
_NAV_REQUIRED_ACTIONS = {"buy", "sell"}

# Actions that are always manual-review
_MANUAL_REVIEW_ACTIONS = {"conversion", "refund", "unknown"}


def compute_nav_coverage(
    *,
    fund_code: str | None,
    transactions: Sequence[Mapping[str, Any]],
    nav_records: Sequence[Mapping[str, Any]] | None = None,
    as_of_date: date | None = None,
    is_qdii_like: bool = False,
    provider_name: str | None = None,
    provider_available: bool = True,
    provider_error_count: int = 0,
    nav_history_window_days: int | None = None,
) -> dict[str, Any]:
    """Compute NAV coverage diagnostics for a single fund.

    Args:
        fund_code: Fund identifier (may be None for name-only).
        transactions: Normalized ledger transactions for this fund.
        nav_records: NAV snapshot records [{date, nav}, ...].
        as_of_date: Reference date for stale NAV detection.
        is_qdii_like: Whether this fund is QDII-like (from profile).
        provider_name: Name of the NAV data provider (e.g. "akshare").
        provider_available: Whether the provider was reachable.
        provider_error_count: Number of provider errors for this fund.
        nav_history_window_days: Window of NAV history retrieved (days).

    Returns:
        Dict with coverage_status, valuation_quality, warnings, provider_diagnostics, etc.
    """
    trade_count = 0
    trades_with_nav = 0
    trades_with_explicit_units = 0
    trades_missing_nav = 0
    nav_gap_count = 0  # trades where trade-date NAV is missing (info only)
    nav_used_for_units_count = 0  # trades where trade-date NAV was used to derive units
    has_manual_review_action = False
    has_validation_warnings = False
    latest_nav: float | None = None
    latest_nav_date: str | None = None
    latest_nav_stale_days: int | None = None
    nav_used_for_current_value = False  # whether latest NAV was used for current_value

    # Count transaction types
    for txn in transactions:
        action = str(txn.get("action", "")).lower()
        amount = txn.get("amount")

        # Check for manual-review actions
        if action in _MANUAL_REVIEW_ACTIONS:
            has_manual_review_action = True

        # Check for validation warnings
        if txn.get("needs_manual_review"):
            has_validation_warnings = True

        # Only buy/sell require NAV for unit estimation
        if action not in _NAV_REQUIRED_ACTIONS:
            continue

        trade_count += 1

        # Check if explicit units provided
        has_units = txn.get("units") is not None and isinstance(txn.get("units"), (int, float))

        # Check if trade-date NAV available
        trade_date = txn.get("trade_date")
        trade_nav = _get_nav_on_date(nav_records or [], trade_date)

        if has_units:
            trades_with_explicit_units += 1
            # Explicit units don't require NAV for coverage, but track the gap
            if trade_nav is None:
                nav_gap_count += 1
        elif trade_nav is not None:
            trades_with_nav += 1
            nav_used_for_units_count += 1
        else:
            trades_missing_nav += 1
            nav_gap_count += 1

    # Get latest NAV
    if nav_records and as_of_date:
        latest_nav, latest_nav_date = _get_latest_nav(nav_records, as_of_date)
        if latest_nav_date:
            nav_date = date.fromisoformat(latest_nav_date)
            stale_days = (as_of_date - nav_date).days
            threshold = QDII_STALE_THRESHOLD_DAYS if is_qdii_like else DOMESTIC_STALE_THRESHOLD_DAYS
            if stale_days > threshold:
                latest_nav_stale_days = stale_days

    # Compute coverage ratio
    nav_required_trades = trade_count - trades_with_explicit_units
    if nav_required_trades > 0:
        trade_nav_coverage_ratio = round(trades_with_nav / nav_required_trades, 4)
    else:
        # All trades have explicit units — NAV coverage is conceptually full
        trade_nav_coverage_ratio = 1.0 if trade_count > 0 else 0.0

    # Determine coverage_status
    # trades_missing_nav counts only trades that need NAV but don't have it
    # (trades with explicit units are NOT counted as missing)
    if trade_count == 0:
        coverage_status = "none"
    elif trades_missing_nav == 0:
        coverage_status = "full"
    elif trades_with_nav > 0 or trades_with_explicit_units > 0:
        coverage_status = "partial"
    elif latest_nav is not None:
        coverage_status = "latest_only"
    else:
        coverage_status = "none"

    # Determine valuation_quality
    if has_manual_review_action or has_validation_warnings:
        valuation_quality = "manual_review_required"
    elif coverage_status == "full" and trade_count > 0:
        valuation_quality = "estimated_full_coverage"
    elif coverage_status == "partial":
        valuation_quality = "estimated_partial_coverage"
    elif coverage_status == "latest_only":
        valuation_quality = "cashflow_only"
    elif coverage_status == "none":
        valuation_quality = "unavailable"
    else:
        valuation_quality = "cashflow_only"

    # Build warnings
    warnings: list[str] = []
    if trades_missing_nav > 0:
        warnings.append(f"fund has {trades_missing_nav} trade(s) missing trade-date NAV")
    if nav_gap_count > 0 and trades_missing_nav == 0:
        # All gaps are covered by explicit units, but note the gap
        warnings.append(f"fund has {nav_gap_count} trade(s) without trade-date NAV (covered by explicit units)")
    if latest_nav_stale_days is not None:
        warnings.append(f"latest NAV is {latest_nav_stale_days} day(s) stale")
    if has_manual_review_action:
        warnings.append("fund has conversion/refund/unknown transactions requiring manual review")

    return {
        "fund_code": fund_code,
        "trade_count": trade_count,
        "trades_with_trade_date_nav": trades_with_nav,
        "trades_with_explicit_units": trades_with_explicit_units,
        "trades_missing_trade_date_nav": trades_missing_nav,
        "trades_nav_gap_count": nav_gap_count,
        "trade_nav_coverage_ratio": trade_nav_coverage_ratio,
        "latest_nav_available": latest_nav is not None,
        "latest_nav_date": latest_nav_date,
        "latest_nav_stale_days": latest_nav_stale_days,
        "is_qdii_like": is_qdii_like,
        "coverage_status": coverage_status,
        "valuation_quality": valuation_quality,
        "warnings": warnings,
        "nav_used_for_units_count": nav_used_for_units_count,
        "nav_used_for_current_value_count": 1 if nav_used_for_current_value else 0,
        "provider_diagnostics": {
            "provider_name": provider_name,
            "provider_available": provider_available,
            "provider_error_count": provider_error_count,
            "nav_history_window_days": nav_history_window_days,
            "trade_date_nav_requested_count": trade_count - trades_with_explicit_units,
            "trade_date_nav_found_count": trades_with_nav,
            "latest_nav_found_count": 1 if latest_nav is not None else 0,
            "latest_nav_only_count": 1 if coverage_status == "latest_only" else 0,
            "nav_used_for_units_count": nav_used_for_units_count,
            "nav_used_for_current_value_count": 1 if nav_used_for_current_value else 0,
        },
    }


def compute_portfolio_nav_coverage(
    positions: Sequence[Mapping[str, Any]],
    *,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Compute NAV coverage summary across all portfolio positions.

    Args:
        positions: List of position dicts from reconstruction output.
        as_of_date: Reference date for stale NAV computation.

    Returns:
        Portfolio-level NAV coverage summary.
    """
    positions_total = len(positions)
    positions_estimated = 0
    positions_cashflow_only = 0
    positions_unavailable = 0
    positions_manual_review_required = 0
    nav_coverage_full_count = 0
    nav_coverage_partial_count = 0
    nav_coverage_none_count = 0
    nav_coverage_latest_only_count = 0
    latest_nav_stale_count = 0
    qdii_like_count = 0
    estimated_current_value_total = 0.0
    estimated_current_value_coverage_count = 0
    trade_date_nav_requested_count = 0
    trade_date_nav_found_count = 0

    for pos in positions:
        vt = pos.get("valuation_type", "none")
        vq = pos.get("valuation_quality", "unavailable")
        cs = pos.get("nav_coverage_status", pos.get("coverage_status", "none"))

        if vt == "estimated":
            positions_estimated += 1
        elif vt == "cashflow_only":
            positions_cashflow_only += 1
        elif vt == "none":
            positions_unavailable += 1

        if vq == "manual_review_required":
            positions_manual_review_required += 1

        if cs == "full":
            nav_coverage_full_count += 1
        elif cs == "partial":
            nav_coverage_partial_count += 1
        elif cs == "latest_only":
            nav_coverage_latest_only_count += 1
        else:
            nav_coverage_none_count += 1

        if pos.get("latest_nav_stale_days") is not None:
            latest_nav_stale_count += 1

        if pos.get("is_qdii_like"):
            qdii_like_count += 1

        cv = pos.get("current_value")
        if cv is not None and isinstance(cv, (int, float)) and cv > 0:
            estimated_current_value_total += float(cv)
            estimated_current_value_coverage_count += 1

        # Aggregate provider diagnostics
        pd = pos.get("provider_diagnostics", {})
        if isinstance(pd, dict):
            trade_date_nav_requested_count += int(pd.get("trade_date_nav_requested_count", 0))
            trade_date_nav_found_count += int(pd.get("trade_date_nav_found_count", 0))

    estimated_current_value_total_is_partial = (
        positions_estimated > 0 and estimated_current_value_coverage_count < positions_total
    )

    return {
        "positions_total": positions_total,
        "positions_estimated": positions_estimated,
        "positions_cashflow_only": positions_cashflow_only,
        "positions_unavailable": positions_unavailable,
        "positions_manual_review_required": positions_manual_review_required,
        "nav_coverage_full_count": nav_coverage_full_count,
        "nav_coverage_partial_count": nav_coverage_partial_count,
        "nav_coverage_none_count": nav_coverage_none_count,
        "nav_coverage_latest_only_count": nav_coverage_latest_only_count,
        "latest_nav_stale_count": latest_nav_stale_count,
        "qdii_like_count": qdii_like_count,
        "estimated_current_value_total": round(estimated_current_value_total, 2),
        "estimated_current_value_coverage_count": estimated_current_value_coverage_count,
        "estimated_current_value_total_is_partial": estimated_current_value_total_is_partial,
        "trade_date_nav_requested_count": trade_date_nav_requested_count,
        "trade_date_nav_found_count": trade_date_nav_found_count,
    }


# ── Internal helpers ──────────────────────────────────────────────────


def _get_latest_nav(
    nav_records: Sequence[Mapping[str, Any]],
    as_of_date: date,
) -> tuple[float | None, str | None]:
    """Get the latest NAV at or before as_of_date from records."""
    latest_nav = None
    latest_date = None
    for rec in nav_records:
        d = _parse_date(rec.get("date"))
        nav = rec.get("nav")
        if d and nav is not None and d <= as_of_date and (latest_date is None or d > latest_date):
            latest_nav = float(nav)
            latest_date = d
    return latest_nav, latest_date.isoformat() if latest_date else None


def _get_nav_on_date(
    nav_records: Sequence[Mapping[str, Any]],
    target_date_str: str | None,
) -> float | None:
    """Get NAV on a specific date."""
    if not target_date_str or not nav_records:
        return None
    target = _parse_date(target_date_str)
    if not target:
        return None
    for rec in nav_records:
        d = _parse_date(rec.get("date"))
        nav = rec.get("nav")
        if d and nav is not None and d == target:
            return float(nav)
    return None


def _parse_date(val) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None
