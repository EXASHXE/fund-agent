"""Holdings snapshot overlay — merge authoritative snapshot into reconstructed portfolio.

When a current holdings snapshot is available, it provides authoritative data
for current shares, NAV, and market value. This module merges snapshot data
into the reconstructed portfolio, overriding reconstructed values where the
snapshot is more authoritative.

Key rules:
- Snapshot shares + latest_nav → current_value (valuation_type = "holdings_snapshot")
- Snapshot current_value → platform_reported_current_value (not mixed with reconstructed)
- Snapshot + reconstruction shares disagree → reconciliation_gap flag
- Snapshot user_verified=true → identity_verification_status = user_verified_override
- Snapshot positions not in reconstruction → added as snapshot-only positions
- Reconciliation gaps are flagged, never silently merged
"""
from __future__ import annotations

import math
from typing import Any

from scripts.fund_identity_utils import normalize_fund_name


def apply_holdings_snapshot_overlay(
    confirmed_portfolio: dict[str, Any],
    holdings_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Apply holdings snapshot overlay to reconstructed portfolio.

    Args:
        confirmed_portfolio: Reconstructed portfolio dict (from reconstruct_portfolio).
        holdings_snapshot: Normalized holdings snapshot dict (from load_current_holdings_snapshot).

    Returns:
        Updated portfolio dict with snapshot data merged in. The input
        confirmed_portfolio is NOT mutated; a new dict is returned.
    """
    import copy
    portfolio = copy.deepcopy(confirmed_portfolio)

    snapshot_positions = holdings_snapshot.get("positions", [])
    reconstructed_positions = portfolio.get("positions", [])

    # Build lookup maps for matching
    by_code: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for pos in reconstructed_positions:
        fc = pos.get("fund_code")
        fn = pos.get("fund_name") or ""
        if fc:
            by_code[fc] = pos
        if fn:
            by_name[normalize_fund_name(fn)] = pos

    matched_reconstructed: set[int] = set()  # indices of matched positions
    reconciliation_gaps: list[dict[str, Any]] = []

    for snap_pos in snapshot_positions:
        snap_code = snap_pos.get("fund_code")
        snap_name = snap_pos.get("fund_name") or ""
        snap_shares = snap_pos.get("shares")
        snap_latest_nav = snap_pos.get("latest_nav")
        snap_current_value = snap_pos.get("current_value")
        snap_user_verified = snap_pos.get("user_verified")
        snap_holding_cost = snap_pos.get("holding_cost")
        snap_holding_profit = snap_pos.get("holding_profit")
        snap_holding_profit_pct = snap_pos.get("holding_profit_pct")
        snap_nav_date = snap_pos.get("nav_date")

        # Match by fund_code first, then by normalized name
        recon_pos = None
        if snap_code and snap_code in by_code:
            recon_pos = by_code[snap_code]
        elif snap_name:
            norm_name = normalize_fund_name(snap_name)
            if norm_name in by_name:
                recon_pos = by_name[norm_name]

        if recon_pos is not None:
            # ── Matched position: apply overlay ───────────────────────
            idx = reconstructed_positions.index(recon_pos)
            matched_reconstructed.add(idx)

            # Record snapshot data as platform_reported fields
            if snap_current_value is not None:
                recon_pos["platform_reported_current_value"] = snap_current_value
                recon_pos["platform_reported_source"] = snap_pos.get("source", "holdings_snapshot")

            if snap_holding_profit is not None:
                recon_pos["platform_reported_profit"] = snap_holding_profit
                recon_pos["platform_reported_profit_pct"] = snap_holding_profit_pct

            if snap_holding_cost is not None:
                recon_pos["platform_reported_cost"] = snap_holding_cost

            # User-verified identity override (Phase 4)
            if snap_user_verified and snap_code:
                recon_pos["identity_verification_status"] = "user_verified_override"
                recon_pos["identity_verified_by"] = "holdings_snapshot_user_verified"
                # Remove identity_unverified from data_quality if present
                dq = recon_pos.get("data_quality", [])
                if "identity_unverified" in dq:
                    dq.remove("identity_unverified")
                recon_pos["data_quality"] = dq

            # Authoritative shares from snapshot
            if snap_shares is not None:
                recon_units = recon_pos.get("units")

                # Check for reconciliation gap
                if recon_units is not None:
                    # Allow small floating-point difference (0.01 units)
                    if abs(float(snap_shares) - float(recon_units)) > 0.01:
                        reconciliation_gaps.append({
                            "fund_code": snap_code,
                            "fund_name": snap_name,
                            "gap_type": "shares_mismatch",
                            "snapshot_shares": float(snap_shares),
                            "reconstructed_units": float(recon_units),
                            "difference": _safe_round(float(snap_shares) - float(recon_units), 4),
                        })
                        recon_pos["reconciliation_gap"] = "shares_mismatch"
                        recon_pos["snapshot_shares"] = float(snap_shares)
                        recon_pos["data_quality"] = recon_pos.get("data_quality", []) + ["reconciliation_gap_shares"]

                # Override units with snapshot value
                recon_pos["units"] = _safe_round(float(snap_shares), 4)
                recon_pos["units_source"] = "holdings_snapshot"
                recon_pos["snapshot_shares"] = float(snap_shares)

            # Authoritative latest_nav from snapshot
            if snap_latest_nav is not None:
                recon_pos["latest_nav"] = float(snap_latest_nav)
                if snap_nav_date:
                    recon_pos["latest_nav_date"] = snap_nav_date
                recon_pos["nav_source"] = "holdings_snapshot"

            # Compute current_value from snapshot shares + latest_nav
            if snap_shares is not None and snap_latest_nav is not None:
                computed_value = _safe_round(float(snap_shares) * float(snap_latest_nav))
                recon_pos["current_value"] = computed_value
                recon_pos["valuation_type"] = "holdings_snapshot"
                recon_pos["valuation_source"] = "authoritative_holdings_snapshot"
                # Remove valuation-blocked flags since snapshot provides authoritative data
                dq = recon_pos.get("data_quality", [])
                dq = [f for f in dq if f not in (
                    "valuation_blocked_cashflow_only",
                    "valuation_blocked_no_nav",
                    "identity_unverified",
                    "partial_lot_coverage",
                )]
                recon_pos["data_quality"] = dq
                # Clear position_valuation_status override
                recon_pos["position_valuation_status"] = "holdings_snapshot_valued"
            elif snap_current_value is not None:
                # Snapshot provides current_value directly but not shares+nav
                # Use platform_reported_current_value but don't override current_value
                # unless the reconstructed position has no current_value
                if recon_pos.get("current_value") is None:
                    recon_pos["current_value"] = float(snap_current_value)
                    recon_pos["valuation_type"] = "holdings_snapshot_reported"
                    recon_pos["valuation_source"] = "platform_reported_current_value"

            # Mark holding_source
            recon_pos["holding_source"] = "holdings_snapshot_authoritative"
            recon_pos["snapshot_matched"] = True

        else:
            # ── Unmatched snapshot position: add as snapshot-only ──────
            new_pos = _build_snapshot_only_position(snap_pos)
            reconstructed_positions.append(new_pos)

    # ── Recompute portfolio-level summary ─────────────────────────────
    _recompute_portfolio_summary(portfolio, reconciliation_gaps)

    return portfolio


def _build_snapshot_only_position(snap_pos: dict[str, Any]) -> dict[str, Any]:
    """Build a position dict from a snapshot position with no reconstruction match."""
    snap_shares = snap_pos.get("shares")
    snap_latest_nav = snap_pos.get("latest_nav")
    snap_current_value = snap_pos.get("current_value")

    # Compute current_value if shares + nav available
    current_value = None
    valuation_type = "none"
    valuation_source = "none"
    if snap_shares is not None and snap_latest_nav is not None:
        current_value = _safe_round(float(snap_shares) * float(snap_latest_nav))
        valuation_type = "holdings_snapshot"
        valuation_source = "authoritative_holdings_snapshot"
    elif snap_current_value is not None:
        current_value = float(snap_current_value)
        valuation_type = "holdings_snapshot_reported"
        valuation_source = "platform_reported_current_value"

    # Identity verification status from snapshot
    identity_status = snap_pos.get("identity_verification_status", "name_only")

    return {
        "fund_code": snap_pos.get("fund_code"),
        "fund_name": snap_pos.get("fund_name"),
        "units": _safe_round(float(snap_shares), 4) if snap_shares is not None else None,
        "units_source": "holdings_snapshot" if snap_shares is not None else "unavailable",
        "current_value": current_value,
        "cost_basis": _safe_round(float(snap_pos["holding_cost"])) if snap_pos.get("holding_cost") is not None else None,
        "average_cost_per_unit": None,
        "latest_nav": float(snap_latest_nav) if snap_latest_nav is not None else None,
        "latest_nav_date": snap_pos.get("nav_date"),
        "valuation_type": valuation_type,
        "valuation_source": valuation_source,
        "valuation_quality": "snapshot_authoritative" if valuation_type == "holdings_snapshot" else "snapshot_reported",
        "identity_verification_status": identity_status,
        "platform_reported_current_value": float(snap_current_value) if snap_current_value is not None else None,
        "platform_reported_profit": float(snap_pos["holding_profit"]) if snap_pos.get("holding_profit") is not None else None,
        "platform_reported_profit_pct": snap_pos.get("holding_profit_pct"),
        "platform_reported_cost": _safe_round(float(snap_pos["holding_cost"])) if snap_pos.get("holding_cost") is not None else None,
        "platform_reported_source": snap_pos.get("source", "holdings_snapshot"),
        "data_quality": ["snapshot_only_position"],
        "holding_source": "holdings_snapshot_only",
        "snapshot_matched": False,
        "confidence": "snapshot_reported" if snap_pos.get("user_verified") else "snapshot_unverified",
    }


def _recompute_portfolio_summary(
    portfolio: dict[str, Any],
    reconciliation_gaps: list[dict[str, Any]],
) -> None:
    """Recompute portfolio-level summary after overlay application."""
    positions = portfolio.get("positions", [])

    valued_positions_count = sum(1 for p in positions if p.get("current_value") is not None)
    total_positions_count = len(positions)
    total_value = sum(
        float(p["current_value"])
        for p in positions
        if p.get("current_value") is not None
    )
    known_valued_amount = _safe_round(total_value)

    # Recompute portfolio_valuation_status
    if valued_positions_count == 0:
        portfolio_valuation_status = "unavailable"
    elif valued_positions_count < total_positions_count:
        portfolio_valuation_status = "partial_diagnostic_only"
    else:
        portfolio_valuation_status = "estimated_full_coverage"

    # Total current value only when full coverage
    total_current_value = _safe_round(total_value) if portfolio_valuation_status in ("estimated_full_coverage", "confirmed") else None

    # Valuation type counts
    valuation_type_counts: dict[str, int] = {}
    for p in positions:
        vt = p.get("valuation_type", "none")
        valuation_type_counts[vt] = valuation_type_counts.get(vt, 0) + 1

    # Snapshot-specific counts
    snapshot_valued_count = sum(
        1 for p in positions
        if p.get("valuation_type") in ("holdings_snapshot", "holdings_snapshot_reported")
    )
    snapshot_matched_count = sum(1 for p in positions if p.get("snapshot_matched") is True)
    snapshot_only_count = sum(1 for p in positions if p.get("holding_source") == "holdings_snapshot_only")

    # Update summary
    summary = portfolio.get("summary", {})
    summary["total_positions"] = total_positions_count
    summary["valued_positions_count"] = valued_positions_count
    summary["total_current_value"] = total_current_value
    summary["known_valued_amount"] = known_valued_amount
    summary["portfolio_valuation_status"] = portfolio_valuation_status
    summary["is_partial_diagnostic"] = portfolio_valuation_status in ("partial_diagnostic_only", "unavailable")
    summary["valuation_type_counts"] = valuation_type_counts
    summary["holdings_snapshot_valued_count"] = snapshot_valued_count
    summary["holdings_snapshot_matched_count"] = snapshot_matched_count
    summary["holdings_snapshot_only_count"] = snapshot_only_count
    summary["reconciliation_gap_count"] = len(reconciliation_gaps)
    summary["reconciliation_gaps"] = reconciliation_gaps

    portfolio["summary"] = summary


def _safe_round(value: float | None, decimals: int = 2) -> float | None:
    """Round a value, returning None if input is None."""
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(value, decimals)
