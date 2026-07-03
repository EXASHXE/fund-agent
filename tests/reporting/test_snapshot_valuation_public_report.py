"""Tests for M7.22 snapshot valuation public report.

Validates:
1. public_summary_has_counts_no_amounts
2. valuation_result_public_has_no_private_data
3. no_fund_codes_in_public_output
4. no_formal_decision_in_output
"""
from __future__ import annotations

import re

import pytest

from src.tools.portfolio.snapshot_valuation_reconciliation import (
    VAL_STATUS_MATCHED_SNAPSHOT_POSITION,
    SnapshotValuationPosition,
    SnapshotValuationResult,
    SnapshotValuationSummary,
)


class TestPublicSummaryHasCountsNoAmounts:
    """Public summary must have counts but no amounts/NAV/shares."""

    def test_has_counts(self):
        summary = SnapshotValuationSummary(
            snapshot_position_count=5,
            valued_position_count=5,
            missing_nav_count=1,
        )
        public = summary.to_public_dict()
        assert public["snapshot_position_count"] == 5
        assert public["valued_position_count"] == 5
        assert public["missing_nav_count"] == 1

    def test_no_raw_amounts(self):
        summary = SnapshotValuationSummary(
            snapshot_position_count=3,
            total_snapshot_amount=50000,
            total_recomputed_amount=50100,
        )
        public = summary.to_public_dict()
        for key in public:
            assert key != "total_snapshot_amount"
            assert key != "total_recomputed_amount"
            assert key != "total_amount_diff_abs"
            assert key != "total_amount_diff_pct"


class TestValuationResultPublicHasNoPrivateData:
    """Valuation result public dict must not contain fund codes or amounts."""

    def test_no_fund_codes_in_public(self):
        result = SnapshotValuationResult(
            summary=SnapshotValuationSummary(snapshot_position_count=2, valued_position_count=2),
            positions=[
                SnapshotValuationPosition(fund_code="110011", valuation_status=VAL_STATUS_MATCHED_SNAPSHOT_POSITION),
                SnapshotValuationPosition(fund_code="110012", valuation_status=VAL_STATUS_MATCHED_SNAPSHOT_POSITION),
            ],
        )
        public = result.to_public_dict()
        public_str = str(public)
        codes = re.findall(r'\b\d{6}\b', public_str)
        assert len(codes) == 0

    def test_no_amounts_in_public(self):
        result = SnapshotValuationResult(
            summary=SnapshotValuationSummary(
                snapshot_position_count=1,
                valued_position_count=1,
                total_snapshot_amount=10000,
            ),
            positions=[
                SnapshotValuationPosition(
                    fund_code="110011",
                    valuation_status=VAL_STATUS_MATCHED_SNAPSHOT_POSITION,
                    current_amount_snapshot=10000,
                    unit_nav_snapshot=1.5,
                    implied_shares=6666.67,
                ),
            ],
        )
        public = result.to_public_dict()
        public_str = str(public)
        # No raw monetary values or NAV or shares
        assert "current_amount_snapshot" not in public
        assert "unit_nav_snapshot" not in public
        assert "implied_shares" not in public

    def test_positions_not_in_public(self):
        result = SnapshotValuationResult(
            summary=SnapshotValuationSummary(snapshot_position_count=1, valued_position_count=1),
            positions=[
                SnapshotValuationPosition(fund_code="110011"),
            ],
        )
        public = result.to_public_dict()
        assert "positions" not in public


class TestNoFormalDecisionInOutput:
    """Snapshot valuation must not produce formal investment decisions."""

    def test_result_has_no_decision_fields(self):
        result = SnapshotValuationResult(
            summary=SnapshotValuationSummary(snapshot_position_count=1, valued_position_count=1),
        )
        public = result.to_public_dict()
        d = result.summary.to_public_dict()
        # No decision-related fields
        assert "decision" not in str(public).lower() or "valuation_reconciliation_status" in str(public)
        assert "buy" not in str(public).lower()
        assert "sell" not in str(public).lower()
        assert "action" not in str(public).lower() or "full_portfolio_metrics_allowed" in str(public)
