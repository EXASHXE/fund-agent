"""Valuation source model — M7.9 transaction-derived holdings reconstruction.

Defines the canonical enumerations for holdings_source, valuation_source,
and profit_source, along with the rules for which combinations are valid
and how they interact with position_valuation_status.

Key design:
- holdings snapshot → platform_reported_snapshot + platform_reported_current_value
- transaction-derived full reconstruction → transaction_derived_full + reconstructed_units_latest_nav
- transaction-derived partial → transaction_derived_partial (no current_value)
- cashflow only → cashflow_only (no current_value)
- unavailable → no valuation possible
"""
from __future__ import annotations

from typing import Any


# ── Holdings source enumeration ─────────────────────────────────────────

HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT = "platform_reported_snapshot"
HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL = "transaction_derived_full"
HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL = "transaction_derived_partial"
HOLDINGS_SOURCE_CASHFLOW_ONLY = "cashflow_only"
HOLDINGS_SOURCE_UNAVAILABLE = "unavailable"

VALID_HOLDINGS_SOURCES = frozenset({
    HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT,
    HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL,
    HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL,
    HOLDINGS_SOURCE_CASHFLOW_ONLY,
    HOLDINGS_SOURCE_UNAVAILABLE,
})


# ── Valuation source enumeration ────────────────────────────────────────

VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE = "platform_reported_current_value"
VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV = "reconstructed_units_latest_nav"
VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS = "partial_reconstructed_units"
VALUATION_SOURCE_UNAVAILABLE = "unavailable"

# Legacy aliases (still used by existing code, mapped to new values)
LEGACY_VALUATION_SOURCE_MAP = {
    "authoritative_holdings_snapshot": VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE,
    "platform_reported_current_value": VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE,
    "estimated_from_transactions_and_nav": VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV,
    "cashflow_only": VALUATION_SOURCE_UNAVAILABLE,
    "identity_unverified_blocked": VALUATION_SOURCE_UNAVAILABLE,
    "identity_mismatch_blocked": VALUATION_SOURCE_UNAVAILABLE,
    "partial_lot_coverage_blocked": VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS,
    "missing_units_blocked": VALUATION_SOURCE_UNAVAILABLE,
    "manual_review_required": VALUATION_SOURCE_UNAVAILABLE,
    "none": VALUATION_SOURCE_UNAVAILABLE,
    "holdings_snapshot_no_valuation": VALUATION_SOURCE_UNAVAILABLE,
}

VALID_VALUATION_SOURCES = frozenset({
    VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE,
    VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV,
    VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS,
    VALUATION_SOURCE_UNAVAILABLE,
})


# ── Profit source enumeration ───────────────────────────────────────────

PROFIT_SOURCE_PLATFORM_REPORTED_PROFIT = "platform_reported_profit"
PROFIT_SOURCE_RECONSTRUCTED_CASHFLOW_COST = "reconstructed_cashflow_cost"
PROFIT_SOURCE_UNAVAILABLE = "unavailable"

VALID_PROFIT_SOURCES = frozenset({
    PROFIT_SOURCE_PLATFORM_REPORTED_PROFIT,
    PROFIT_SOURCE_RECONSTRUCTED_CASHFLOW_COST,
    PROFIT_SOURCE_UNAVAILABLE,
})


# ── Position valuation status (M7.9 extended) ──────────────────────────

POSITION_VALUATION_CONFIRMED = "confirmed"
POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_FULL = "reconstructed_estimated_full"
POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_PARTIAL = "reconstructed_estimated_partial"
POSITION_VALUATION_CASHFLOW_ONLY = "cashflow_only"
POSITION_VALUATION_BLOCKED_IDENTITY = "blocked_identity"
POSITION_VALUATION_BLOCKED_MISSING_NAV = "blocked_missing_nav"
POSITION_VALUATION_BLOCKED_MANUAL_REVIEW = "blocked_manual_review"

# Legacy aliases
LEGACY_POSITION_VALUATION_MAP = {
    "estimated_full_lot_coverage": POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_FULL,
    "estimated_partial_lot_coverage": POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_PARTIAL,
    "blocked_missing_units": POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_PARTIAL,
    "blocked_missing_trade_nav": POSITION_VALUATION_BLOCKED_MISSING_NAV,
    "holdings_snapshot_valued": POSITION_VALUATION_CONFIRMED,
}

VALID_POSITION_VALUATION_STATUSES = frozenset({
    POSITION_VALUATION_CONFIRMED,
    POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_FULL,
    POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_PARTIAL,
    POSITION_VALUATION_CASHFLOW_ONLY,
    POSITION_VALUATION_BLOCKED_IDENTITY,
    POSITION_VALUATION_BLOCKED_MISSING_NAV,
    POSITION_VALUATION_BLOCKED_MANUAL_REVIEW,
})


# ── Portfolio valuation status (M7.9) ───────────────────────────────────

PORTFOLIO_VALUATION_PLATFORM_SNAPSHOT_FULL = "platform_snapshot_full"
PORTFOLIO_VALUATION_TRANSACTION_DERIVED_FULL = "transaction_derived_full"
PORTFOLIO_VALUATION_TRANSACTION_DERIVED_PARTIAL = "transaction_derived_partial"
PORTFOLIO_VALUATION_UNAVAILABLE = "unavailable"

# Legacy aliases
LEGACY_PORTFOLIO_VALUATION_MAP = {
    "estimated_full_coverage": PORTFOLIO_VALUATION_TRANSACTION_DERIVED_FULL,
    "partial_diagnostic_only": PORTFOLIO_VALUATION_TRANSACTION_DERIVED_PARTIAL,
    "confirmed": PORTFOLIO_VALUATION_PLATFORM_SNAPSHOT_FULL,
}

VALID_PORTFOLIO_VALUATION_STATUSES = frozenset({
    PORTFOLIO_VALUATION_PLATFORM_SNAPSHOT_FULL,
    PORTFOLIO_VALUATION_TRANSACTION_DERIVED_FULL,
    PORTFOLIO_VALUATION_TRANSACTION_DERIVED_PARTIAL,
    PORTFOLIO_VALUATION_UNAVAILABLE,
})


# ── Reconstruction quality levels ───────────────────────────────────────

RECONSTRUCTION_QUALITY_CONFIRMED = "confirmed"
RECONSTRUCTION_QUALITY_ESTIMATED_HIGH = "estimated_high"
RECONSTRUCTION_QUALITY_ESTIMATED_MEDIUM = "estimated_medium"
RECONSTRUCTION_QUALITY_ESTIMATED_LOW = "estimated_low"
RECONSTRUCTION_QUALITY_PARTIAL = "partial"
RECONSTRUCTION_QUALITY_BLOCKED = "blocked"

VALID_RECONSTRUCTION_QUALITIES = frozenset({
    RECONSTRUCTION_QUALITY_CONFIRMED,
    RECONSTRUCTION_QUALITY_ESTIMATED_HIGH,
    RECONSTRUCTION_QUALITY_ESTIMATED_MEDIUM,
    RECONSTRUCTION_QUALITY_ESTIMATED_LOW,
    RECONSTRUCTION_QUALITY_PARTIAL,
    RECONSTRUCTION_QUALITY_BLOCKED,
})


# ── Reconstruction blockers ─────────────────────────────────────────────

RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED = "identity_unverified"
RECONSTRUCTION_BLOCKER_CODE_NAME_MISMATCH = "code_name_mismatch"
RECONSTRUCTION_BLOCKER_MISSING_TRADE_NAV = "missing_trade_nav"
RECONSTRUCTION_BLOCKER_MISSING_FEE = "missing_fee"
RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS = "unknown_amount_semantics"
RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND = "unmatched_refund"
RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED = "conversion_unverified"
RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED = "dividend_unmodeled"
RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS = "negative_units"
RECONSTRUCTION_BLOCKER_QDII_NAV_LAG = "qdii_nav_lag"

VALID_RECONSTRUCTION_BLOCKERS = frozenset({
    RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_CODE_NAME_MISMATCH,
    RECONSTRUCTION_BLOCKER_MISSING_TRADE_NAV,
    RECONSTRUCTION_BLOCKER_MISSING_FEE,
    RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS,
    RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND,
    RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED,
    RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS,
    RECONSTRUCTION_BLOCKER_QDII_NAV_LAG,
})

BLOCKER_SEVERITY_BLOCK = "blocker"
BLOCKER_SEVERITY_DEGRADE = "degrade"

# Blockers that completely prevent valuation
_BLOCK_SEVERITY_BLOCKERS = frozenset({
    RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_CODE_NAME_MISMATCH,
    RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS,
    RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND,
    RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED,
})

# Blockers that degrade quality but don't block entirely
_BLOCK_SEVERITY_DEGRADE = frozenset({
    RECONSTRUCTION_BLOCKER_MISSING_TRADE_NAV,
    RECONSTRUCTION_BLOCKER_MISSING_FEE,
    RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS,
    RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED,
    RECONSTRUCTION_BLOCKER_QDII_NAV_LAG,
})


def get_blocker_severity(blocker: str) -> str:
    """Return the severity level for a reconstruction blocker."""
    if blocker in _BLOCK_SEVERITY_BLOCKERS:
        return BLOCKER_SEVERITY_BLOCK
    if blocker in _BLOCK_SEVERITY_DEGRADE:
        return BLOCKER_SEVERITY_DEGRADE
    return BLOCKER_SEVERITY_DEGRADE  # unknown blockers default to degrade


# ── Holdings source → valuation source rules ────────────────────────────

def compute_valuation_source_from_holdings(
    holdings_source: str,
    has_units: bool,
    has_latest_nav: bool,
    has_current_value_from_snapshot: bool = False,
) -> str:
    """Compute valuation_source from holdings_source and available data.

    Rules:
    1. holdings snapshot provides current_value:
       holdings_source = platform_reported_snapshot
       valuation_source = platform_reported_current_value

    2. transaction-derived full + latest NAV:
       holdings_source = transaction_derived_full
       valuation_source = reconstructed_units_latest_nav

    3. transaction-derived partial:
       holdings_source = transaction_derived_partial
       valuation_source = partial_reconstructed_units

    4. cashflow only:
       holdings_source = cashflow_only
       valuation_source = unavailable
    """
    if holdings_source == HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT:
        if has_current_value_from_snapshot:
            return VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE
        if has_units and has_latest_nav:
            return VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE
        return VALUATION_SOURCE_UNAVAILABLE

    if holdings_source == HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL:
        if has_units and has_latest_nav:
            return VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV
        if has_units:
            return VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS
        return VALUATION_SOURCE_UNAVAILABLE

    if holdings_source == HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL:
        return VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS

    if holdings_source == HOLDINGS_SOURCE_CASHFLOW_ONLY:
        return VALUATION_SOURCE_UNAVAILABLE

    return VALUATION_SOURCE_UNAVAILABLE


def compute_holdings_source(
    has_snapshot: bool,
    units_coverage_ratio: float | None,
    has_units: bool,
    has_cost: bool,
    blockers: list[str] | None = None,
) -> str:
    """Compute holdings_source from available data.

    Rules:
    1. Snapshot available → platform_reported_snapshot
    2. Full units coverage (ratio == 1.0) and no blockers → transaction_derived_full
    3. Partial units coverage → transaction_derived_partial
    4. Only cost/cashflow → cashflow_only
    5. Nothing → unavailable
    """
    if has_snapshot:
        return HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT

    # Check for blocking severity blockers
    has_blocking = any(
        get_blocker_severity(b) == BLOCKER_SEVERITY_BLOCK
        for b in (blockers or [])
    )

    if has_units and not has_blocking:
        if units_coverage_ratio is not None and units_coverage_ratio >= 1.0:
            return HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL
        if units_coverage_ratio is not None and units_coverage_ratio > 0:
            return HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL
        # has_units but no coverage info — assume partial
        return HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL

    if has_cost:
        return HOLDINGS_SOURCE_CASHFLOW_ONLY

    return HOLDINGS_SOURCE_UNAVAILABLE


def compute_profit_source(
    has_platform_reported_profit: bool,
    holdings_source: str,
) -> str:
    """Compute profit_source from available data.

    Rules:
    1. Platform reported profit available → platform_reported_profit
    2. Transaction-derived with cost basis → reconstructed_cashflow_cost
    3. Otherwise → unavailable
    """
    if has_platform_reported_profit:
        return PROFIT_SOURCE_PLATFORM_REPORTED_PROFIT

    if holdings_source in (
        HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL,
        HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL,
    ):
        return PROFIT_SOURCE_RECONSTRUCTED_CASHFLOW_COST

    return PROFIT_SOURCE_UNAVAILABLE


def compute_reconstruction_quality(
    lot_statuses: list[str],
    blockers: list[str],
    units_coverage_ratio: float,
    identity_status: str,
) -> str:
    """Compute reconstruction quality from lot statuses and blockers.

    Returns one of: confirmed, estimated_high, estimated_medium, estimated_low,
    partial, blocked.
    """
    # Identity blocks
    if identity_status in ("code_name_mismatch", "manual_override_unverified",
                           "provider_lookup_failed", "name_only", "invalid_code"):
        return RECONSTRUCTION_QUALITY_BLOCKED

    # Blocking severity blockers
    if any(get_blocker_severity(b) == BLOCKER_SEVERITY_BLOCK for b in blockers):
        return RECONSTRUCTION_QUALITY_BLOCKED

    if not lot_statuses:
        return RECONSTRUCTION_QUALITY_BLOCKED

    confirmed = sum(1 for s in lot_statuses if s == "confirmed")
    estimated = sum(1 for s in lot_statuses if s == "estimated")
    blocked = sum(1 for s in lot_statuses if s.startswith("blocked_"))
    total = len(lot_statuses)

    if blocked > 0 and confirmed + estimated == 0:
        return RECONSTRUCTION_QUALITY_BLOCKED

    # Degrade blockers affect quality level
    degrade_count = sum(
        1 for b in blockers
        if get_blocker_severity(b) == BLOCKER_SEVERITY_DEGRADE
    )

    if units_coverage_ratio < 1.0:
        return RECONSTRUCTION_QUALITY_PARTIAL

    # Full coverage
    if confirmed == total and degrade_count == 0:
        return RECONSTRUCTION_QUALITY_CONFIRMED

    if degrade_count == 0 and estimated <= total * 0.3:
        return RECONSTRUCTION_QUALITY_ESTIMATED_HIGH

    if degrade_count <= 1:
        return RECONSTRUCTION_QUALITY_ESTIMATED_MEDIUM

    return RECONSTRUCTION_QUALITY_ESTIMATED_LOW


def can_output_current_value(
    identity_status: str,
    total_units: float | None,
    latest_nav: float | None,
    units_coverage_ratio: float | None,
    blockers: list[str],
    reconstruction_quality: str,
) -> bool:
    """Check if current_value can be output for a position.

    Allowed when:
    1. identity provider_verified or valid user_verified_override
    2. total_units > 0
    3. latest_nav exists
    4. units_coverage_ratio == 1.0
    5. no blocker with severity=blocker
    6. reconstruction_quality not partial/blocked
    """
    # Identity gate
    if identity_status in ("code_name_mismatch", "manual_override_unverified",
                           "provider_lookup_failed", "name_only", "invalid_code"):
        return False

    # Units and NAV
    if total_units is None or total_units <= 0:
        return False
    if latest_nav is None:
        return False

    # Coverage
    if units_coverage_ratio is not None and units_coverage_ratio < 1.0:
        return False

    # Blockers
    if any(get_blocker_severity(b) == BLOCKER_SEVERITY_BLOCK for b in blockers):
        return False

    # Quality gate
    if reconstruction_quality in (RECONSTRUCTION_QUALITY_PARTIAL, RECONSTRUCTION_QUALITY_BLOCKED):
        return False

    return True


def is_valuation_estimated(valuation_source: str) -> bool:
    """Check if a valuation source represents a transaction-derived estimate.

    Transaction-derived estimates must be labeled as estimated,
    never as platform_reported.
    """
    return valuation_source in (
        VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV,
        VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS,
    )


def map_legacy_valuation_source(legacy_source: str) -> str:
    """Map a legacy valuation_source string to the M7.9 enumeration."""
    return LEGACY_VALUATION_SOURCE_MAP.get(legacy_source, legacy_source)


def map_legacy_position_valuation_status(legacy_status: str) -> str:
    """Map a legacy position_valuation_status to the M7.9 enumeration."""
    return LEGACY_POSITION_VALUATION_MAP.get(legacy_status, legacy_status)


def map_legacy_portfolio_valuation_status(legacy_status: str) -> str:
    """Map a legacy portfolio_valuation_status to the M7.9 enumeration."""
    return LEGACY_PORTFOLIO_VALUATION_MAP.get(legacy_status, legacy_status)
