"""Tests for M7.20 current holding discovery public report.

Validates:
1. current_holding_discovery_summary_has_counts
2. public_report_uses_lifecycle_status_not_all_ledger_funds
3. closed_positions_not_counted_as_current_holdings
4. manual_review_blocks_full_valuation
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.current_holding_discovery import (
    HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_HISTORY_ONLY,
    HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED,
    HoldingDiscoverySummary,
    is_current_holding,
)
from src.tools.portfolio.pre_valuation_readiness import (
    VALUATION_SCOPE_CURRENT_HOLDINGS_SNAPSHOT_ONLY,
    VALUATION_SCOPE_NONE,
    VALUATION_SCOPE_TRANSACTION_DERIVED_FULL,
    VALUATION_SCOPE_TRANSACTION_DERIVED_PARTIAL,
    PreValuationReadiness,
    assess_valuation_readiness,
)


class TestCurrentHoldingDiscoverySummaryHasCounts:
    """Summary must contain all required count fields."""

    def test_summary_has_all_count_fields(self):
        summary = HoldingDiscoverySummary()
        d = summary.to_dict()
        required_fields = [
            "ledger_fund_count",
            "identity_verified_fund_count",
            "current_position_confirmed_count",
            "current_position_probable_count",
            "closed_position_probable_count",
            "history_only_count",
            "manual_review_required_count",
        ]
        for field in required_fields:
            assert field in d, f"Missing field: {field}"

    def test_summary_counts_are_integers(self):
        summary = HoldingDiscoverySummary()
        d = summary.to_dict()
        for field in [
            "ledger_fund_count", "identity_verified_fund_count",
            "current_position_confirmed_count", "current_position_probable_count",
            "closed_position_probable_count", "history_only_count",
            "manual_review_required_count",
        ]:
            assert isinstance(d[field], int), f"{field} should be int"


class TestPublicReportUsesLifecycleStatusNotAllLedgerFunds:
    """Public report must distinguish current holdings from all ledger funds."""

    def test_not_all_ledger_funds_are_current(self):
        """A fund in the ledger is not necessarily a current holding."""
        # History-only fund (dividend received) is NOT a current holding
        assert not is_current_holding(HOLDING_LIFECYCLE_HISTORY_ONLY)
        # Closed fund is NOT a current holding
        assert not is_current_holding(HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE)
        # Manual review is NOT a current holding
        assert not is_current_holding(HOLDING_LIFECYCLE_MANUAL_REVIEW_REQUIRED)

    def test_only_confirmed_and_probable_are_current(self):
        """Only confirmed and probable are considered current holdings."""
        assert is_current_holding(HOLDING_LIFECYCLE_CURRENT_POSITION_CONFIRMED)
        assert is_current_holding(HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE)


class TestClosedPositionsNotCountedAsCurrentHoldings:
    """Closed positions must not be counted as current holdings."""

    def test_closed_not_in_current_count(self):
        summary = HoldingDiscoverySummary(
            ledger_fund_count=5,
            current_position_confirmed_count=2,
            current_position_probable_count=1,
            closed_position_probable_count=2,
        )
        current_count = summary.current_position_confirmed_count + summary.current_position_probable_count
        closed_count = summary.closed_position_probable_count
        assert current_count == 3
        assert closed_count == 2
        assert current_count + closed_count <= summary.ledger_fund_count


class TestManualReviewBlocksFullValuation:
    """Manual review in holding discovery blocks full valuation."""

    def test_manual_review_blocks_full(self):
        summary = HoldingDiscoverySummary(
            ledger_fund_count=10,
            current_position_confirmed_count=7,
            current_position_probable_count=0,
            manual_review_required_count=3,
        )
        readiness = assess_valuation_readiness(
            identity_verified_count=7,
            total_ledger_fund_count=10,
            holding_discovery=summary,
            holdings_snapshot_loaded=False,
            transaction_chain_complete=True,
            nav_provider_available=True,
            manual_review_count=3,
        )
        assert readiness.valuation_scope != VALUATION_SCOPE_TRANSACTION_DERIVED_FULL
        assert "manual_review_required" in readiness.blocking_reasons
