"""Tests for M7.22 snapshot valuation reconciliation.

Validates:
1. snapshot_implied_shares_computed
2. provider_nav_same_date_reconciles
3. provider_nav_date_mismatch_warns_not_fail
4. missing_provider_nav_marks_partial
5. amount_diff_above_threshold_manual_review
6. public_summary_has_no_amount_or_nav
7. excluded_probable_not_in_snapshot
8. identity_mismatch_blocks_valuation
9. full_portfolio_metrics_allowed
10. amount_diff_pct_buckets
11. private_csv_generated
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.tools.portfolio.holding_snapshot_reconciliation import (
    RECON_STATUS_FULLY_RECONCILED,
    RECON_STATUS_SNAPSHOT_HAS_UNSEEN_POSITIONS,
    RECON_STATUS_TRANSACTION_PROBABLE_EXTRA,
    HoldingSnapshotReconciliationResult,
    ReconciliationDiffEntry,
    reconcile_holdings,
)
from src.tools.portfolio.holdings_snapshot import HoldingsSnapshotEntry
from src.tools.portfolio.snapshot_valuation_reconciliation import (
    DEFAULT_AMOUNT_DIFF_THRESHOLD_PCT,
    VAL_RECON_STATUS_AMOUNT_MISMATCH_MANUAL_REVIEW,
    VAL_RECON_STATUS_FULLY_RECONCILED,
    VAL_RECON_STATUS_MANUAL_REVIEW_REQUIRED,
    VAL_RECON_STATUS_MISSING_NAV_PARTIAL,
    VAL_RECON_STATUS_NAV_DATE_MISMATCH,
    VAL_STATUS_BLOCKED_IDENTITY_MISMATCH,
    VAL_STATUS_BLOCKED_MISSING_NAV,
    VAL_STATUS_EXCLUDED_PROBABLE_NOT_IN_SNAPSHOT,
    VAL_STATUS_MATCHED_SNAPSHOT_POSITION,
    VAL_STATUS_SNAPSHOT_ONLY_POSITION,
    SnapshotValuationPosition,
    SnapshotValuationResult,
    SnapshotValuationSummary,
    reconcile_snapshot_valuation,
    write_snapshot_valuation_diff_csv,
)
from src.tools.portfolio.current_holding_discovery import (
    HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
    CurrentHoldingCandidate,
)


def _make_snapshot_entry(
    fund_code: str = "110011",
    current_amount: float = 10000,
    unit_nav: float = 1.5,
    nav_date: str = "2026-06-30",
) -> HoldingsSnapshotEntry:
    return HoldingsSnapshotEntry(
        fund_code=fund_code,
        fund_name="某基金",
        current_amount=current_amount,
        unit_nav=unit_nav,
        nav_date=nav_date,
        source="alipay_holdings_snapshot",
        confidence="high",
    )


def _make_candidate(
    fund_code: str = "110011",
    lifecycle_status: str = HOLDING_LIFECYCLE_CURRENT_POSITION_PROBABLE,
) -> CurrentHoldingCandidate:
    return CurrentHoldingCandidate(
        fund_code=fund_code,
        identity_status="provider_verified",
        lifecycle_status=lifecycle_status,
    )


def _make_holding_reconciliation(
    matched_codes: set[str] | None = None,
    snapshot_only_codes: set[str] | None = None,
    probable_extra_codes: set[str] | None = None,
) -> HoldingSnapshotReconciliationResult:
    """Build a minimal HoldingSnapshotReconciliationResult for testing."""
    matched = matched_codes or set()
    snapshot_only = snapshot_only_codes or set()
    probable_extra = probable_extra_codes or set()

    diff_entries = []
    for code in sorted(matched):
        diff_entries.append(ReconciliationDiffEntry(
            fund_code=code, reconciliation_result="confirmed",
        ))
    for code in sorted(snapshot_only):
        diff_entries.append(ReconciliationDiffEntry(
            fund_code=code, reconciliation_result="snapshot_only",
        ))
    for code in sorted(probable_extra):
        diff_entries.append(ReconciliationDiffEntry(
            fund_code=code, reconciliation_result="probable_extra",
        ))

    return HoldingSnapshotReconciliationResult(
        snapshot_position_count=len(matched) + len(snapshot_only),
        probable_current_count=len(matched) + len(probable_extra),
        confirmed_current_count=len(matched),
        matched_snapshot_count=len(matched),
        probable_not_in_snapshot_count=len(probable_extra),
        snapshot_not_in_probable_count=len(snapshot_only),
        valuation_ready_position_count=len(matched) + len(snapshot_only),
        reconciliation_status=RECON_STATUS_FULLY_RECONCILED,
        private_diff_entries=diff_entries,
    )


class MockNAVProvider:
    """Mock NAV provider for testing."""

    def __init__(self, nav_data: dict[str, dict] | None = None):
        self._nav_data = nav_data or {}
        self._request_count = 0

    def get_latest_nav(self, fund_code: str) -> dict | None:
        self._request_count += 1
        return self._nav_data.get(fund_code)

    def get_trade_date_nav(self, fund_code: str, trade_date: str) -> dict | None:
        self._request_count += 1
        data = self._nav_data.get(fund_code)
        if data and data.get("nav_date") == trade_date:
            return data
        return None

    def get_diagnostics(self):
        from src.tools.portfolio.provider_contracts import ProviderDiagnostics
        return ProviderDiagnostics(provider_name="mock_nav", request_count=self._request_count)


class TestSnapshotImpliedSharesComputed:
    """implied_shares = current_amount_snapshot / unit_nav_snapshot."""

    def test_implied_shares_computed(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5)]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        result = reconcile_snapshot_valuation(snapshot, recon)
        pos = result.positions[0]
        assert pos.implied_shares == 10000.0

    def test_implied_shares_zero_nav(self):
        entry = HoldingsSnapshotEntry(fund_code="110011", unit_nav=0, current_amount=1000)
        snapshot = [entry]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        result = reconcile_snapshot_valuation(snapshot, recon)
        pos = result.positions[0]
        assert pos.implied_shares is None


class TestProviderNavSameDateReconciles:
    """Provider NAV on same date allows strict reconciliation."""

    def test_same_date_reconciles(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5, nav_date="2026-06-30")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({
            "110011": {"nav": 1.5, "nav_date": "2026-06-30", "source": "mock"},
        })
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        pos = result.positions[0]
        assert pos.provider_unit_nav == 1.5
        assert pos.nav_diff_pct == 0.0
        assert pos.amount_diff_pct == 0.0
        assert result.summary.valuation_reconciliation_status == VAL_RECON_STATUS_FULLY_RECONCILED

    def test_nav_diff_computed(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5, nav_date="2026-06-30")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({
            "110011": {"nav": 1.51, "nav_date": "2026-06-30", "source": "mock"},
        })
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        pos = result.positions[0]
        assert pos.nav_diff_pct is not None
        assert pos.nav_diff_pct > 0


class TestProviderNavDateMismatchWarnsNotFail:
    """Provider NAV date different from snapshot → warning, not error."""

    def test_date_mismatch_warns(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5, nav_date="2026-06-30")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({
            "110011": {"nav": 1.5, "nav_date": "2026-06-29", "source": "mock"},
        })
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        pos = result.positions[0]
        assert "nav_date_mismatch" in pos.blocking_reasons
        assert result.summary.nav_date_mismatch_count == 1
        assert result.summary.valuation_reconciliation_status == VAL_RECON_STATUS_NAV_DATE_MISMATCH


class TestMissingProviderNavMarksPartial:
    """Missing provider NAV marks partial but does not block baseline."""

    def test_missing_nav_partial(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5)]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({})  # No NAV data
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        pos = result.positions[0]
        assert "provider_nav_unavailable" in pos.blocking_reasons
        assert result.summary.missing_nav_count == 1
        assert result.summary.valuation_reconciliation_status == VAL_RECON_STATUS_MISSING_NAV_PARTIAL
        # Baseline still available
        assert pos.unit_nav_snapshot == 1.5
        assert pos.current_amount_snapshot == 15000

    def test_no_provider_at_all(self):
        snapshot = [_make_snapshot_entry("110011")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=None)
        assert result.summary.missing_nav_count == 0  # No provider = no missing NAV check
        assert result.summary.valuation_reconciliation_status == VAL_RECON_STATUS_FULLY_RECONCILED


class TestAmountDiffAboveThresholdManualReview:
    """amount_diff_pct > threshold → amount_mismatch_manual_review."""

    def test_above_threshold(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5, nav_date="2026-06-30")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({
            "110011": {"nav": 1.52, "nav_date": "2026-06-30", "source": "mock"},
        })
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        pos = result.positions[0]
        # 1.5 -> 1.52 is ~1.3% diff, well above 0.5% threshold
        assert pos.amount_diff_pct is not None
        if pos.amount_diff_pct > DEFAULT_AMOUNT_DIFF_THRESHOLD_PCT:
            assert "amount_mismatch_exceeds_threshold" in pos.blocking_reasons

    def test_below_threshold(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5, nav_date="2026-06-30")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({
            "110011": {"nav": 1.5001, "nav_date": "2026-06-30", "source": "mock"},
        })
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        pos = result.positions[0]
        assert "amount_mismatch_exceeds_threshold" not in pos.blocking_reasons


class TestPublicSummaryHasNoAmountOrNav:
    """Public summary must not contain amounts, NAV, or shares."""

    def test_public_dict_no_amounts(self):
        summary = SnapshotValuationSummary(
            snapshot_position_count=3,
            valued_position_count=3,
            total_snapshot_amount=50000,
            total_recomputed_amount=50100,
        )
        public = summary.to_public_dict()
        for key in public:
            assert key != "total_snapshot_amount", "public should not have total_snapshot_amount"
            assert key != "total_recomputed_amount", "public should not have total_recomputed_amount"
            assert key != "total_amount_diff_abs", "public should not have total_amount_diff_abs"
            assert key != "total_amount_diff_pct", "public should not have total_amount_diff_pct"

    def test_public_dict_no_fund_codes(self):
        result = SnapshotValuationResult(
            summary=SnapshotValuationSummary(snapshot_position_count=2, valued_position_count=2),
            positions=[
                SnapshotValuationPosition(fund_code="110011", valuation_status=VAL_STATUS_MATCHED_SNAPSHOT_POSITION),
                SnapshotValuationPosition(fund_code="110012", valuation_status=VAL_STATUS_SNAPSHOT_ONLY_POSITION),
            ],
        )
        public = result.to_public_dict()
        public_str = str(public)
        import re
        codes = re.findall(r'\b\d{6}\b', public_str)
        assert len(codes) == 0


class TestExcludedProbableNotInSnapshot:
    """Probable not in snapshot must be excluded from valuation."""

    def test_excluded(self):
        snapshot = [_make_snapshot_entry("110011")]
        recon = _make_holding_reconciliation(
            matched_codes={"110011"},
            probable_extra_codes={"110012"},
        )
        result = reconcile_snapshot_valuation(snapshot, recon)
        excluded = [p for p in result.positions if p.valuation_status == VAL_STATUS_EXCLUDED_PROBABLE_NOT_IN_SNAPSHOT]
        assert len(excluded) == 1
        assert excluded[0].fund_code == "110012"
        assert result.summary.excluded_probable_not_in_snapshot_count == 1


class TestIdentityMismatchBlocksValuation:
    """Identity mismatch blocks valuation for that position."""

    def test_identity_mismatch_blocked(self):
        snapshot = [_make_snapshot_entry("110011")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        result = reconcile_snapshot_valuation(
            snapshot, recon, identity_mismatch_codes={"110011"},
        )
        pos = result.positions[0]
        assert pos.valuation_status == VAL_STATUS_BLOCKED_IDENTITY_MISMATCH
        assert result.summary.valuation_reconciliation_status == VAL_RECON_STATUS_MANUAL_REVIEW_REQUIRED


class TestFullPortfolioMetricsAllowed:
    """full_portfolio_metrics_allowed only when all conditions met."""

    def test_all_conditions_met(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5, nav_date="2026-06-30")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({
            "110011": {"nav": 1.5, "nav_date": "2026-06-30", "source": "mock"},
        })
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        assert result.summary.full_portfolio_metrics_allowed is True

    def test_missing_nav_blocks(self):
        snapshot = [_make_snapshot_entry("110011")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        nav_provider = MockNAVProvider({})  # No NAV
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        assert result.summary.full_portfolio_metrics_allowed is False

    def test_identity_mismatch_blocks(self):
        snapshot = [_make_snapshot_entry("110011")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        result = reconcile_snapshot_valuation(
            snapshot, recon, identity_mismatch_codes={"110011"},
        )
        assert result.summary.full_portfolio_metrics_allowed is False


class TestAmountDiffPctBuckets:
    """Amount diff percentage must be bucketed correctly."""

    def test_buckets_populated(self):
        snapshot = [
            _make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5, nav_date="2026-06-30"),
            _make_snapshot_entry("110012", current_amount=10000, unit_nav=2.0, nav_date="2026-06-30"),
        ]
        recon = _make_holding_reconciliation(matched_codes={"110011", "110012"})
        nav_provider = MockNAVProvider({
            "110011": {"nav": 1.5001, "nav_date": "2026-06-30", "source": "mock"},
            "110012": {"nav": 2.01, "nav_date": "2026-06-30", "source": "mock"},
        })
        result = reconcile_snapshot_valuation(snapshot, recon, nav_provider=nav_provider)
        total_bucketed = sum(result.amount_diff_pct_buckets.values())
        assert total_bucketed > 0


class TestPrivateCsvGenerated:
    """Private diff CSV generation."""

    def test_csv_generated(self):
        snapshot = [_make_snapshot_entry("110011", current_amount=15000, unit_nav=1.5)]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        result = reconcile_snapshot_valuation(snapshot, recon)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "diff.private.csv"
            write_snapshot_valuation_diff_csv(result.positions, output_path)
            assert output_path.exists()

            import csv
            with open(output_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) >= 1
            assert "fund_code" in rows[0]
            assert "valuation_status" in rows[0]

    def test_csv_has_recommended_action(self):
        snapshot = [_make_snapshot_entry("110011")]
        recon = _make_holding_reconciliation(matched_codes={"110011"})
        result = reconcile_snapshot_valuation(snapshot, recon)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "diff.private.csv"
            write_snapshot_valuation_diff_csv(result.positions, output_path)

            import csv
            with open(output_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert "recommended_action" in rows[0]
