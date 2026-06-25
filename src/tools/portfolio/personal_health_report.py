"""Personal portfolio health summary builder.

Aggregates existing E2E pipeline outputs into a single structured health report.
No new business calculations — only counts, status labels, and data-quality
next steps. No private data in output.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "personal_health_report.v1"

# ── Reason codes ──────────────────────────────────────────────────────
REASON_NO_VALID_FUND_CODES = "no_valid_fund_codes"
REASON_NAV_MISSING = "nav_missing"
REASON_PARTIAL_NAV_COVERAGE = "partial_nav_coverage"
REASON_MANUAL_REVIEW_TRANSACTIONS = "manual_review_transactions"
REASON_STALE_NAV = "stale_nav"
REASON_QDII_NAV_LAG = "qdii_nav_lag"
REASON_FALLBACK_HOLDINGS_USED = "fallback_holdings_used"
REASON_CASHFLOW_ONLY = "cashflow_only"
REASON_ESTIMATED_ONLY = "estimated_only"
REASON_NAME_ONLY_FUNDS = "name_only_funds"
REASON_IDENTITY_MISMATCH = "identity_mismatch"
REASON_REDEMPTION_FEE_UNKNOWN = "redemption_fee_unknown"

VALID_REASON_CODES = frozenset({
    REASON_NO_VALID_FUND_CODES,
    REASON_NAV_MISSING,
    REASON_PARTIAL_NAV_COVERAGE,
    REASON_MANUAL_REVIEW_TRANSACTIONS,
    REASON_STALE_NAV,
    REASON_QDII_NAV_LAG,
    REASON_FALLBACK_HOLDINGS_USED,
    REASON_CASHFLOW_ONLY,
    REASON_ESTIMATED_ONLY,
    REASON_NAME_ONLY_FUNDS,
    REASON_IDENTITY_MISMATCH,
    REASON_REDEMPTION_FEE_UNKNOWN,
})

# ── Status / confidence enums ─────────────────────────────────────────
VALID_OVERALL_STATUSES = frozenset({"ok", "partial", "needs_data", "needs_manual_review", "unavailable"})
VALID_CONFIDENCE_LEVELS = frozenset({"high", "medium", "low", "unavailable"})

# ── Safety notes (always included) ────────────────────────────────────
_SAFETY_NOTES = [
    "This is not a formal investment decision — no BUY/SELL/HOLD instruction.",
    "No broker/order execution capability.",
    "No auto trading.",
    "Estimated values are not confirmed market values.",
    "Partial coverage means incomplete valuation.",
]


def build_personal_health_summary(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    """Build a personal portfolio health summary from E2E pipeline artifacts.

    Args:
        artifacts: Mapping of pipeline artifact names to their data.
            Expected keys (all optional):
            - e2e_summary: E2E summary dict
            - portfolio_summary: Portfolio summary dict
            - nav_coverage_summary: NAV coverage summary dict
            - portfolio_input_transactions_summary: Transaction stats dict
            - identity_summary: Identity resolution summary dict
            - reconstruction_summary: Reconstruction status dict
            - valuation_summary: Valuation type counts dict

    Returns:
        Personal health report dict with schema_version, overall_status,
        confidence_level, reason_codes, data_sources, valuation_quality,
        nav_coverage, fix_it_checklist, and safety_notes.
    """
    e2e = _as_dict(artifacts.get("e2e_summary"))
    portfolio = _as_dict(artifacts.get("portfolio_summary"))
    nav_coverage = _as_dict(artifacts.get("nav_coverage_summary"))
    txn_stats = _as_dict(artifacts.get("portfolio_input_transactions_summary"))
    identity = _as_dict(artifacts.get("identity_summary"))
    valuation = _as_dict(artifacts.get("valuation_summary"))

    # ── Data sources ──────────────────────────────────────────────────
    transaction_source = str(e2e.get("transaction_source", "none"))
    valuation_source = str(e2e.get("portfolio_input_source", "unavailable"))
    identity_source = _determine_identity_source(identity, e2e)

    data_sources = {
        "transaction_source": transaction_source,
        "valuation_source": valuation_source,
        "identity_source": identity_source,
    }

    # ── Reason codes ──────────────────────────────────────────────────
    reason_codes: list[str] = []

    valid_fund_codes_count = int(e2e.get("pipeline_steps", {}).get("valid_fund_codes_count", 0))
    name_only_count = int(e2e.get("pipeline_steps", {}).get("name_only_count", 0))
    if identity.get("name_only_count"):
        name_only_count = max(name_only_count, int(identity["name_only_count"]))

    if valid_fund_codes_count == 0:
        reason_codes.append(REASON_NO_VALID_FUND_CODES)

    if name_only_count > 0:
        reason_codes.append(REASON_NAME_ONLY_FUNDS)

    # Identity mismatch
    identity_mismatch_count = int(identity.get("identity_mismatch_count", 0))
    if identity_mismatch_count > 0:
        reason_codes.append(REASON_IDENTITY_MISMATCH)

    # Redemption fee unknown
    redemption_fee_unknown_count = int(valuation.get("redemption_fee_unknown_count", 0))
    if redemption_fee_unknown_count == 0:
        redemption_fee_unknown_count = int(nav_coverage.get("positions_redemption_fee_unknown", 0))
    if redemption_fee_unknown_count > 0:
        reason_codes.append(REASON_REDEMPTION_FEE_UNKNOWN)

    # NAV availability
    reconstruction_status = str(e2e.get("pipeline_steps", {}).get("reconstruction_status", ""))
    if reconstruction_status == "nav_unavailable":
        reason_codes.append(REASON_NAV_MISSING)

    # NAV coverage from nav_coverage_summary
    nav_partial = int(nav_coverage.get("nav_coverage_partial_count", 0))
    nav_none = int(nav_coverage.get("nav_coverage_none_count", 0))
    nav_full = int(nav_coverage.get("nav_coverage_full_count", 0))
    stale_count = int(nav_coverage.get("latest_nav_stale_count", 0))
    qdii_like_count = int(nav_coverage.get("qdii_like_count", 0))

    if nav_partial > 0:
        reason_codes.append(REASON_PARTIAL_NAV_COVERAGE)

    if stale_count > 0:
        reason_codes.append(REASON_STALE_NAV)

    if qdii_like_count > 0 and stale_count > 0:
        reason_codes.append(REASON_QDII_NAV_LAG)

    # Manual review transactions
    manual_review_count = int(txn_stats.get("manual_review_required_count", 0))
    if manual_review_count == 0:
        manual_review_count = int(txn_stats.get("manual_review_count", 0))
    if manual_review_count > 0:
        reason_codes.append(REASON_MANUAL_REVIEW_TRANSACTIONS)

    # Fallback holdings
    if valuation_source == "existing_private_portfolio_input":
        reason_codes.append(REASON_FALLBACK_HOLDINGS_USED)

    # Cashflow-only positions
    cashflow_only_count = int(nav_coverage.get("positions_cashflow_only", 0))
    if cashflow_only_count == 0 and valuation:
        cashflow_only_count = int(valuation.get("cashflow_only", 0))
    if cashflow_only_count > 0:
        reason_codes.append(REASON_CASHFLOW_ONLY)

    # Estimated-only: only flag when all positions are estimated AND there are
    # no full-NAV-coverage positions (i.e., estimated without full coverage).
    # Normal reconstructed portfolios are all "estimated" — that's expected.
    positions_estimated = int(nav_coverage.get("positions_estimated", 0))
    positions_total = int(nav_coverage.get("positions_total", 0))
    confirmed_count = 0
    if (
        positions_total > 0
        and positions_estimated == positions_total
        and confirmed_count == 0
        and nav_full == 0
    ):
        reason_codes.append(REASON_ESTIMATED_ONLY)

    # Deduplicate reason codes while preserving order
    seen: set[str] = set()
    unique_reasons: list[str] = []
    for code in reason_codes:
        if code not in seen:
            seen.add(code)
            unique_reasons.append(code)

    # ── Valuation quality ─────────────────────────────────────────────
    estimated_full = int(nav_coverage.get("nav_coverage_full_count", 0))
    estimated_partial = nav_partial
    unavailable_count = nav_none
    manual_review_positions = int(nav_coverage.get("positions_manual_review_required", 0))

    # Override from valuation_summary if available
    if valuation:
        estimated_full = max(estimated_full, int(valuation.get("estimated_full_coverage", 0)))
        estimated_partial = max(estimated_partial, int(valuation.get("estimated_partial_coverage", 0)))
        cashflow_only_count = max(cashflow_only_count, int(valuation.get("cashflow_only", 0)))
        unavailable_count = max(unavailable_count, int(valuation.get("unavailable", 0)))
        manual_review_positions = max(manual_review_positions, int(valuation.get("manual_review_required", 0)))

    valuation_quality = {
        "positions_total": positions_total,
        "confirmed_count": confirmed_count,
        "estimated_full_coverage_count": estimated_full,
        "estimated_partial_coverage_count": estimated_partial,
        "cashflow_only_count": cashflow_only_count,
        "unavailable_count": unavailable_count,
        "manual_review_count": manual_review_positions,
        "estimated_current_value_total_is_partial": bool(
            nav_coverage.get("estimated_current_value_total_is_partial", False)
        ),
    }

    # ── NAV coverage summary ──────────────────────────────────────────
    nav_coverage_result = {
        "full": nav_full,
        "partial": nav_partial,
        "none": nav_none,
        "latest_only": int(nav_coverage.get("nav_coverage_latest_only_count", 0)),
        "stale_count": stale_count,
        "qdii_like_count": qdii_like_count,
    }

    # ── Overall status ────────────────────────────────────────────────
    overall_status = _determine_overall_status(
        transaction_source=transaction_source,
        valuation_source=valuation_source,
        valid_fund_codes_count=valid_fund_codes_count,
        name_only_count=name_only_count,
        manual_review_count=manual_review_count,
        nav_none=nav_none,
        positions_total=positions_total,
        reason_codes=unique_reasons,
    )

    # ── Confidence level ──────────────────────────────────────────────
    confidence_level = _determine_confidence_level(
        overall_status=overall_status,
        nav_full=nav_full,
        nav_partial=nav_partial,
        valuation_source=valuation_source,
        name_only_count=name_only_count,
        positions_total=positions_total,
    )

    # ── Fix-it checklist ──────────────────────────────────────────────
    checklist = _build_checklist(
        name_only_count=name_only_count,
        nav_missing=REASON_NAV_MISSING in unique_reasons,
        nav_partial=nav_partial,
        manual_review_count=manual_review_count,
        stale_count=stale_count,
        qdii_like_count=qdii_like_count,
        unavailable_count=unavailable_count,
        cashflow_only_count=cashflow_only_count,
        positions_total=positions_total,
        valuation_source=valuation_source,
        identity_mismatch_count=identity_mismatch_count,
        redemption_fee_unknown_count=redemption_fee_unknown_count,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall_status,
        "confidence_level": confidence_level,
        "reason_codes": unique_reasons,
        "data_sources": data_sources,
        "valuation_quality": valuation_quality,
        "nav_coverage": nav_coverage_result,
        "fix_it_checklist": checklist,
        "safety_notes": list(_SAFETY_NOTES),
    }


# ── Internal helpers ──────────────────────────────────────────────────


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _determine_identity_source(identity: dict[str, Any], e2e: dict[str, Any]) -> str:
    """Determine identity resolution source label."""
    # Check if overrides were used (from identity resolution data)
    override_warnings = identity.get("override_validation_warnings")
    if override_warnings is not None:
        # Overrides file existed (even if it had warnings)
        return "overrides"

    # Check if manual overrides were used (from identity resolution summary)
    if identity.get("manual_overrides_used") or int(identity.get("manual_override_matches_count", 0)) > 0:
        return "manual_override"

    valid_codes = int(e2e.get("pipeline_steps", {}).get("valid_fund_codes_count", 0))
    name_only = int(e2e.get("pipeline_steps", {}).get("name_only_count", 0))

    if valid_codes > 0 and name_only == 0:
        return "direct_fund_code"
    if name_only > 0:
        return "name_only"
    return "unavailable"


def _determine_overall_status(
    *,
    transaction_source: str,
    valuation_source: str,
    valid_fund_codes_count: int,
    name_only_count: int,
    manual_review_count: int,
    nav_none: int,
    positions_total: int,
    reason_codes: list[str],
) -> str:
    """Determine overall health status based on pipeline state."""
    # Priority: unavailable > needs_manual_review > needs_data > partial > ok

    if transaction_source == "none" and valuation_source == "unavailable":
        return "unavailable"

    if manual_review_count > 0:
        return "needs_manual_review"

    if valid_fund_codes_count == 0:
        return "needs_data"

    if REASON_NAV_MISSING in reason_codes:
        return "needs_data"

    # Has some data but not complete
    if reason_codes:
        return "partial"

    # All clear
    if positions_total > 0 and nav_none == 0:
        return "ok"

    if positions_total == 0:
        return "needs_data"

    return "partial"


def _determine_confidence_level(
    *,
    overall_status: str,
    nav_full: int,
    nav_partial: int,
    valuation_source: str,
    name_only_count: int,
    positions_total: int,
) -> str:
    """Determine confidence level based on data completeness."""
    if overall_status == "unavailable":
        return "unavailable"

    if overall_status == "needs_data" and positions_total == 0:
        return "unavailable"

    if overall_status == "needs_data":
        return "low"

    if overall_status == "needs_manual_review":
        return "low"

    # Has data
    if nav_full > 0 and nav_partial == 0 and name_only_count == 0:
        if valuation_source == "reconstructed_from_ledger":
            return "high"
        # Fallback holdings or derived — medium at best
        return "medium"

    if nav_partial > 0 or name_only_count > 0:
        return "medium"

    if nav_full > 0:
        return "high"

    return "low"


def _build_checklist(
    *,
    name_only_count: int,
    nav_missing: bool,
    nav_partial: int,
    manual_review_count: int,
    stale_count: int,
    qdii_like_count: int,
    unavailable_count: int,
    cashflow_only_count: int,
    positions_total: int,
    valuation_source: str,
    identity_mismatch_count: int = 0,
    redemption_fee_unknown_count: int = 0,
) -> list[str]:
    """Build fix-it checklist from data quality diagnostics."""
    items: list[str] = []

    if identity_mismatch_count > 0:
        items.append(f"Verify fund_identity_overrides for {identity_mismatch_count} fund(s) with code/name mismatch")

    if redemption_fee_unknown_count > 0:
        items.append(f"Provide fee_overrides for {redemption_fee_unknown_count} fund(s) with unknown redemption fees")

    if name_only_count > 0:
        items.append(f"Add fund_identity_overrides for {name_only_count} name-only fund(s)")

    if nav_missing:
        items.append("NAV data is missing; provide nav_overrides or ensure provider access")
    elif nav_partial > 0:
        items.append(f"Add trade-date NAV overrides for {nav_partial} fund(s) with missing coverage")

    if manual_review_count > 0:
        items.append(f"Review {manual_review_count} conversion/refund/unknown transaction(s)")

    if stale_count > 0:
        items.append(f"Check NAV freshness for {stale_count} fund(s) with stale NAV")

    if qdii_like_count > 0 and stale_count > 0:
        items.append(
            f"Check NAV freshness for {min(qdii_like_count, stale_count)} QDII-like fund(s) with potentially lagged NAV"
        )

    if unavailable_count > 0 or (positions_total == 0 and valuation_source == "unavailable"):
        if unavailable_count > 0:
            items.append(f"Provide portfolio_input.holdings for {unavailable_count} position(s) without valuation")
        else:
            items.append("Provide portfolio_input.holdings if valuation is unavailable")

    if cashflow_only_count > 0:
        items.append(f"Add explicit units for {cashflow_only_count} cashflow-only transaction(s) if available")

    return items
