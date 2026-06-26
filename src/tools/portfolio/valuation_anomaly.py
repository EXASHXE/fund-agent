"""Valuation anomaly sanity checks (M7.4 Phase 4).

Detects extreme returns, inconsistent units, and other anomalies in
reconstructed portfolio positions. Anomalies with severity 'blocker'
suppress current_value in the output.
"""
from __future__ import annotations

from typing import Any


# ── Thresholds ──────────────────────────────────────────────────────────

# Normal fund: > 50% return is extreme
EXTREME_RETURN_THRESHOLD_NORMAL = 0.50
# QDII/sector fund: > 80% return is extreme
EXTREME_RETURN_THRESHOLD_QDII = 0.80


def check_valuation_anomalies(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check positions for valuation anomalies.

    For each position with current_value and cost_basis:
    - Compute return_pct = (current_value - cost_basis) / cost_basis
    - Flag extreme returns based on fund type thresholds
    - If extreme_return + units_source not all_explicit → severity blocker
    - If extreme_return + units_source is all_explicit → severity warning

    Args:
        positions: List of position dicts from reconstruct_portfolio.

    Returns:
        List of anomaly dicts with fund_code, flags, severity, message.
    """
    anomalies: list[dict[str, Any]] = []

    for pos in positions:
        fund_code = pos.get("fund_code", "")
        current_value = pos.get("current_value")
        cost_basis = pos.get("cost_basis")
        is_qdii = pos.get("is_qdii_like", False)
        units_source = pos.get("total_units_source", pos.get("units_source", ""))
        position_status = pos.get("position_valuation_status", "")
        identity_status = pos.get("identity_verification_status", "")

        flags: list[str] = []
        severity = "info"
        messages: list[str] = []

        # Skip positions without valuation
        if current_value is None or cost_basis is None or cost_basis == 0:
            continue

        # Compute return
        return_pct = (current_value - cost_basis) / cost_basis
        threshold = EXTREME_RETURN_THRESHOLD_QDII if is_qdii else EXTREME_RETURN_THRESHOLD_NORMAL

        # Check extreme return
        if abs(return_pct) >= threshold:
            flags.append("extreme_return")
            direction = "gain" if return_pct > 0 else "loss"
            messages.append(
                f"Extreme {direction}: {return_pct:.1%} return "
                f"(threshold: {threshold:.0%})"
            )

            # Severity depends on units evidence
            if units_source != "all_explicit":
                severity = "blocker"
                messages.append(
                    "Units not from explicit source — likely a units/NAV/code error"
                )
            else:
                severity = "warning"
                messages.append(
                    "Units from explicit source — value might be real but verify"
                )

        # Check for identity unverified (always flag regardless of extreme return)
        if identity_status == "manual_override_unverified":
            flags.append("code_name_unverified")
            messages.append("Identity unverified — fund code may be wrong")
            if severity != "blocker":
                severity = "warning"

        # Check for partial lot coverage
        if position_status == "estimated_partial_lot_coverage":
            flags.append("partial_lot_coverage")
            if severity != "blocker":
                severity = "warning"
            messages.append("Partial lot coverage — valuation may be incomplete")

        # Check for QDII NAV lag
        if is_qdii and pos.get("latest_nav_stale_days", 0) > 3:
            flags.append("qdii_nav_lag")
            messages.append("QDII NAV may be lagged")

        if flags:
            anomalies.append({
                "fund_code": fund_code,
                "flags": flags,
                "severity": severity,
                "message": "; ".join(messages),
                "return_pct": return_pct,
            })

    return anomalies
