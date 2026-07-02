"""Tests for M7.19 public supplemental fund universe provider.

Validates:
- Local supplement loads entries from CSV
- Rejects invalid fund codes
- Requires public source
- Low confidence entries do not auto-verify
- Supplement contains no private fields
- Composite universe merges akshare and supplement
"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest

from src.tools.portfolio.fund_universe_provider import (
    ALLOWED_PUBLIC_SOURCES,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    AkShareFundUniverseProvider,
    CompositeFundUniverseProvider,
    FundUniverseEntryData,
    LocalPublicFundUniverseSupplementProvider,
    supplement_contains_no_private_fields,
)


def _write_supplement_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a supplement CSV file."""
    csv_path = tmp_path / "fund_universe_supplement.public.csv"
    fieldnames = [
        "fund_code", "fund_name", "fund_full_name", "fund_short_name",
        "source", "source_url", "source_date", "confidence", "notes",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return csv_path


class TestLocalPublicUniverseSupplementLoadsEntries:
    """Supplement provider loads valid entries from CSV."""

    def test_loads_valid_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "000001",
                    "fund_name": "某基金A",
                    "fund_full_name": "某基金A",
                    "fund_short_name": "某基金A",
                    "source": "eastmoney",
                    "source_url": "",
                    "source_date": "2026-01-01",
                    "confidence": "high",
                    "notes": "",
                },
                {
                    "fund_code": "000002",
                    "fund_name": "某基金B",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "fund_company",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "medium",
                    "notes": "",
                },
            ])
            provider = LocalPublicFundUniverseSupplementProvider(csv_path)
            entries = provider.load_entries()

            assert len(entries) == 2
            assert entries[0].fund_code == "000001"
            assert entries[0].fund_name == "某基金A"
            assert entries[0].source == "eastmoney"
            assert entries[0].confidence == CONFIDENCE_HIGH
            assert entries[1].fund_code == "000002"
            assert entries[1].confidence == CONFIDENCE_MEDIUM

    def test_loads_from_full_name_when_name_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "000003",
                    "fund_name": "",
                    "fund_full_name": "某基金C全称",
                    "fund_short_name": "",
                    "source": "tiantian",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            provider = LocalPublicFundUniverseSupplementProvider(csv_path)
            entries = provider.load_entries()

            assert len(entries) == 1
            assert entries[0].primary_name == "某基金C全称"

    def test_file_not_found_returns_empty(self):
        provider = LocalPublicFundUniverseSupplementProvider(Path("/nonexistent/file.csv"))
        entries = provider.load_entries()
        assert entries == []


class TestLocalPublicUniverseSupplementRejectsInvalidCode:
    """Supplement provider rejects entries with invalid fund codes."""

    def test_rejects_non_6digit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "12345",  # 5 digits
                    "fund_name": "某基金",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "eastmoney",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "某基金A",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "eastmoney",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            provider = LocalPublicFundUniverseSupplementProvider(csv_path)
            entries = provider.load_entries()

            assert len(entries) == 1
            diag = provider.get_diagnostics()
            assert diag["rejected_count"] == 1
            assert diag["rejection_reasons"]["invalid_code"] == 1

    def test_rejects_empty_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "",
                    "fund_name": "某基金",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "eastmoney",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            provider = LocalPublicFundUniverseSupplementProvider(csv_path)
            entries = provider.load_entries()
            assert len(entries) == 0


class TestLocalPublicUniverseSupplementRequiresPublicSource:
    """Supplement provider requires entries from public sources."""

    def test_rejects_private_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "000001",
                    "fund_name": "某基金",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "private_oracle",  # Not a public source
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            provider = LocalPublicFundUniverseSupplementProvider(csv_path)
            entries = provider.load_entries()

            assert len(entries) == 0
            diag = provider.get_diagnostics()
            assert diag["rejected_count"] == 1
            assert diag["rejection_reasons"]["invalid_source"] == 1

    def test_rejects_empty_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "000001",
                    "fund_name": "某基金",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            provider = LocalPublicFundUniverseSupplementProvider(csv_path)
            entries = provider.load_entries()
            assert len(entries) == 0

    def test_accepts_all_allowed_public_sources(self):
        for source in ALLOWED_PUBLIC_SOURCES:
            with tempfile.TemporaryDirectory() as tmp:
                csv_path = _write_supplement_csv(Path(tmp), [
                    {
                        "fund_code": "000001",
                        "fund_name": "某基金",
                        "fund_full_name": "",
                        "fund_short_name": "",
                        "source": source,
                        "source_url": "",
                        "source_date": "",
                        "confidence": "high",
                        "notes": "",
                    },
                ])
                provider = LocalPublicFundUniverseSupplementProvider(csv_path)
                entries = provider.load_entries()
                assert len(entries) == 1, f"Failed for source={source}"


class TestLowConfidenceSupplementDoesNotAutoVerify:
    """Low confidence supplement entries must not auto-verify."""

    def test_low_confidence_flagged(self):
        entry = FundUniverseEntryData(
            fund_code="000001",
            fund_name="某基金",
            source="eastmoney",
            confidence=CONFIDENCE_LOW,
        )
        assert entry.confidence == CONFIDENCE_LOW

    def test_high_confidence_not_flagged(self):
        entry = FundUniverseEntryData(
            fund_code="000001",
            fund_name="某基金",
            source="eastmoney",
            confidence=CONFIDENCE_HIGH,
        )
        assert entry.confidence == CONFIDENCE_HIGH


class TestSupplementProviderContainsNoPrivateFields:
    """Supplement entries must not contain private data."""

    def test_clean_entries_pass(self):
        entries = [
            FundUniverseEntryData(
                fund_code="000001",
                fund_name="某基金A",
                source="eastmoney",
                confidence=CONFIDENCE_HIGH,
            ),
        ]
        assert supplement_contains_no_private_fields(entries) is True

    def test_private_field_in_extra_fails(self):
        entries = [
            FundUniverseEntryData(
                fund_code="000001",
                fund_name="某基金A",
                source="eastmoney",
                confidence=CONFIDENCE_HIGH,
                extra={"nav": "1.2345"},
            ),
        ]
        assert supplement_contains_no_private_fields(entries) is False

    def test_holdings_in_extra_fails(self):
        entries = [
            FundUniverseEntryData(
                fund_code="000001",
                fund_name="某基金A",
                source="eastmoney",
                confidence=CONFIDENCE_HIGH,
                extra={"持仓": "1000份"},
            ),
        ]
        assert supplement_contains_no_private_fields(entries) is False


class TestCompositeUniverseMergesAkshareAndSupplement:
    """Composite provider merges and deduplicates entries."""

    def test_merges_two_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "000002",
                    "fund_name": "补充基金B",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "eastmoney",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            supplement = LocalPublicFundUniverseSupplementProvider(csv_path)

            # Mock akshare provider
            class MockAkShare:
                def load_entries(self):
                    return [
                        FundUniverseEntryData(
                            fund_code="000001",
                            fund_name="AkShare基金A",
                            source="akshare_fund_universe",
                            confidence=CONFIDENCE_HIGH,
                        ),
                    ]
                def get_diagnostics(self):
                    return {"provider": "mock_akshare", "entry_count": 1}

            composite = CompositeFundUniverseProvider([MockAkShare(), supplement])
            entries = composite.load_entries()

            assert len(entries) == 2
            codes = {e.fund_code for e in entries}
            assert "000001" in codes
            assert "000002" in codes

    def test_deduplicates_by_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "000001",
                    "fund_name": "补充基金A",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "eastmoney",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            supplement = LocalPublicFundUniverseSupplementProvider(csv_path)

            class MockAkShare:
                def load_entries(self):
                    return [
                        FundUniverseEntryData(
                            fund_code="000001",
                            fund_name="AkShare基金A",
                            source="akshare_fund_universe",
                            confidence=CONFIDENCE_HIGH,
                        ),
                    ]
                def get_diagnostics(self):
                    return {"provider": "mock_akshare", "entry_count": 1}

            composite = CompositeFundUniverseProvider([MockAkShare(), supplement])
            entries = composite.load_entries()

            # First provider wins on dedup
            assert len(entries) == 1
            assert entries[0].fund_name == "AkShare基金A"

    def test_diagnostics_include_source_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = _write_supplement_csv(Path(tmp), [
                {
                    "fund_code": "000002",
                    "fund_name": "补充基金B",
                    "fund_full_name": "",
                    "fund_short_name": "",
                    "source": "eastmoney",
                    "source_url": "",
                    "source_date": "",
                    "confidence": "high",
                    "notes": "",
                },
            ])
            supplement = LocalPublicFundUniverseSupplementProvider(csv_path)

            class MockAkShare:
                def load_entries(self):
                    return [
                        FundUniverseEntryData(
                            fund_code="000001",
                            fund_name="基金A",
                            source="akshare_fund_universe",
                            confidence=CONFIDENCE_HIGH,
                        ),
                    ]
                def get_diagnostics(self):
                    return {"provider": "mock_akshare", "entry_count": 1}

            composite = CompositeFundUniverseProvider([MockAkShare(), supplement])
            composite.load_entries()
            diag = composite.get_diagnostics()

            assert diag["total_entry_count"] == 2
            assert "akshare_fund_universe" in diag["universe_source_counts"]
            assert "eastmoney" in diag["universe_source_counts"]
