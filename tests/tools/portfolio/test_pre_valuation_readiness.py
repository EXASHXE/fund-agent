"""Tests for M7.20 pre-valuation readiness gate.

Validates:
1. identity_verified_alone_does_not_allow_full_valuation
2. probable_current_holdings_only_allows_partial
3. holdings_snapshot_allows_snapshot_valuation
4. missing_nav_blocks_transaction_derived_full
5. manual_review_blocks_full_valuation
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.current_holding_discovery import (
    HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_HISTORY_ONLY,
    HoldingDiscoverySummary,
)
from src.tools.portfolio.pre_valuation_readiness import (
    VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY,
    VALUATION_SCOPE_NONE,
    VALUATION_SCOPE_TRANSACTION_DERIVED_FULL,
    VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL,
    assess_valuation_readiness,
)


def _make_holding_summary(
    confirmed: int = 0,
    probable: int = 0,
    closed: int = 0,
    history: int = 0,
    manual_review: int = 0,
) -> HoldingDiscoverySummary:
    return HoldingDiscoverySummary(
        ledger_fund_count=confirmed + probable + closed + history + manual_review,
        identity_verified_fund_count=confirmed + probable,
        current_position_confirmed_count=confirmed,
        current_position_probable_count=probable,
        closed_position_probable_count=closed,
        history_only_count=history,
        manual_review_required_count=manual_review,
    )


class TestIdentityVerifiedAloneDoesNotAllowFullValuation:
    """Identity verified alone (without current holding discovery) does NOT allow full valuation."""

    def test_identity_verified_no_holdings(self):
        readiness = assess_valuation_readiness(
            identity_verified_count=15,
            total_ledger_fund_count=15,
            holding_discovery=None,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=True,
        )
        # No holding discovery → can't determine which funds are current
        assert readiness.valuation_scope != VALUATION_SCOPE_TRANSACTION_DERIVED_FULL

    def test_identity_verified_no_current_holdings(self):
        summary = _make_holding_summary(closed=10, history=5)
        readiness = assess_valuation_readiness(
            identity_verified_count=15,
            total_ledger_fund_count=15,
            holding_discovery=summary,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=True,
        )
        # All funds are closed/history → no current holdings
        assert "no_current_holdings_identified" in readiness.blocking_reasons


class TestProbableCurrentHoldingsOnlyAllowsPartial:
    """Probable current holdings only allow partial valuation scope."""

    def test_probable_only_partial(self):
        summary = _make_holding_summary(probable=8)
        readiness = assess_valuation_readiness(
            identity_verified_count=8,
            total_ledger_fund_count=8,
            holding_discovery=summary,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=True,
        )
        # Probable only → cannot be transaction_derived_full
        assert readiness.valuation_scope == VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL
        assert "holdings_only_probable_no_snapshot" in readiness.blocking_reasons


class TestHoldingsSnapshotAllowsSnapshotValuation:
    """Holdings snapshot allows snapshot-based valuation."""

    def test_snapshot_with_identity(self):
        summary = _make_holding_summary(probable=8)
        readiness = assess_valuation_readiness(
            identity_verified_count=8,
            total_ledger_fund_count=8,
            holding_discovery=summary,
            holdings_snapshot_loaded=True,
            transaction_chain_complete=True,
            nav_provider_available=True,
        )
        assert readiness.valuation_scope == VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY
        assert readiness.valuation_allowed is True

    def test_snapshot_without_full_identity(self):
        summary = _make_holding_summary(probable=8)
        readiness = assess_valuation_readiness(
            identity_verified_count=5,
            total_ledger_fund_count=8,
            holding_discovery=summary,
            holdings_snapshot_loaded=True,
            transaction_chain_complete=True,
            nav_provider_available=True,
        )
        assert readiness.valuation_scope == VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY
        assert readiness.valuation_allowed is True
        assert "identity_incomplete_snapshot_partial" in readiness.blocking_reasons


class TestMissingNavBlocksTransactionDerivedFull:
    """Missing NAV provider blocks transaction_derived_full valuation."""

    def test_confirmed_no_nav(self):
        summary = _make_holding_summary(confirmed=8)
        readiness = assess_valuation_readiness(
            identity_verified_count=8,
            total_ledger_fund_count=8,
            holding_discovery=summary,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=False,
        )
        # Confirmed holdings but no NAV → partial
        assert readiness.valuation_scope == VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL
        assert "nav_provider_unavailable" in readiness.blocking_reasons

    def test_confirmed_with_nav(self):
        summary = _make_holding_summary(confirmed=8)
        readiness = assess_valuation_readiness(
            identity_verified_count=8,
            total_ledger_fund_count=8,
            holding_discovery=summary,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=True,
        )
        assert readiness.valuation_scope == VALUATION_SCOPE_TRANSACTION_DERIVED_FULL
        assert readiness.valuation_allowed is True


class TestManualReviewBlocksFullValuation:
    """Manual review required blocks full valuation."""

    def test_manual_review_downgrades_to_partial(self):
        summary = _make_holding_summary(confirmed=6, manual_review=2)
        readiness = assess_valuation_readiness(
            identity_verified_count=8,
            total_ledger_fund_count=8,
            holding_discovery=summary,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=True,
            manual_review_count=2,
        )
        # Manual review present → cannot be full
        assert readiness.valuation_scope != VALUATION_SCOPE_TRANSACTION_DERIVED_FULL
        assert "manual_review_required" in readiness.blocking_reasons


class TestFullValuationConditions:
    """Full valuation requires all conditions met."""

    def test_all_conditions_met(self):
        summary = _make_holding_summary(confirmed=15)
        readiness = assess_valuation_readiness(
            identity_verified_count=15,
            total_ledger_fund_count=15,
            holding_discovery=summary,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=True,
        )
        assert readiness.valuation_allowed is True
        assert readiness.valuation_scope == VALUATION_SCOPE_TRANSACTION_DERIVED_FULL
        assert readiness.identity_verified_all_ledger_funds is True

    def test_no_holdings_no_valuation(self):
        readiness = assess_valuation_readiness(
            identity_verified_count=0,
            total_ledger_fund_count=0,
            holding_discovery=None,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=False,
            nav_provider_available=False,
        )
        assert readiness.valuation_scope == VALUATION_SCOPE_NONE
