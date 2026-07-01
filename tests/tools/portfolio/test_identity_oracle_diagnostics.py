"""Tests for M7.18 Expected Identity Oracle Diagnostics.

Validates:
1. Oracle file is NOT used for runtime resolution
2. Oracle diff detects exact_correct
3. Oracle diff detects exact_missed
4. Oracle diff detects wrong_code
5. Public summary has no codes or names
6. Private CSV contains expected codes
7. wrong_code blocks valuation
"""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pytest

from src.tools.portfolio.identity_oracle_diagnostics import (
    ORACLE_EXACT_CORRECT,
    ORACLE_EXACT_MISSED,
    ORACLE_NAME_VARIANT,
    ORACLE_UNRESOLVED,
    ORACLE_WRONG_CODE,
    OracleDiffEntry,
    OraclePublicSummary,
    compute_oracle_diagnostics,
    load_expected_identity_map,
    oracle_wrong_code_blocks_valuation,
    write_oracle_diff_csv,
)


def _make_expected_csv(tmp_path: Path, entries: list[dict[str, str]]) -> Path:
    """Write a temporary expected identity map CSV."""
    csv_path = tmp_path / "expected_fund_identity_map.private.csv"
    fieldnames = ["raw_fund_name", "expected_fund_code", "expected_provider_name"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry)
    return csv_path


def _make_resolution(
    raw_name: str,
    resolved_code: str | None = None,
    resolution_source: str = "name_search_auto_verified",
    ivs: str = "provider_verified",
    match_reasons: list[str] | None = None,
    candidates: list[dict] | None = None,
) -> dict:
    """Create a resolution dict for testing."""
    if candidates is None:
        candidates = [
            {
                "fund_code": resolved_code or "000000",
                "fund_name": raw_name,
                "match_score": 1.0,
                "match_bucket": "exact",
                "match_reasons": match_reasons or ["exact_fund_universe_name_match"],
                "source": "akshare_fund_universe_exact",
                "hard_reject": False,
                "critical_token_mismatch": [],
                "identity_token_overlap": 0.9,
                "risk_flags": [],
            },
        ]
    return {
        "resolved_fund_code": resolved_code,
        "raw_fund_name": raw_name,
        "fund_name": raw_name,
        "resolution_source": resolution_source,
        "identity_verification_status": ivs,
        "name_search_candidates": candidates,
    }


class TestOracleFileNotUsedForRuntimeResolution:
    """Oracle data must NEVER influence runtime resolution."""

    def test_oracle_does_not_modify_resolutions(self):
        """compute_oracle_diagnostics must not modify input resolutions."""
        resolutions = [
            _make_resolution("某基金A", resolved_code="110011"),
        ]
        expected = [
            {"raw_fund_name": "某基金A", "expected_fund_code": "110011", "expected_provider_name": "某基金A"},
        ]
        # Snapshot resolutions before
        code_before = resolutions[0]["resolved_fund_code"]
        source_before = resolutions[0]["resolution_source"]

        compute_oracle_diagnostics(expected, resolutions)

        # Resolutions unchanged
        assert resolutions[0]["resolved_fund_code"] == code_before
        assert resolutions[0]["resolution_source"] == source_before

    def test_oracle_does_not_create_resolved_code(self):
        """Oracle must not set resolved_fund_code on unresolved funds."""
        resolutions = [
            _make_resolution("某基金B", resolved_code=None, ivs="name_search_candidate_unverified",
                             match_reasons=["medium_name_similarity"]),
        ]
        expected = [
            {"raw_fund_name": "某基金B", "expected_fund_code": "000002", "expected_provider_name": "某基金B"},
        ]
        diff_entries, summary = compute_oracle_diagnostics(expected, resolutions)

        # Agent code is still None — oracle did not fill it
        assert diff_entries[0].agent_resolved_code is None
        assert resolutions[0]["resolved_fund_code"] is None

    def test_oracle_does_not_set_provider_verified(self):
        """Oracle must not change identity_verification_status to provider_verified."""
        resolutions = [
            _make_resolution("某基金C", resolved_code=None, ivs="name_search_candidate_unverified",
                             match_reasons=["high_name_similarity"]),
        ]
        expected = [
            {"raw_fund_name": "某基金C", "expected_fund_code": "000003", "expected_provider_name": "某基金C"},
        ]
        compute_oracle_diagnostics(expected, resolutions)

        # Status unchanged
        assert resolutions[0]["identity_verification_status"] == "name_search_candidate_unverified"


class TestOracleDiffDetectsExactCorrect:
    """Agent resolved the correct code matching oracle."""

    def test_exact_correct(self):
        resolutions = [
            _make_resolution("某基金A", resolved_code="110011"),
        ]
        expected = [
            {"raw_fund_name": "某基金A", "expected_fund_code": "110011", "expected_provider_name": "某基金A"},
        ]
        diff_entries, summary = compute_oracle_diagnostics(expected, resolutions)

        assert diff_entries[0].oracle_match_result == ORACLE_EXACT_CORRECT
        assert summary.oracle_exact_correct_count == 1
        assert summary.oracle_total == 1


class TestOracleDiffDetectsExactMissed:
    """Agent did not resolve a code that exists in oracle."""

    def test_exact_missed(self):
        resolutions = [
            _make_resolution("某基金D", resolved_code=None,
                             ivs="name_search_candidate_unverified",
                             match_reasons=["high_name_similarity"]),
        ]
        expected = [
            {"raw_fund_name": "某基金D", "expected_fund_code": "000004", "expected_provider_name": "某基金D"},
        ]
        diff_entries, summary = compute_oracle_diagnostics(expected, resolutions)

        assert diff_entries[0].oracle_match_result == ORACLE_EXACT_MISSED
        assert summary.oracle_exact_missed_count == 1


class TestOracleDiffDetectsWrongCode:
    """Agent resolved a different code than expected — critical error."""

    def test_wrong_code(self):
        resolutions = [
            _make_resolution("某基金E", resolved_code="999999"),
        ]
        expected = [
            {"raw_fund_name": "某基金E", "expected_fund_code": "000005", "expected_provider_name": "某基金E"},
        ]
        diff_entries, summary = compute_oracle_diagnostics(expected, resolutions)

        assert diff_entries[0].oracle_match_result == ORACLE_WRONG_CODE
        assert summary.oracle_wrong_code_count == 1


class TestOraclePublicSummaryHasNoCodesOrNames:
    """Public summary must not contain any fund names or codes."""

    def test_public_summary_no_codes(self):
        resolutions = [
            _make_resolution("某基金A", resolved_code="110011"),
            _make_resolution("某基金B", resolved_code=None,
                             ivs="name_search_candidate_unverified",
                             match_reasons=["high_name_similarity"]),
        ]
        expected = [
            {"raw_fund_name": "某基金A", "expected_fund_code": "110011", "expected_provider_name": "某基金A"},
            {"raw_fund_name": "某基金B", "expected_fund_code": "000002", "expected_provider_name": "某基金B"},
        ]
        _, summary = compute_oracle_diagnostics(expected, resolutions)

        summary_str = json.dumps(summary.to_dict(), ensure_ascii=False)
        # No 6-digit codes
        assert "110011" not in summary_str
        assert "000002" not in summary_str
        # No fund names
        assert "某基金" not in summary_str

    def test_public_summary_only_counts(self):
        resolutions = [
            _make_resolution("某基金A", resolved_code="110011"),
        ]
        expected = [
            {"raw_fund_name": "某基金A", "expected_fund_code": "110011", "expected_provider_name": "某基金A"},
        ]
        _, summary = compute_oracle_diagnostics(expected, resolutions)
        d = summary.to_dict()

        # Only count fields allowed
        allowed_keys = {
            "oracle_total",
            "oracle_exact_correct_count",
            "oracle_exact_missed_count",
            "oracle_wrong_code_count",
            "oracle_unresolved_count",
            "oracle_name_variant_count",
            "oracle_provider_universe_missing_count",
            "non_exact_auto_verified_count",
            "fuzzy_auto_verified_count",
        }
        assert set(d.keys()) == allowed_keys


class TestOraclePrivateCsvContainsExpectedCodes:
    """Private CSV must contain expected codes for debugging."""

    def test_private_csv_has_expected_code(self):
        diff_entries = [
            OracleDiffEntry(
                raw_fund_name="某基金A",
                expected_fund_code="110011",
                expected_provider_name="某基金A",
                agent_resolved_code="110011",
                agent_resolution_source="name_search_auto_verified",
                agent_identity_status="provider_verified",
                agent_match_reason="exact_fund_universe_name_match",
                oracle_match_result=ORACLE_EXACT_CORRECT,
                likely_root_cause="none",
                recommended_fix="none",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "identity_oracle_diff.private.csv"
            write_oracle_diff_csv(diff_entries, output_path)

            with open(output_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["expected_fund_code"] == "110011"
            assert rows[0]["agent_resolved_code"] == "110011"
            assert rows[0]["oracle_match_result"] == ORACLE_EXACT_CORRECT

    def test_private_csv_has_all_fields(self):
        diff_entries = [
            OracleDiffEntry(
                raw_fund_name="某基金B",
                expected_fund_code="000002",
                expected_provider_name="某基金B",
                agent_resolved_code=None,
                agent_resolution_source="name_only",
                agent_identity_status="name_search_candidate_unverified",
                agent_match_reason="high_name_similarity",
                oracle_match_result=ORACLE_EXACT_MISSED,
                likely_root_cause="no_exact_universe_match",
                recommended_fix="check_provider_universe",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "identity_oracle_diff.private.csv"
            write_oracle_diff_csv(diff_entries, output_path)

            with open(output_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["raw_fund_name"] == "某基金B"
            assert rows[0]["expected_fund_code"] == "000002"
            assert rows[0]["agent_resolved_code"] == ""
            assert rows[0]["oracle_match_result"] == ORACLE_EXACT_MISSED


class TestOracleWrongCodeBlocksValuation:
    """If wrong_code > 0, valuation must be blocked."""

    def test_wrong_code_blocks_valuation(self):
        summary = OraclePublicSummary(oracle_wrong_code_count=1)
        assert oracle_wrong_code_blocks_valuation(summary) is True

    def test_no_wrong_code_allows_valuation(self):
        summary = OraclePublicSummary(oracle_wrong_code_count=0)
        assert oracle_wrong_code_blocks_valuation(summary) is False

    def test_wrong_code_with_other_results_still_blocks(self):
        summary = OraclePublicSummary(
            oracle_total=3,
            oracle_exact_correct_count=2,
            oracle_wrong_code_count=1,
        )
        assert oracle_wrong_code_blocks_valuation(summary) is True


class TestOracleNameVariantDetection:
    """Name variant detection for common patterns."""

    def test_name_variant_unresolved_with_variant(self):
        """Unresolved fund where raw name is a variant of provider name."""
        resolutions = [
            _make_resolution("建信短债债券C", resolved_code=None,
                             ivs="name_search_candidate_unverified",
                             match_reasons=["high_name_similarity"]),
        ]
        expected = [
            {"raw_fund_name": "建信短债债券C", "expected_fund_code": "000208",
             "expected_provider_name": "建信中短债纯债C"},
        ]
        diff_entries, summary = compute_oracle_diagnostics(expected, resolutions)

        assert diff_entries[0].oracle_match_result == ORACLE_NAME_VARIANT
        assert summary.oracle_name_variant_count == 1

    def test_unresolved_without_variant_is_exact_missed(self):
        """Unresolved fund where raw name is NOT a variant of provider name."""
        resolutions = [
            _make_resolution("某基金X", resolved_code=None,
                             ivs="name_search_candidate_unverified",
                             match_reasons=["medium_name_similarity"]),
        ]
        expected = [
            {"raw_fund_name": "某基金X", "expected_fund_code": "000010",
             "expected_provider_name": "完全不同的基金Y"},
        ]
        diff_entries, summary = compute_oracle_diagnostics(expected, resolutions)

        assert diff_entries[0].oracle_match_result == ORACLE_EXACT_MISSED
        assert summary.oracle_exact_missed_count == 1


class TestLoadExpectedIdentityMap:
    """Test CSV loading."""

    def test_load_valid_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "expected.csv"
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["raw_fund_name", "expected_fund_code", "expected_provider_name"])
                writer.writeheader()
                writer.writerow({"raw_fund_name": "某基金A", "expected_fund_code": "110011", "expected_provider_name": "某基金A"})

            entries = load_expected_identity_map(csv_path)
            assert len(entries) == 1
            assert entries[0]["raw_fund_name"] == "某基金A"
            assert entries[0]["expected_fund_code"] == "110011"

    def test_skip_empty_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "expected.csv"
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["raw_fund_name", "expected_fund_code", "expected_provider_name"])
                writer.writeheader()
                writer.writerow({"raw_fund_name": "某基金A", "expected_fund_code": "", "expected_provider_name": "某基金A"})
                writer.writerow({"raw_fund_name": "某基金B", "expected_fund_code": "110012", "expected_provider_name": "某基金B"})

            entries = load_expected_identity_map(csv_path)
            assert len(entries) == 1
            assert entries[0]["expected_fund_code"] == "110012"


class TestOracleDiagnosticsMixedScenario:
    """Test with a mix of correct, missed, wrong, and variant results."""

    def test_mixed_scenario_counts(self):
        resolutions = [
            _make_resolution("基金A", resolved_code="110011"),  # exact_correct
            _make_resolution("基金B", resolved_code=None, ivs="name_search_candidate_unverified",
                             match_reasons=["high_name_similarity"]),  # exact_missed
            _make_resolution("基金C", resolved_code="999999"),  # wrong_code (auto-verified but wrong)
            _make_resolution("基金D", resolved_code=None, ivs="name_only",
                             resolution_source="name_only"),  # unresolved
        ]
        expected = [
            {"raw_fund_name": "基金A", "expected_fund_code": "110011", "expected_provider_name": "基金A"},
            {"raw_fund_name": "基金B", "expected_fund_code": "000002", "expected_provider_name": "基金B"},
            {"raw_fund_name": "基金C", "expected_fund_code": "000003", "expected_provider_name": "基金C"},
            {"raw_fund_name": "基金D", "expected_fund_code": "000004", "expected_provider_name": "基金D"},
        ]
        diff_entries, summary = compute_oracle_diagnostics(expected, resolutions)

        assert summary.oracle_total == 4
        assert summary.oracle_exact_correct_count == 1
        assert summary.oracle_exact_missed_count == 1
        assert summary.oracle_wrong_code_count == 1
        assert summary.oracle_unresolved_count == 1
