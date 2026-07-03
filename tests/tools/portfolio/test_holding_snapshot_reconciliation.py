"""Tests for M7.21 holding snapshot reconciliation.

Validates:
1. snapshot_matches_probable_upgrades_to_confirmed
2. probable_not_in_snapshot_excluded_from_snapshot_valuation
3. snapshot_only_position_allowed_snapshot_valuation
4. closed_but_in_snapshot_requires_manual_review
5. identity_mismatch_blocks_full_valuation
6. reconciliation_counts_match_expected
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.current_holding_discovery import (
    HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE,
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    CurrentHoldingCandidate,
)
from src.tools.portfolio.holding_snapshot_reconciliation import (
    RECON_STATUS_FULLY_RECONCILED,
    RECON_STATUS_IDENTITY_MISMATCH,
    RECON_STATUS_MANUAL_REVIEW_REQUIRED,
    RECON_STATUS_SNAPSHOT_CONFIRMS_SUBSET,
    RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS,
    RECON_STATUS_TRANSACTION_PROBABLE_EXTRA,
    reconcile_holdings,
    write_reconciliation_diff_csv,
)
from src.tools.portfolio.holdings_snapshot import HoldingsSnapshotEntry


def _make_candidate(
    fund_code: str = "110011",
    lifecycle_status: str = HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
) -> CurrentHoldingCandidate:
    return CurrentHoldingCandidate(
        fund_code=fund_code,
        identity_status="provider_verified",
        lifecycle_status=lifecycle_status,
    )


def _make_snapshot_entry(
    fund_code: str = "110011",
    current_amount: float = 10000,
    unit_nav: float = 1.5,
) -> HoldingsSnapshotEntry:
    return HoldingsSnapshotEntry(
        fund_code=fund_code,
        fund_name="某基金",
        current_amount=current_amount,
        unit_nav=unit_nav,
        source="alipay_holdings_snapshot",
        confidence="high",
    )


class TestSnapshotMatchesProbableUpgradesToConfirmed:
    """Fund in both snapshot and probable → confirmed_current."""

    def test_match_upgrades(self):
        candidates = [_make_candidate("110011")]
        snapshot = [_make_snapshot_entry("110011")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.confirmed_current_count == 1
        assert result.matched_snapshot_count == 1

    def test_multiple_matches(self):
        candidates = [_make_candidate("110011"), _make_candidate("110012")]
        snapshot = [_make_snapshot_entry("110011"), _make_snapshot_entry("110012")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.confirmed_current_count == 2


class TestProbableNotInSnapshotExcludedFromSnapshotValuation:
    """Probable holdings not in snapshot are excluded from valuation set."""

    def test_probable_extra(self):
        candidates = [_make_candidate("110011"), _make_candidate("110012")]
        snapshot = [_make_snapshot_entry("110011")]  # 110012 not in snapshot
        result = reconcile_holdings(candidates, snapshot)
        assert result.probable_not_in_snapshot_count == 1
        assert result.confirmed_current_count == 1
        # Valuation-ready excludes probable_not_in_snapshot
        assert result.valuation_ready_position_count == 1  # only matched

    def test_probable_extra_status(self):
        candidates = [_make_candidate("110011"), _make_candidate("110012")]
        snapshot = [_make_snapshot_entry("110011")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.reconciliation_status == RECON_STATUS_TRANSACTION_PROBABLE_EXTRA


class TestSnapshotOnlyPositionAllowedSnapshotValuation:
    """Snapshot positions not in probable are allowed for snapshot valuation."""

    def test_snapshot_only(self):
        candidates = [_make_candidate("110011")]
        snapshot = [_make_snapshot_entry("110011"), _make_snapshot_entry("110013")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.snapshot_not_in_probable_count == 1
        # Valuation-ready includes snapshot-only positions
        assert result.valuation_ready_position_count == 2  # matched + snapshot_only

    def test_snapshot_only_status(self):
        candidates = [_make_candidate("110011")]
        snapshot = [_make_snapshot_entry("110011"), _make_snapshot_entry("110013")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.reconciliation_status == RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS


class TestClosedButInSnapshotRequiresManualReview:
    """Closed position appearing in snapshot requires manual review."""

    def test_closed_in_snapshot(self):
        candidates = [
            _make_candidate("110011"),
            _make_candidate("110014", HOLDING_LIFECYCLE_CLOSED_POSITION_PROBABLE),
        ]
        snapshot = [_make_snapshot_entry("110011"), _make_snapshot_entry("110014")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.closed_but_in_snapshot_count == 1
        assert result.reconciliation_status == RECON_STATUS_MANUAL_REVIEW_REQUIRED
        assert "closed_position_in_snapshot" in result.blocking_reasons


class TestIdentityMismatchBlocksFullValuation:
    """Identity mismatch in snapshot blocks full valuation."""

    def test_identity_mismatch(self):
        candidates = [_make_candidate("110011")]
        snapshot = [_make_snapshot_entry("110011")]
        identity = {
            "resolutions": [
                {"resolved_fund_code": "110011", "identity_verification_status": "name_only"},
            ]
        }
        result = reconcile_holdings(candidates, snapshot, identity)
        assert result.identity_mismatch_count == 1
        assert result.reconciliation_status == RECON_STATUS_IDENTITY_MISMATCH

    def test_no_mismatch_with_verified(self):
        candidates = [_make_candidate("110011")]
        snapshot = [_make_snapshot_entry("110011")]
        identity = {
            "resolutions": [
                {"resolved_fund_code": "110011", "identity_verification_status": "provider_verified"},
            ]
        }
        result = reconcile_holdings(candidates, snapshot, identity)
        assert result.identity_mismatch_count == 0
        assert result.reconciliation_status == RECON_STATUS_FULLY_RECONCILED


class TestReconciliationCountsMatchExpected:
    """Reconciliation counts must be consistent."""

    def test_fully_reconciled(self):
        candidates = [_make_candidate("110011"), _make_candidate("110012")]
        snapshot = [_make_snapshot_entry("110011"), _make_snapshot_entry("110012")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.snapshot_position_count == 2
        assert result.probable_current_count == 2
        assert result.confirmed_current_count == 2
        assert result.probable_not_in_snapshot_count == 0
        assert result.snapshot_not_in_probable_count == 0
        assert result.closed_but_in_snapshot_count == 0
        assert result.reconciliation_status == RECON_STATUS_FULLY_RECONCILED

    def test_empty_snapshot_and_candidates(self):
        result = reconcile_holdings([], [])
        assert result.snapshot_position_count == 0
        assert result.probable_current_count == 0
        assert result.confirmed_current_count == 0

    def test_both_sides_have_extras(self):
        candidates = [_make_candidate("110011"), _make_candidate("110012")]
        snapshot = [_make_snapshot_entry("110011"), _make_snapshot_entry("110013")]
        result = reconcile_holdings(candidates, snapshot)
        assert result.probable_not_in_snapshot_count == 1  # 110012
        assert result.snapshot_not_in_probable_count == 1  # 110013
        assert result.reconciliation_status == RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS


class TestReconciliationDiffCsv:
    """Private diff CSV generation."""

    def test_diff_csv_generated(self):
        import tempfile
        from pathlib import Path

        candidates = [_make_candidate("110011"), _make_candidate("110012")]
        snapshot = [_make_snapshot_entry("110011")]
        result = reconcile_holdings(candidates, snapshot)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "diff.private.csv"
            write_reconciliation_diff_csv(result.private_diff_entries, output_path)
            assert output_path.exists()

            import csv
            with open(output_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2  # matched + probable_extra
            # Check fund_code present in private CSV
            codes = [r["fund_code"] for r in rows]
            assert "110011" in codes
            assert "110012" in codes

    def test_public_result_has_no_codes_or_amounts(self):
        candidates = [_make_candidate("110011")]
        snapshot = [_make_snapshot_entry("110011")]
        result = reconcile_holdings(candidates, snapshot)
        public = result.to_public_dict()
        public_str = str(public)
        import re
        codes = re.findall(r'\b\d{6}\b', public_str)
        assert len(codes) == 0
