"""E2E tests for personal health report integration.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.tools.portfolio.personal_health_report import (
    REASON_FALLBACK_HOLDINGS_USED,
    REASON_MANUAL_REVIEW_TRANSACTIONS,
    REASON_NAME_ONLY_FUNDS,
    REASON_NAV_MISSING,
    REASON_NO_VALID_FUND_CODES,
    REASON_PARTIAL_NAV_COVERAGE,
    REASON_STALE_NAV,
    build_personal_health_summary,
)


def _e2e_summary(
    *,
    transaction_source: str = "alipay",
    portfolio_input_source: str = "reconstructed_from_ledger",
    valid_fund_codes_count: int = 3,
    name_only_count: int = 0,
    reconstruction_status: str = "reconstructed_from_ledger",
) -> dict[str, Any]:
    """Build a synthetic e2e_summary for testing."""
    return {
        "transaction_source": transaction_source,
        "portfolio_input_source": portfolio_input_source,
        "pipeline_steps": {
            "fund_data_snapshot_attempted": True,
            "fund_data_snapshot_status": "attempted",
            "reconstruction_attempted": True,
            "reconstruction_status": reconstruction_status,
            "valid_fund_codes_count": valid_fund_codes_count,
            "name_only_count": name_only_count,
        },
    }


def _nav_coverage(
    *,
    positions_total: int = 3,
    full: int = 3,
    partial: int = 0,
    none: int = 0,
    latest_only: int = 0,
    stale_count: int = 0,
    qdii_like_count: int = 0,
    is_partial: bool = False,
) -> dict[str, Any]:
    return {
        "positions_total": positions_total,
        "positions_estimated": positions_total,
        "positions_cashflow_only": 0,
        "positions_unavailable": none,
        "positions_manual_review_required": 0,
        "nav_coverage_full_count": full,
        "nav_coverage_partial_count": partial,
        "nav_coverage_none_count": none,
        "nav_coverage_latest_only_count": latest_only,
        "latest_nav_stale_count": stale_count,
        "qdii_like_count": qdii_like_count,
        "estimated_current_value_total_is_partial": is_partial,
    }


class TestE2EScenarioACsvOnly:
    """Scenario A: CSV only, no overrides → needs_data."""

    def test_no_valid_fund_codes_needs_data(self):
        artifacts = {
            "e2e_summary": _e2e_summary(
                valid_fund_codes_count=0,
                name_only_count=0,
                reconstruction_status="nav_unavailable",
                portfolio_input_source="unavailable",
            ),
            "nav_coverage_summary": _nav_coverage(positions_total=0, full=0),
            "portfolio_input_transactions_summary": {},
            "identity_summary": {},
            "valuation_summary": {},
        }
        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "needs_data"
        assert REASON_NO_VALID_FUND_CODES in result["reason_codes"]


class TestE2EScenarioBIdentityNoNav:
    """Scenario B: identity overrides, no NAV → needs_data with nav_missing."""

    def test_identity_resolved_no_nav(self):
        artifacts = {
            "e2e_summary": _e2e_summary(
                valid_fund_codes_count=3,
                reconstruction_status="nav_unavailable",
                portfolio_input_source="unavailable",
            ),
            "nav_coverage_summary": _nav_coverage(full=0, none=3),
            "portfolio_input_transactions_summary": {},
            "identity_summary": {"override_validation_warnings": []},
            "valuation_summary": {},
        }
        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "needs_data"
        assert REASON_NAV_MISSING in result["reason_codes"]
        assert result["data_sources"]["identity_source"] == "overrides"


class TestE2EScenarioC2PartialNav:
    """Scenario C2: identity + NAV partial → partial, medium confidence."""

    def test_partial_nav_medium_confidence(self):
        artifacts = {
            "e2e_summary": _e2e_summary(),
            "nav_coverage_summary": _nav_coverage(full=1, partial=2),
            "portfolio_input_transactions_summary": {},
            "identity_summary": {},
            "valuation_summary": {},
        }
        result = build_personal_health_summary(artifacts)
        assert result["overall_status"] == "partial"
        assert result["confidence_level"] == "medium"
        assert REASON_PARTIAL_NAV_COVERAGE in result["reason_codes"]


class TestE2EScenarioD2HoldingsFallback:
    """Scenario D2: holdings fallback → fallback_holdings_used."""

    def test_fallback_holdings(self):
        artifacts = {
            "e2e_summary": _e2e_summary(
                portfolio_input_source="existing_private_portfolio_input",
            ),
            "nav_coverage_summary": _nav_coverage(),
            "portfolio_input_transactions_summary": {},
            "identity_summary": {},
            "valuation_summary": {},
        }
        result = build_personal_health_summary(artifacts)
        assert REASON_FALLBACK_HOLDINGS_USED in result["reason_codes"]
        # Must NOT say reconstructed_from_ledger
        all_text = " ".join(result["reason_codes"] + result["fix_it_checklist"])
        assert "reconstructed_from_ledger" not in all_text


class TestE2EM2PortfolioInputTransactions:
    """M2: portfolio_input.transactions with warnings."""

    def test_manual_review_transactions(self):
        artifacts = {
            "e2e_summary": _e2e_summary(
                transaction_source="portfolio_input.transactions",
            ),
            "nav_coverage_summary": _nav_coverage(),
            "portfolio_input_transactions_summary": {
                "manual_review_required_count": 2,
                "manual_review_count": 2,
            },
            "identity_summary": {},
            "valuation_summary": {},
        }
        result = build_personal_health_summary(artifacts)
        assert REASON_MANUAL_REVIEW_TRANSACTIONS in result["reason_codes"]
        assert result["overall_status"] == "needs_manual_review"


class TestE2EM3StaleQdiiNav:
    """M3: stale NAV / QDII → stale_nav / qdii_nav_lag."""

    def test_stale_qdii(self):
        artifacts = {
            "e2e_summary": _e2e_summary(),
            "nav_coverage_summary": _nav_coverage(stale_count=2, qdii_like_count=1),
            "portfolio_input_transactions_summary": {},
            "identity_summary": {},
            "valuation_summary": {},
        }
        result = build_personal_health_summary(artifacts)
        assert REASON_STALE_NAV in result["reason_codes"]
        checklist_text = " ".join(result["fix_it_checklist"])
        assert "NAV freshness" in checklist_text


class TestE2EV0105Regression:
    """v0.10.5 regression: existing fields must remain unchanged."""

    def test_existing_e2e_summary_fields_unchanged(self):
        """Health report addition must not change existing e2e_summary fields."""
        # This test verifies that the personal_health_report is an additive
        # field — existing fields (run_id, status, pipeline_steps, etc.)
        # are not modified by the health report builder.
        artifacts = {
            "e2e_summary": _e2e_summary(),
            "nav_coverage_summary": _nav_coverage(),
            "portfolio_input_transactions_summary": {},
            "identity_summary": {},
            "valuation_summary": {},
        }
        result = build_personal_health_summary(artifacts)
        # The result should have the health report schema
        assert "schema_version" in result
        assert "overall_status" in result
        assert "confidence_level" in result
        # The original e2e_summary data should not be modified
        assert artifacts["e2e_summary"]["pipeline_steps"]["valid_fund_codes_count"] == 3
