"""Pre-valuation readiness gate — M7.20 + M7.21.

Determines whether the portfolio is ready for valuation based on:
- Identity verification completeness
- Current holding discovery status
- Holdings snapshot availability and reconciliation
- Transaction chain completeness
- NAV provider availability

Key rules:
- Identity verified alone does NOT allow full valuation.
- Probable current holdings only allow partial valuation.
- Holdings snapshot allows snapshot-based valuation.
- Snapshot reconciled with no mismatches allows snapshot_reconciled scope.
- No NAV provider blocks transaction-derived full valuation.
- Manual review blocks full valuation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.tools.portfolio.current_holding_discovery import (
    HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_HISTORY_ONLY,
    HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED,
    HoldingDiscoverySummary,
)


# ── Valuation scope enumeration ──────────────────────────────────────────

VALUATION_SCOPE_NONE = "none"
VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY = "current_holdings_snapshot_only"
VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED = "current_holdings_snapshot_reconciled"
VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL = "transaction_derived_partial"
VALUATION_SCOPE_TRANSACTION_DERIVED_FULL = "transaction_derived_full"

VALID_VALUATION_SCOPES = frozenset({
    VALUATION_SCOPE_NONE,
    VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY,
    VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED,
    VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL,
    VALUATION_SCOPE_TRANSACTION_DERIVED_FULL,
})


@dataclass
class PreValuationReadiness:
    """Pre-valuation readiness assessment."""

    identity_verified_all_ledger_funds: bool = False
    current_holding_discovery_available: bool = False
    current_position_confirmed_count: int = 0
    current_position_probable_count: int = 0
    closed_position_probable_count: int = 0
    holdings_snapshot_loaded: bool = False
    holdings_snapshot_reconciled: bool = False
    valuation_ready_position_count: int = 0
    probable_not_in_snapshot_count: int = 0
    snapshot_not_in_probable_count: int = 0
    snapshot_reconciliation_status: str = ""
    transaction_chain_complete: bool = False
    nav_provider_available: bool = False
    valuation_allowed: bool = False
    valuation_scope: str = VALUATION_SCOPE_NONE
    blocking_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_verified_all_ledger_funds": self.identity_verified_all_ledger_funds,
            "current_holding_discovery_available": self.current_holding_discovery_available,
            "current_position_confirmed_count": self.current_position_confirmed_count,
            "current_position_probable_count": self.current_position_probable_count,
            "closed_position_probable_count": self.closed_position_probable_count,
            "holdings_snapshot_loaded": self.holdings_snapshot_loaded,
            "holdings_snapshot_reconciled": self.holdings_snapshot_reconciled,
            "valuation_ready_position_count": self.valuation_ready_position_count,
            "probable_not_in_snapshot_count": self.probable_not_in_snapshot_count,
            "snapshot_not_in_probable_count": self.snapshot_not_in_probable_count,
            "snapshot_reconciliation_status": self.snapshot_reconciliation_status,
            "transaction_chain_complete": self.transaction_chain_complete,
            "nav_provider_available": self.nav_provider_available,
            "valuation_allowed": self.valuation_allowed,
            "valuation_scope": self.valuation_scope,
            "blocking_reasons": self.blocking_reasons,
        }


def assess_valuation_readiness(
    *,
    identity_verified_count: int,
    total_ledger_fund_count: int,
    holding_discovery: HoldingDiscoverySummary | None = None,
    holdings_snapshot_loaded: bool = False,
    holdings_snapshot_reconciled: bool = False,
    valuation_ready_position_count: int = 0,
    probable_not_in_snapshot_count: int = 0,
    snapshot_not_in_probable_count: int = 0,
    snapshot_reconciliation_status: str = "",
    closed_but_in_snapshot_count: int = 0,
    identity_mismatch_count: int = 0,
    transaction_chain_complete: bool = False,
    nav_provider_available: bool = False,
    manual_review_count: int = 0,
) -> PreValuationReadiness:
    """Assess whether the portfolio is ready for valuation.

    Args:
        identity_verified_count: Number of identity-verified funds.
        total_ledger_fund_count: Total funds in the ledger.
        holding_discovery: CurrentHoldingDiscovery summary (if available).
        holdings_snapshot_loaded: Whether a holdings snapshot was loaded.
        holdings_snapshot_reconciled: Whether snapshot was reconciled with holdings.
        valuation_ready_position_count: Positions ready for valuation.
        probable_not_in_snapshot_count: Probable holdings not in snapshot.
        snapshot_not_in_probable_count: Snapshot positions not in probable holdings.
        snapshot_reconciliation_status: Reconciliation status string.
        closed_but_in_snapshot_count: Closed positions that appear in snapshot.
        identity_mismatch_count: Positions with identity mismatch.
        transaction_chain_complete: Whether all transaction chains are complete.
        nav_provider_available: Whether NAV data is available.
        manual_review_count: Number of funds requiring manual review.

    Returns:
        PreValuationReadiness with valuation_allowed and valuation_scope.
    """
    readiness = PreValuationReadiness()
    blocking_reasons: list[str] = []

    # Identity verification check
    identity_verified_all = (
        total_ledger_fund_count > 0
        and identity_verified_count >= total_ledger_fund_count
    )
    readiness.identity_verified_all_ledger_funds = identity_verified_all

    # Current holding discovery
    if holding_discovery is not None:
        readiness.current_holding_discovery_available = True
        readiness.current_position_confirmed_count = holding_discovery.current_position_confirmed_count
        readiness.current_position_probable_count = holding_discovery.current_position_probable_count
        readiness.closed_position_probable_count = holding_discovery.closed_position_probable_count
    else:
        readiness.current_holding_discovery_available = False

    readiness.holdings_snapshot_loaded = holdings_snapshot_loaded
    readiness.holdings_snapshot_reconciled = holdings_snapshot_reconciled
    readiness.valuation_ready_position_count = valuation_ready_position_count
    readiness.probable_not_in_snapshot_count = probable_not_in_snapshot_count
    readiness.snapshot_not_in_probable_count = snapshot_not_in_probable_count
    readiness.snapshot_reconciliation_status = snapshot_reconciliation_status
    readiness.transaction_chain_complete = transaction_chain_complete
    readiness.nav_provider_available = nav_provider_available

    # ── Gate logic ───────────────────────────────────────────────────

    if not identity_verified_all:
        blocking_reasons.append("identity_not_all_verified")

    if manual_review_count > 0:
        blocking_reasons.append("manual_review_required")

    # Determine current holdings status
    has_confirmed_holdings = readiness.current_position_confirmed_count > 0
    has_probable_holdings = readiness.current_position_probable_count > 0
    has_any_current_holdings = has_confirmed_holdings or has_probable_holdings

    # Rule: probable only without snapshot → partial
    if has_probable_holdings and not has_confirmed_holdings and not holdings_snapshot_loaded:
        blocking_reasons.append("holdings_only_probable_no_snapshot")

    # ── Snapshot reconciliation scope ────────────────────────────────

    if holdings_snapshot_loaded and holdings_snapshot_reconciled:
        # Check for blocking conditions
        if identity_mismatch_count > 0:
            blocking_reasons.append("identity_mismatch_blocks_snapshot_reconciled")
            # Downgrade to snapshot_only
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY
            readiness.valuation_allowed = True
        elif closed_but_in_snapshot_count > 0:
            blocking_reasons.append("closed_but_in_snapshot_blocks_full")
            # Downgrade to snapshot_only
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY
            readiness.valuation_allowed = True
        elif probable_not_in_snapshot_count > 0 and snapshot_not_in_probable_count > 0:
            # Both sides have extras — partial reconciliation
            blocking_reasons.append("partial_reconciliation_both_sides_have_extras")
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED
            readiness.valuation_allowed = True
        elif probable_not_in_snapshot_count > 0:
            # Transaction has extras not in snapshot — probable excluded from snapshot valuation
            blocking_reasons.append("transaction_probable_not_in_snapshot_excluded")
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED
            readiness.valuation_allowed = True
        elif snapshot_not_in_probable_count > 0:
            # Snapshot has positions not seen in transactions
            blocking_reasons.append("snapshot_has_positions_not_in_transactions")
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED
            readiness.valuation_allowed = True
        else:
            # Fully reconciled — all snapshot positions matched with probable
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_RECONCILED
            readiness.valuation_allowed = True

    elif holdings_snapshot_loaded and not holdings_snapshot_reconciled:
        # Snapshot loaded but not reconciled — snapshot_only scope
        if identity_verified_all:
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY
            readiness.valuation_allowed = True
        else:
            readiness.valuation_scope = VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY
            readiness.valuation_allowed = True
            blocking_reasons.append("identity_incomplete_snapshot_partial")

    # ── Transaction-derived valuation (no snapshot) ──────────────────

    if not holdings_snapshot_loaded and has_any_current_holdings:
        if not nav_provider_available:
            blocking_reasons.append("nav_provider_unavailable")
            readiness.valuation_scope = VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL
            readiness.valuation_allowed = True
        elif has_confirmed_holdings and transaction_chain_complete and identity_verified_all:
            readiness.valuation_scope = VALUATION_SCOPE_TRANSACTION_DERIVED_FULL
            readiness.valuation_allowed = True
        elif has_probable_holdings:
            readiness.valuation_scope = VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL
            readiness.valuation_allowed = True
        else:
            readiness.valuation_scope = VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL
            readiness.valuation_allowed = True

    # Rule: Identity 15/15 but no current holdings and no snapshot
    if identity_verified_all and not has_any_current_holdings and not holdings_snapshot_loaded:
        blocking_reasons.append("no_current_holdings_identified")
        if readiness.valuation_scope == VALUATION_SCOPE_NONE:
            readiness.valuation_allowed = False

    # Rule: No NAV blocks transaction_derived_full
    if readiness.valuation_scope == VALUATION_SCOPE_TRANSACTION_DERIVED_FULL and not nav_provider_available:
        readiness.valuation_scope = VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL
        blocking_reasons.append("nav_unavailable_downgraded_to_partial")

    # Manual review blocks full valuation
    if manual_review_count > 0 and readiness.valuation_scope == VALUATION_SCOPE_TRANSACTION_DERIVED_FULL:
        readiness.valuation_scope = VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL
        blocking_reasons.append("manual_review_downgraded_to_partial")

    readiness.blocking_reasons = blocking_reasons

    return readiness
