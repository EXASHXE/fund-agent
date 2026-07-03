"""Tests for M7.21 holdings snapshot loader.

Validates:
1. holdings_snapshot_loads_valid_csv
2. holdings_snapshot_rejects_invalid_code
3. holdings_snapshot_rejects_negative_amount
4. holdings_snapshot_rejects_zero_nav
5. holdings_snapshot_is_private_not_public
6. holdings_snapshot_not_used_for_identity_verification
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.tools.portfolio.holdings_snapshot import (
    HoldingsSnapshotEntry,
    HoldingsSnapshotSummary,
    load_holdings_snapshot,
    validate_holdings_snapshot,
)


def _write_csv(tmp_path: Path, rows: list[str]) -> Path:
    """Write a minimal CSV for testing."""
    csv_path = tmp_path / "snapshot.private.csv"
    header = "fund_name,fund_code,nav_date,unit_nav,current_amount,source,confidence,notes"
    lines = [header] + rows
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path


class TestHoldingsSnapshotLoadsValidCsv:
    """Valid CSV loads successfully."""

    def test_load_valid_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_csv(Path(tmp), [
                "某基金A,110011,2026-07-01,1.5,10000,alipay_holdings_snapshot,high,",
                "某基金B,110012,2026-07-01,2.3,5000,manual_snapshot,medium,",
            ])
            entries, summary = load_holdings_snapshot(csv_path)
            assert len(entries) == 2
            assert summary.position_count == 2
            assert summary.fund_code_available_count == 2
            assert summary.nav_available_count == 2
            assert summary.current_amount_available_count == 2
            assert summary.validation_errors == []

    def test_entry_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_csv(Path(tmp), [
                "某基金A,110011,2026-07-01,1.5,10000,alipay_holdings_snapshot,high,test note",
            ])
            entries, _ = load_holdings_snapshot(csv_path)
            assert entries[0].fund_name == "某基金A"
            assert entries[0].fund_code == "110011"
            assert entries[0].nav_date == "2026-07-01"
            assert entries[0].unit_nav == 1.5
            assert entries[0].current_amount == 10000
            assert entries[0].source == "alipay_holdings_snapshot"
            assert entries[0].confidence == "high"
            assert entries[0].notes == "test note"


class TestHoldingsSnapshotRejectsInvalidCode:
    """Invalid fund_code must be rejected."""

    def test_non_6_digit_code(self):
        entries = [HoldingsSnapshotEntry(fund_code="12345")]
        errors = validate_holdings_snapshot(entries)
        assert any("6 digits" in e for e in errors)

    def test_empty_code(self):
        entries = [HoldingsSnapshotEntry(fund_code="")]
        errors = validate_holdings_snapshot(entries)
        assert any("fund_code is required" in e for e in errors)

    def test_alpha_code(self):
        entries = [HoldingsSnapshotEntry(fund_code="ABCDEF")]
        errors = validate_holdings_snapshot(entries)
        assert len(errors) > 0


class TestHoldingsSnapshotRejectsNegativeAmount:
    """Negative current_amount must be rejected."""

    def test_negative_amount(self):
        entries = [HoldingsSnapshotEntry(fund_code="110011", current_amount=-100)]
        errors = validate_holdings_snapshot(entries)
        assert any("non-negative" in e for e in errors)


class TestHoldingsSnapshotRejectsZeroNav:
    """Zero or negative unit_nav must be rejected."""

    def test_zero_nav(self):
        entries = [HoldingsSnapshotEntry(fund_code="110011", unit_nav=0)]
        errors = validate_holdings_snapshot(entries)
        assert any("unit_nav must be > 0" in e for e in errors)

    def test_negative_nav(self):
        entries = [HoldingsSnapshotEntry(fund_code="110011", unit_nav=-1.5)]
        errors = validate_holdings_snapshot(entries)
        assert any("unit_nav must be > 0" in e for e in errors)


class TestHoldingsSnapshotIsPrivateNotPublic:
    """Snapshot must be private — not in public reports."""

    def test_summary_has_no_fund_codes(self):
        summary = HoldingsSnapshotSummary(position_count=3)
        d = summary.to_dict()
        d_str = str(d)
        import re
        codes = re.findall(r'\b\d{6}\b', d_str)
        assert len(codes) == 0

    def test_summary_has_no_amounts(self):
        summary = HoldingsSnapshotSummary(position_count=3)
        d = summary.to_dict()
        # No raw monetary values in summary — count fields are OK
        for key in d:
            assert key != "current_amount", f"summary should not expose raw current_amount"
            assert key != "unit_nav", f"summary should not expose raw unit_nav"

    def test_entry_to_dict_contains_private_data(self):
        """Entry to_dict has private data — must not appear in public report."""
        entry = HoldingsSnapshotEntry(fund_code="110011", current_amount=10000, unit_nav=1.5)
        d = entry.to_dict()
        assert d["fund_code"] == "110011"
        assert d["current_amount"] == 10000
        assert d["unit_nav"] == 1.5


class TestHoldingsSnapshotNotUsedForIdentityVerification:
    """Snapshot must not be used as identity oracle."""

    def test_snapshot_has_no_identity_verification_status(self):
        """HoldingsSnapshotEntry has no identity_verification_status field."""
        entry = HoldingsSnapshotEntry(fund_code="110011")
        assert not hasattr(entry, "identity_verification_status")

    def test_snapshot_cannot_set_provider_verified(self):
        """There is no mechanism to set provider_verified from snapshot."""
        # The HoldingsSnapshotEntry dataclass has no identity fields
        entry = HoldingsSnapshotEntry(fund_code="110011")
        d = entry.to_dict()
        assert "identity_verification_status" not in d
        assert "provider_verified" not in d


class TestHoldingsSnapshotFileNotFound:
    """File not found handling."""

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_holdings_snapshot(Path("/nonexistent/snapshot.csv"))

    def test_non_csv_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "snapshot.json"
            json_path.write_text("{}", encoding="utf-8")
            with pytest.raises(ValueError, match="Unsupported"):
                load_holdings_snapshot(json_path)
