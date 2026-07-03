"""Tests for M7.21 holdings snapshot public report.

Validates:
1. snapshot_summary_has_counts_no_fund_codes
2. reconciliation_result_public_has_no_private_data
3. snapshot_not_used_for_identity_verification
4. reconciliation_counts_are_integers
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.holding_snapshot_reconciliation import (
    RECON_STATUS_FULLY_RECONCILED,
    HoldingSnapshotReconciliationResult,
)
from src.tools.portfolio.holdings_snapshot import (
    HoldingsSnapshotEntry,
    HoldingsSnapshotSummary,
)


class TestSnapshotSummaryHasCountsNoFundCodes:
    """Snapshot summary must have counts but no fund codes or amounts."""

    def test_summary_has_position_count(self):
        summary = HoldingsSnapshotSummary(position_count=5)
        d = summary.to_dict()
        assert "position_count" in d
        assert d["position_count"] == 5

    def test_summary_no_fund_codes(self):
        summary = HoldingsSnapshotSummary(position_count=3)
        d = summary.to_dict()
        d_str = str(d)
        import re
        codes = re.findall(r'\b\d{6}\b', d_str)
        assert len(codes) == 0

    def test_summary_no_raw_amounts(self):
        summary = HoldingsSnapshotSummary(position_count=3)
        d = summary.to_dict()
        for key in d:
            assert key != "current_amount", "summary should not expose raw current_amount"
            assert key != "unit_nav", "summary should not expose raw unit_nav"


class TestReconciliationResultPublicHasNoPrivateData:
    """Reconciliation result public dict must not contain fund codes or amounts."""

    def test_public_dict_no_fund_codes(self):
        result = HoldingSnapshotReconciliationResult(
            snapshot_position_count=2,
            probable_current_count=2,
            confirmed_current_count=2,
            matched_snapshot_count=2,
            reconciliation_status=RECON_STATUS_FULLY_RECONCILED,
        )
        public = result.to_public_dict()
        public_str = str(public)
        import re
        codes = re.findall(r'\b\d{6}\b', public_str)
        assert len(codes) == 0

    def test_public_dict_no_amounts(self):
        result = HoldingSnapshotReconciliationResult(
            snapshot_position_count=2,
            probable_current_count=2,
            confirmed_current_count=2,
            matched_snapshot_count=2,
            reconciliation_status=RECON_STATUS_FULLY_RECONCILED,
        )
        public = result.to_public_dict()
        for key in public:
            assert key != "current_amount", "public dict should not have current_amount"
            assert key != "unit_nav", "public dict should not have unit_nav"

    def test_private_diff_not_in_public(self):
        """private_diff_entries must not appear in public dict."""
        result = HoldingSnapshotReconciliationResult(
            snapshot_position_count=1,
            probable_current_count=1,
            confirmed_current_count=1,
            reconciliation_status=RECON_STATUS_FULLY_RECONCILED,
        )
        public = result.to_public_dict()
        assert "private_diff_entries" not in public


class TestSnapshotNotUsedForIdentityVerification:
    """Snapshot must not be used as identity oracle."""

    def test_entry_has_no_identity_status(self):
        entry = HoldingsSnapshotEntry(fund_code="110011")
        assert not hasattr(entry, "identity_verification_status")

    def test_entry_to_dict_no_identity_fields(self):
        entry = HoldingsSnapshotEntry(fund_code="110011")
        d = entry.to_dict()
        assert "identity_verification_status" not in d
        assert "provider_verified" not in d


class TestReconciliationCountsAreIntegers:
    """All reconciliation counts must be integers."""

    def test_all_counts_are_int(self):
        result = HoldingSnapshotReconciliationResult()
        d = result.to_dict()
        count_fields = [
            "snapshot_position_count",
            "probable_current_count",
            "confirmed_current_count",
            "matched_snapshot_count",
            "probable_not_in_snapshot_count",
            "snapshot_not_in_probable_count",
            "closed_but_in_snapshot_count",
            "identity_mismatch_count",
            "valuation_ready_position_count",
        ]
        for field in count_fields:
            assert field in d, f"Missing field: {field}"
            assert isinstance(d[field], int), f"{field} should be int"
