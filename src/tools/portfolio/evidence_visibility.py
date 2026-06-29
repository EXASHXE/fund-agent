"""Evidence visibility sanitization — M7.6 blocked evidence firewall.

Controls what position-level data is visible at each output boundary:
- public_report: end-user report (report.md)
- agent_context: agent-facing context (agent_context.json/md)
- private_debug: debug/diagnostic artifacts only
- blocked: never emitted

When a fund's identity is unverified, candidate codes, estimated units,
latest NAV, NAV vs avg cost, and P&L must NOT appear in public reports
or agent analysis. Only raw_fund_name, transaction counts, and cashflow
costs are safe to display.
"""
from __future__ import annotations

from typing import Any

# ── Identity statuses that block valuation and hide identity-dependent fields ──
BLOCKED_IDENTITY_STATUSES = frozenset({
    "manual_override_unverified",
    "code_name_mismatch",
    "provider_lookup_failed",
    "invalid_code",
    "name_only",
    "name_search_candidate_unverified",
})

# ── Valuation types that indicate identity-blocked positions ──────────────
BLOCKED_VALUATION_TYPES = frozenset({
    "cashflow_only",
    "none",
})

# ── Allowed verification sources for verified_by_user ────────────────────
ALLOWED_VERIFICATION_SOURCES = frozenset({
    "alipay_holdings_page",
    "fund_detail_page",
    "official_fund_statement",
    "provider_cross_check",
    "user_manual_verified",
    "provider_name_search",
})


def is_identity_blocked(position: dict[str, Any]) -> bool:
    """Check if a position has a blocked identity status.

    A blocked identity means the fund code is unverified and must NOT
    be displayed as a confirmed code in reports or agent context.
    """
    identity_status = position.get("identity_verification_status", "")
    return identity_status in BLOCKED_IDENTITY_STATUSES


def is_valuation_blocked(position: dict[str, Any]) -> bool:
    """Check if a position has a blocked valuation type.

    A blocked valuation means current_value/units/NAV are unreliable
    and must NOT appear in public reports.
    """
    valuation_type = position.get("valuation_type", "")
    return valuation_type in BLOCKED_VALUATION_TYPES


def sanitize_position_for_public_report(position: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a position for public report visibility.

    When identity is blocked:
    - fund_code → replaced with "unverified candidate" label
    - estimated_units, latest_nav, nav_date, nav_coverage → removed
    - avg_cost, nav_vs_avg_cost → removed
    - current_value, unrealized_pnl, return_pct → removed
    - trend signals → removed

    Only raw_fund_name, transaction counts, and cashflow costs are preserved.
    """
    if not is_identity_blocked(position) and not is_valuation_blocked(position):
        # Identity verified and valuation available — pass through with minimal filtering
        return _copy_safe_fields(position)

    # Identity or valuation is blocked — only show safe fields
    safe: dict[str, Any] = {}

    # Always safe: raw fund name from transaction source
    raw_name = position.get("fund_name") or position.get("raw_fund_name", "")
    if raw_name:
        safe["raw_fund_name"] = raw_name

    # Safe: transaction counts
    for count_key in (
        "buy_count", "sell_count", "conversion_count",
        "total_transaction_count", "transaction_count",
    ):
        val = position.get(count_key)
        if val is not None:
            safe[count_key] = val

    # Safe: cashflow costs (these come from transactions, not valuation)
    for cf_key in (
        "total_cost", "gross_buy", "gross_sell",
        "net_cashflow", "dividend_amount",
    ):
        val = position.get(cf_key)
        if val is not None:
            safe[cf_key] = val

    # Status indicator
    identity_status = position.get("identity_verification_status", "")
    if identity_status:
        safe["identity_verification_status"] = identity_status
    else:
        valuation_type = position.get("valuation_type", "")
        if valuation_type in BLOCKED_VALUATION_TYPES:
            safe["identity_verification_status"] = "valuation_blocked"

    safe["next_step"] = "verify code or provide holdings snapshot"

    # Mark as sanitized
    safe["_sanitized"] = True
    safe["_sanitization_reason"] = "identity_blocked" if is_identity_blocked(position) else "valuation_blocked"

    return safe


def sanitize_position_for_agent_context(position: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a position for agent context visibility.

    When identity is blocked:
    - fund_code → show as "unverified_candidate" (no actual code)
    - estimated_units, latest_nav → counts only, no values
    - No NAV trend signals
    - No per-fund NAV coverage table

    When identity is verified but valuation is partial:
    - fund_code → allowed
    - estimated_units → allowed if lot coverage sufficient
    - latest_nav → allowed as diagnostic
    """
    if not is_identity_blocked(position):
        # Identity verified — allow code and most fields
        result = _copy_safe_fields(position)
        if is_valuation_blocked(position):
            # Still block P&L and return fields
            result = _remove_valuation_fields(result)
        return result

    # Identity blocked — show counts only, no actual codes or values
    safe: dict[str, Any] = {}

    raw_name = position.get("fund_name") or position.get("raw_fund_name", "")
    if raw_name:
        safe["raw_fund_name"] = raw_name

    # Show candidate code indicator but NOT the actual code
    candidate_code = position.get("fund_code")
    if candidate_code:
        safe["has_candidate_code"] = True
        # Do NOT include the actual candidate code

    # Counts only
    for count_key in (
        "buy_count", "sell_count", "conversion_count",
        "total_transaction_count", "transaction_count",
    ):
        val = position.get(count_key)
        if val is not None:
            safe[count_key] = val

    # Cashflow costs are safe
    for cf_key in (
        "total_cost", "gross_buy", "gross_sell",
        "net_cashflow", "dividend_amount",
    ):
        val = position.get(cf_key)
        if val is not None:
            safe[cf_key] = val

    identity_status = position.get("identity_verification_status", "")
    if identity_status:
        safe["identity_verification_status"] = identity_status

    safe["_sanitized"] = True
    safe["_sanitization_reason"] = "identity_blocked"

    return safe


def sanitize_position_for_debug(position: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a position for debug/diagnostic visibility.

    Debug output includes all fields including candidate codes and
    estimated values. This is only for local_reports/ artifacts
    that are never committed.
    """
    result = dict(position)
    result["_visibility"] = "private_debug"
    return result


def compute_blocked_evidence_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute blocked evidence summary from a list of positions.

    Returns counts of blocked fields and reason codes for agent context.
    """
    candidate_code_count = 0
    estimated_units_blocked_count = 0
    latest_nav_blocked_count = 0
    nav_trend_blocked = False
    reasons: list[str] = []

    for pos in positions:
        identity_blocked = is_identity_blocked(pos)
        valuation_blocked = is_valuation_blocked(pos)

        if identity_blocked and pos.get("fund_code"):
            candidate_code_count += 1

        if identity_blocked or valuation_blocked:
            if pos.get("estimated_units") is not None or pos.get("shares") is not None:
                estimated_units_blocked_count += 1
            if pos.get("latest_nav") is not None or pos.get("nav") is not None:
                latest_nav_blocked_count += 1
            nav_trend_blocked = True

    # Determine reason
    has_identity_unverified = any(
        pos.get("identity_verification_status") in BLOCKED_IDENTITY_STATUSES
        for pos in positions
    )
    has_no_holdings = any(
        pos.get("valuation_type") in ("cashflow_only", "none")
        for pos in positions
    )

    if has_identity_unverified:
        reasons.append("identity_unverified")
    if has_no_holdings:
        reasons.append("no_holdings_snapshot")

    return {
        "candidate_code_count": candidate_code_count,
        "estimated_units_blocked_count": estimated_units_blocked_count,
        "latest_nav_blocked_count": latest_nav_blocked_count,
        "nav_trend_blocked": nav_trend_blocked,
        "reasons": reasons,
    }


def validate_verified_by_user(override_record: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate that a verified_by_user override has all required fields.

    M7.6: verified_by_user:true is NOT an unlock switch. It requires:
    - fund_code: valid 6-digit code
    - fund_name: present
    - verification_source: in allowed set
    - verified_at: present (ISO date)

    Returns (is_valid, list_of_missing_fields).
    """
    missing: list[str] = []

    fund_code = str(override_record.get("fund_code", ""))
    if not fund_code or len(fund_code) != 6 or not fund_code.isdigit():
        missing.append("fund_code (6-digit)")

    fund_name = override_record.get("fund_name") or override_record.get("raw_name", "")
    if not fund_name:
        missing.append("fund_name")

    verification_source = override_record.get("verification_source", "")
    if not verification_source or verification_source not in ALLOWED_VERIFICATION_SOURCES:
        missing.append(f"verification_source (must be one of: {', '.join(sorted(ALLOWED_VERIFICATION_SOURCES))})")

    verified_at = override_record.get("verified_at", "")
    if not verified_at:
        missing.append("verified_at")

    return len(missing) == 0, missing


def should_downgrade_verified_by_user(override_record: dict[str, Any]) -> bool:
    """Check if a verified_by_user override should be downgraded to unverified.

    M7.6: If verification_source or verified_at is missing, the override
    is downgraded to manual_override_unverified regardless of the
    verified_by_user flag.
    """
    if not override_record.get("verified_by_user", False):
        return False  # Not claimed as verified — no downgrade needed

    is_valid, _ = validate_verified_by_user(override_record)
    return not is_valid


# ── Internal helpers ──────────────────────────────────────────────────────

# Fields that are always safe to include (identity-independent)
_SAFE_FIELDS = frozenset({
    "fund_code", "fund_name", "raw_fund_name",
    "buy_count", "sell_count", "conversion_count",
    "total_transaction_count", "transaction_count",
    "total_cost", "gross_buy", "gross_sell",
    "net_cashflow", "dividend_amount",
    "identity_verification_status", "valuation_type",
    "data_quality",
})

# Fields that require identity verification
_IDENTITY_DEPENDENT_FIELDS = frozenset({
    "estimated_units", "shares", "latest_nav", "nav", "nav_date",
    "nav_coverage", "avg_cost", "nav_vs_avg_cost",
    "current_value", "unrealized_pnl", "return_pct",
    "pnl_pct", "total_return", "trend_signal",
})


def _copy_safe_fields(position: dict[str, Any]) -> dict[str, Any]:
    """Copy position with only safe fields preserved."""
    result: dict[str, Any] = {}
    for key, value in position.items():
        if key in _SAFE_FIELDS or key in _IDENTITY_DEPENDENT_FIELDS:
            result[key] = value
    return result


def _remove_valuation_fields(position: dict[str, Any]) -> dict[str, Any]:
    """Remove valuation-dependent fields (P&L, return) from a position dict."""
    result = dict(position)
    for field in ("current_value", "unrealized_pnl", "return_pct", "pnl_pct", "total_return"):
        result.pop(field, None)
    return result
