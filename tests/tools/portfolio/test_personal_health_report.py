"""Tests for personal portfolio health summary builder.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.personal_health_report import (
    REASON_CASHFLOW_ONLY,
    REASON_FALLBACK_HOLDINGS_USED,
    REASON_MANUAL_REVIEW_TRANSACTIONS,
    REASON_NAME_ONLY_FUNDS,
    REASON_NAV_MISSING,
    REASON_NO_VALID_FUND_CODES,
    REASON_PARTIAL_NAV_COVERAGE,
    REASON_QDII_NAV_LAG,
    REASON_STALE_NAV,
    SCHEMA_VERSION,
    build_personal_health_summary,
    VALID_OVERALL_STATUSES,
    VALID_REASON_CODES,
)


def _base_artifacts(**overrides) -> dict:
    """Create minimal valid artifacts for testing."""
    artifacts = {
        "e2e_summary": {
            "transaction_source": "alipay",
            "portfolio_input_source": "reconstructed_from_ledger",
            "pipeline_steps": {
                "fund_data_snapshot_attempted": True,
                "fund_data_snapshot_status": "attempted",
                "reconstruction_attempted": True,
                "reconstruction_status": "reconstructed_from_ledger",
                "valid_fund_codes_count": 3,
                "name_only_count": 0,
            },
        },
        "nav_coverage_summary": {
            "positions_total": 3,
            "positions_estimated": 3,
            "positions_cashflow_only": 0,
            "positions_unavailable": 0,
            "positions_manual_review_required": 0,
            "nav_coverage_full_count": 3,
            "nav_coverage_partial_count": 0,
            "nav_coverage_none_count": 0,
            "nav_coverage_latest_only_count": 0,
            "latest_nav_stale_count": 0,
            "qdii_like_count": 0,
            "estimated_current_value_total_is_partial": False,
        },
        "portfolio_input_transactions_summary": {
            "total_transactions": 10,
            "manual_review_required_count": 0,
            "manual_review_count": 0,
        },
        "identity_summary": {
            "total_funds": 3,
            "valid_fund_codes_count": 3,
            "name_only_count": 0,
        },
        "valuation_summary": {},
    }
    artifacts.update(overrides)
    return artifacts


class TestSchemaAndConstants:
    def test_schema_version(self):
        assert SCHEMA_VERSION == "personal_health_report.v1"

    def test_valid_overall_statuses(self):
        assert VALID_OVERALL_STATUSES == {"ok", "partial", "needs_data", "needs_manual_review", "unavailable"}

    def test_valid_reason_codes_are_frozenset(self):
        assert isinstance(VALID_REASON_CODES, frozenset)
        assert REASON_NO_VALID_FUND_CODES in VALID_REASON_CODES


class TestHealthReportOkStatus:
    def test_full_coverage_ok(self):
        """Full NAV coverage, reconstructed from ledger → ok, high confidence."""
        result = build_personal_health_summary(_base_artifacts())
        assert result["schema_version"] == SCHEMA_VERSION
        assert result["overall_status"] == "ok"
        assert result["confidence_level"] == "high"
        assert result["reason_codes"] == []
        assert result["data_sources"]["transaction_source"] == "alipay"
        assert result["data_sources"]["valuation_source"] == "reconstructed_from_ledger"
        assert result["data_sources"]["identity_source"] == "direct_fund_code"
        assert result["valuation_quality"]["positions_total"] == 3
        assert result["valuation_quality"]["estimated_full_coverage_count"] == 3
        assert result["fix_it_checklist"] == []
        assert len(result["safety_notes"]) > 0


class TestHealthReportCsvOnlyNeedsIdentityData:
    """Scenario A: CSV only, no overrides → needs_data."""

    def test_no_valid_fund_codes(self):
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["pipeline_steps"]["valid_fund_codes_count"] = 0
        artifacts["e2e_summary"]["pipeline_steps"]["name_only_count"] = 0
        artifacts["e2e_summary"]["pipeline_steps"]["reconstruction_status"] = "nav_unavailable"
        artifacts["e2e_summary"]["portfolio_input_source"] = "unavailable"
        artifacts["nav_coverage_summary"]["positions_total"] = 0
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 0

        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "needs_data"
        assert REASON_NO_VALID_FUND_CODES in result["reason_codes"]
        # Checklist should ask for identity overrides
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "identity_overrides" in checklist_text or "NAV" in checklist_text or "holdings" in checklist_text


class TestHealthReportIdentityNoNavNeedsNavData:
    """Scenario B: identity overrides, no NAV → needs_data with nav_missing."""

    def test_valid_codes_no_nav(self):
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["pipeline_steps"]["reconstruction_status"] = "nav_unavailable"
        artifacts["e2e_summary"]["portfolio_input_source"] = "unavailable"
        artifacts["identity_summary"]["override_validation_warnings"] = []
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 0
        artifacts["nav_coverage_summary"]["nav_coverage_none_count"] = 3
        artifacts["nav_coverage_summary"]["positions_estimated"] = 0
        artifacts["nav_coverage_summary"]["positions_unavailable"] = 3

        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "needs_data"
        assert REASON_NAV_MISSING in result["reason_codes"]
        assert result["data_sources"]["identity_source"] == "overrides"
        # Checklist should ask for NAV overrides
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "NAV" in checklist_text or "nav" in checklist_text.lower()


class TestHealthReportPartialNavCoverageMediumConfidence:
    """Scenario C2: partial NAV coverage → partial, medium confidence."""

    def test_partial_nav(self):
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 1
        artifacts["nav_coverage_summary"]["nav_coverage_partial_count"] = 2
        artifacts["nav_coverage_summary"]["positions_estimated"] = 3

        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "partial"
        assert result["confidence_level"] == "medium"
        assert REASON_PARTIAL_NAV_COVERAGE in result["reason_codes"]
        assert result["valuation_quality"]["estimated_current_value_total_is_partial"] is False

    def test_partial_nav_with_is_partial_flag(self):
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 1
        artifacts["nav_coverage_summary"]["nav_coverage_partial_count"] = 2
        artifacts["nav_coverage_summary"]["estimated_current_value_total_is_partial"] = True

        result = build_personal_health_summary(artifacts)
        assert result["valuation_quality"]["estimated_current_value_total_is_partial"] is True


class TestHealthReportManualReviewTransactions:
    """M2: portfolio_input.transactions with warnings → manual_review_transactions."""

    def test_manual_review_transactions(self):
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["transaction_source"] = "portfolio_input.transactions"
        artifacts["portfolio_input_transactions_summary"]["manual_review_required_count"] = 2
        artifacts["portfolio_input_transactions_summary"]["manual_review_count"] = 2

        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "needs_manual_review"
        assert REASON_MANUAL_REVIEW_TRANSACTIONS in result["reason_codes"]
        # Checklist should mention review
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "Review" in checklist_text or "review" in checklist_text

    def test_no_raw_transaction_values(self):
        """Checklist and reason codes must not contain raw transaction values."""
        artifacts = _base_artifacts()
        artifacts["portfolio_input_transactions_summary"]["manual_review_required_count"] = 1

        result = build_personal_health_summary(artifacts)
        all_text = " ".join(
            result["reason_codes"]
            + result["fix_it_checklist"]
            + result["safety_notes"]
        )
        # Should not contain amounts, transaction IDs, or notes
        for forbidden in ["100.0", "TXN_", "note:", "order_id"]:
            assert forbidden not in all_text


class TestHealthReportFallbackHoldingsNotReconstructed:
    """D2: holdings fallback → fallback_holdings_used, no reconstructed_from_ledger."""

    def test_fallback_holdings(self):
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["portfolio_input_source"] = "existing_private_portfolio_input"

        result = build_personal_health_summary(artifacts)
        assert REASON_FALLBACK_HOLDINGS_USED in result["reason_codes"]
        assert result["data_sources"]["valuation_source"] == "existing_private_portfolio_input"
        # Must NOT say reconstructed_from_ledger
        all_text = " ".join(result["reason_codes"] + result["fix_it_checklist"])
        assert "reconstructed_from_ledger" not in all_text

    def test_fallback_confidence_medium(self):
        """Fallback holdings should be medium confidence at best."""
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["portfolio_input_source"] = "existing_private_portfolio_input"

        result = build_personal_health_summary(artifacts)
        assert result["confidence_level"] in ("medium", "low")


class TestHealthReportStaleQdiiNav:
    """M3: stale NAV / QDII → stale_nav / qdii_nav_lag reason codes."""

    def test_stale_qdii_nav(self):
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["latest_nav_stale_count"] = 2
        artifacts["nav_coverage_summary"]["qdii_like_count"] = 1

        result = build_personal_health_summary(artifacts)
        assert REASON_STALE_NAV in result["reason_codes"]
        assert REASON_QDII_NAV_LAG in result["reason_codes"]
        # Checklist should ask about NAV freshness
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "NAV freshness" in checklist_text or "QDII" in checklist_text

    def test_stale_without_qdii(self):
        """Stale NAV without QDII → stale_nav only, no qdii_nav_lag."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["latest_nav_stale_count"] = 1
        artifacts["nav_coverage_summary"]["qdii_like_count"] = 0

        result = build_personal_health_summary(artifacts)
        assert REASON_STALE_NAV in result["reason_codes"]
        assert REASON_QDII_NAV_LAG not in result["reason_codes"]


class TestHealthReportNameOnlyFunds:
    """Name-only funds should trigger name_only_funds reason code."""

    def test_name_only_funds(self):
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["pipeline_steps"]["name_only_count"] = 2
        artifacts["e2e_summary"]["pipeline_steps"]["valid_fund_codes_count"] = 1
        artifacts["identity_summary"]["name_only_count"] = 2

        result = build_personal_health_summary(artifacts)
        assert REASON_NAME_ONLY_FUNDS in result["reason_codes"]
        assert result["data_sources"]["identity_source"] == "name_only"
        # Checklist should ask for identity overrides
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "identity_overrides" in checklist_text

    def test_name_only_zero_valid_codes_includes_no_valid_fund_codes(self):
        """When valid_fund_codes_count=0 and name_only_count>0, both
        no_valid_fund_codes AND name_only_funds should appear."""
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["pipeline_steps"]["valid_fund_codes_count"] = 0
        artifacts["e2e_summary"]["pipeline_steps"]["name_only_count"] = 3
        artifacts["identity_summary"]["name_only_count"] = 3
        artifacts["nav_coverage_summary"]["positions_total"] = 0
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 0

        result = build_personal_health_summary(artifacts)
        assert REASON_NO_VALID_FUND_CODES in result["reason_codes"]
        assert REASON_NAME_ONLY_FUNDS in result["reason_codes"]
        assert result["overall_status"] == "needs_data"
        # Checklist should ask for identity overrides
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "identity_overrides" in checklist_text


class TestHealthReportUnavailable:
    """No transaction source, no portfolio input → unavailable."""

    def test_unavailable(self):
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["transaction_source"] = "none"
        artifacts["e2e_summary"]["portfolio_input_source"] = "unavailable"
        artifacts["e2e_summary"]["pipeline_steps"]["valid_fund_codes_count"] = 0
        artifacts["e2e_summary"]["pipeline_steps"]["name_only_count"] = 0
        artifacts["nav_coverage_summary"]["positions_total"] = 0
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 0

        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "unavailable"
        assert result["confidence_level"] == "unavailable"


class TestHealthReportPrivacyRedaction:
    """Privacy: no fund names, amounts, paths, or IDs in output."""

    def test_no_private_data_in_output(self):
        artifacts = _base_artifacts()
        # Even with rich data, output should not contain private info
        result = build_personal_health_summary(artifacts)

        output_str = str(result)
        for forbidden in [
            "fund_name",
            "private_data/",
            "local_data/",
            "api_key",
            "token",
            "secret",
            "cookie",
            "transaction_id",
            "order_id",
        ]:
            assert forbidden not in output_str.lower(), f"Found forbidden string: {forbidden}"

    def test_counts_only_in_checklist(self):
        """Checklist should use counts, not real amounts."""
        artifacts = _base_artifacts()
        artifacts["e2e_summary"]["pipeline_steps"]["name_only_count"] = 3
        result = build_personal_health_summary(artifacts)

        for item in result["fix_it_checklist"]:
            # Should not contain real amounts like 10000.00
            assert "10000" not in item
            # Should contain count references
            assert "3" in item or "fund" in item.lower() or "NAV" in item


class TestHealthReportSafetyNotes:
    """Safety notes must always be present."""

    def test_safety_notes_always_present(self):
        for status in ("ok", "partial", "needs_data", "unavailable"):
            artifacts = _base_artifacts()
            if status == "unavailable":
                artifacts["e2e_summary"]["transaction_source"] = "none"
                artifacts["e2e_summary"]["portfolio_input_source"] = "unavailable"
                artifacts["e2e_summary"]["pipeline_steps"]["valid_fund_codes_count"] = 0
                artifacts["e2e_summary"]["pipeline_steps"]["name_only_count"] = 0
                artifacts["nav_coverage_summary"]["positions_total"] = 0
                artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 0
            result = build_personal_health_summary(artifacts)
            assert len(result["safety_notes"]) >= 3
            all_notes = " ".join(result["safety_notes"])
            assert "decision" in all_notes.lower() or "instruction" in all_notes.lower()
            assert "broker" in all_notes.lower() or "trading" in all_notes.lower()

    def test_no_trading_advice_in_checklist(self):
        """Checklist must not contain buy/sell/hold as instructions."""
        artifacts = _base_artifacts()
        result = build_personal_health_summary(artifacts)
        for item in result["fix_it_checklist"]:
            item_lower = item.lower()
            # These words are forbidden as advice (not as transaction type labels)
            for forbidden in ["buy ", "sell ", "hold ", "rebalance ", "order "]:
                assert forbidden not in item_lower, f"Found trading advice: {item}"


class TestHealthReportEmptyArtifacts:
    """Empty artifacts should produce unavailable status."""

    def test_empty_artifacts(self):
        result = build_personal_health_summary({})
        assert result["overall_status"] == "unavailable"
        assert result["confidence_level"] == "unavailable"
        assert result["schema_version"] == SCHEMA_VERSION

    def test_none_artifacts(self):
        result = build_personal_health_summary({"e2e_summary": None})
        assert result["overall_status"] == "unavailable"


class TestHealthReportReasonCodeStability:
    """Reason codes must be stable strings suitable for testing and agent consumption."""

    def test_all_reason_codes_are_snake_case(self):
        for code in VALID_REASON_CODES:
            assert code == code.lower(), f"Reason code not lowercase: {code}"
            assert " " not in code, f"Reason code contains space: {code}"

    def test_reason_codes_deduplicated(self):
        """Reason codes should not contain duplicates."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["latest_nav_stale_count"] = 2
        artifacts["nav_coverage_summary"]["qdii_like_count"] = 1
        result = build_personal_health_summary(artifacts)
        assert len(result["reason_codes"]) == len(set(result["reason_codes"]))


class TestHealthReportNavCoverageWiring:
    """Verify NAV coverage summary from reconstruction feeds into health report."""

    def test_nav_coverage_partial_from_summary(self):
        """nav_coverage_summary with partial count → partial_nav_coverage reason code."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 1
        artifacts["nav_coverage_summary"]["nav_coverage_partial_count"] = 2
        artifacts["nav_coverage_summary"]["positions_total"] = 3
        artifacts["nav_coverage_summary"]["positions_estimated"] = 3

        result = build_personal_health_summary(artifacts)
        assert REASON_PARTIAL_NAV_COVERAGE in result["reason_codes"]
        assert result["nav_coverage"]["partial"] == 2
        assert result["nav_coverage"]["full"] == 1

    def test_stale_qdii_nav_from_summary(self):
        """nav_coverage_summary with stale+QDII → stale_nav and qdii_nav_lag."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["latest_nav_stale_count"] = 2
        artifacts["nav_coverage_summary"]["qdii_like_count"] = 1

        result = build_personal_health_summary(artifacts)
        assert REASON_STALE_NAV in result["reason_codes"]
        assert REASON_QDII_NAV_LAG in result["reason_codes"]
        assert result["nav_coverage"]["stale_count"] == 2
        assert result["nav_coverage"]["qdii_like_count"] == 1

    def test_cashflow_only_from_summary(self):
        """nav_coverage_summary with positions_cashflow_only → cashflow_only reason."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 1
        artifacts["nav_coverage_summary"]["positions_cashflow_only"] = 2

        result = build_personal_health_summary(artifacts)
        assert REASON_CASHFLOW_ONLY in result["reason_codes"]
        assert result["valuation_quality"]["cashflow_only_count"] == 2

    def test_manual_review_positions_from_summary(self):
        """nav_coverage_summary with positions_manual_review_required → counted."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["positions_manual_review_required"] = 1

        result = build_personal_health_summary(artifacts)
        assert result["valuation_quality"]["manual_review_count"] == 1

    def test_empty_nav_coverage_summary_still_works(self):
        """Empty or missing nav_coverage_summary should not crash."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"] = {}

        result = build_personal_health_summary(artifacts)
        assert result["schema_version"] == SCHEMA_VERSION
        assert result["nav_coverage"]["full"] == 0
        assert result["nav_coverage"]["partial"] == 0

    def test_latest_only_from_summary(self):
        """nav_coverage_summary with latest_only → counted in nav_coverage."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["nav_coverage_full_count"] = 2
        artifacts["nav_coverage_summary"]["nav_coverage_latest_only_count"] = 1

        result = build_personal_health_summary(artifacts)
        assert result["nav_coverage"]["latest_only"] == 1


class TestHealthReportDoesNotLeakPositionDetails:
    """Even if nav_coverage_summary or portfolio_summary contain private fields,
    the health report must not output them."""

    def test_no_fund_names_in_output(self):
        artifacts = _base_artifacts()
        # Simulate a nav_coverage_summary that accidentally includes private fields
        artifacts["nav_coverage_summary"]["fund_name"] = "某真实基金名称"
        artifacts["nav_coverage_summary"]["amount"] = 12345.67
        artifacts["nav_coverage_summary"]["note"] = "private note"
        artifacts["nav_coverage_summary"]["path"] = "private_data/something"

        result = build_personal_health_summary(artifacts)
        output_str = str(result)
        assert "某真实基金名称" not in output_str
        assert "12345.67" not in output_str
        assert "private note" not in output_str
        assert "private_data" not in output_str

    def test_no_real_amounts_in_output(self):
        """estimated_current_value_total should not appear in reason_codes or checklist."""
        artifacts = _base_artifacts()
        artifacts["nav_coverage_summary"]["estimated_current_value_total"] = 999999.99

        result = build_personal_health_summary(artifacts)
        for code in result["reason_codes"]:
            assert "999999" not in str(code)
        for item in result["fix_it_checklist"]:
            assert "999999" not in str(item)
