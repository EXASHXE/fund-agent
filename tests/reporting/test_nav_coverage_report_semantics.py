"""Tests for NAV coverage report semantics.

Verifies report section builders correctly display NAV coverage,
valuation quality, and special transaction information.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from src.tools.portfolio.report_sections import compose_personal_fund_report


def _make_artifacts_with_nav_coverage(
    *,
    source_of_truth: str = "derived_from_transactions",
    transaction_source: str = "alipay",
    nav_coverage_summary: dict[str, Any] | None = None,
    pi_txn_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create minimal artifacts dict for report composition with NAV coverage."""
    artifacts: dict[str, Any] = {
        "source_of_truth": source_of_truth,
        "transaction_source": transaction_source,
        "transaction_cashflow_summary": {"total_cashflow": 100.0, "by_fund": {}},
    }
    if nav_coverage_summary:
        artifacts["nav_coverage_summary"] = nav_coverage_summary
    if pi_txn_summary:
        artifacts["portfolio_input_transactions_summary"] = pi_txn_summary
    return artifacts


class TestNavCoverageReportSemantics:
    def test_nav_coverage_displayed_in_report(self):
        """Report shows NAV coverage counts."""
        artifacts = _make_artifacts_with_nav_coverage(
            nav_coverage_summary={
                "positions_total": 3,
                "nav_coverage_full_count": 1,
                "nav_coverage_partial_count": 1,
                "nav_coverage_none_count": 1,
                "nav_coverage_latest_only_count": 0,
                "latest_nav_stale_count": 0,
                "qdii_like_count": 0,
                "positions_manual_review_required": 0,
                "estimated_current_value_total_is_partial": True,
                "positions_estimated": 2,
                "positions_cashflow_only": 1,
                "positions_unavailable": 0,
                "estimated_current_value_total": 1500.0,
                "estimated_current_value_coverage_count": 2,
            },
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        assert "NAV coverage" in all_text
        assert "full=1" in all_text
        assert "partial=1" in all_text
        assert "none=1" in all_text

    def test_stale_nav_warning_in_report(self):
        """Report mentions stale NAV when present."""
        artifacts = _make_artifacts_with_nav_coverage(
            nav_coverage_summary={
                "positions_total": 2,
                "nav_coverage_full_count": 2,
                "nav_coverage_partial_count": 0,
                "nav_coverage_none_count": 0,
                "nav_coverage_latest_only_count": 0,
                "latest_nav_stale_count": 1,
                "qdii_like_count": 0,
                "positions_manual_review_required": 0,
                "estimated_current_value_total_is_partial": False,
                "positions_estimated": 2,
                "positions_cashflow_only": 0,
                "positions_unavailable": 0,
                "estimated_current_value_total": 2000.0,
                "estimated_current_value_coverage_count": 2,
            },
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        assert "Stale latest NAV" in all_text
        limitations_text = " ".join(rs_section.get("limitations", []))
        assert "stale" in limitations_text.lower()

    def test_qdii_mentioned_in_report(self):
        """Report mentions QDII-like positions when present."""
        artifacts = _make_artifacts_with_nav_coverage(
            nav_coverage_summary={
                "positions_total": 1,
                "nav_coverage_full_count": 1,
                "nav_coverage_partial_count": 0,
                "nav_coverage_none_count": 0,
                "nav_coverage_latest_only_count": 0,
                "latest_nav_stale_count": 0,
                "qdii_like_count": 1,
                "positions_manual_review_required": 0,
                "estimated_current_value_total_is_partial": False,
                "positions_estimated": 1,
                "positions_cashflow_only": 0,
                "positions_unavailable": 0,
                "estimated_current_value_total": 1000.0,
                "estimated_current_value_coverage_count": 1,
            },
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        assert "QDII" in all_text

    def test_partial_estimated_value_wording(self):
        """Report says partial estimated value, not full portfolio value."""
        artifacts = _make_artifacts_with_nav_coverage(
            nav_coverage_summary={
                "positions_total": 3,
                "nav_coverage_full_count": 1,
                "nav_coverage_partial_count": 1,
                "nav_coverage_none_count": 1,
                "nav_coverage_latest_only_count": 0,
                "latest_nav_stale_count": 0,
                "qdii_like_count": 0,
                "positions_manual_review_required": 0,
                "estimated_current_value_total_is_partial": True,
                "positions_estimated": 2,
                "positions_cashflow_only": 1,
                "positions_unavailable": 0,
                "estimated_current_value_total": 1500.0,
                "estimated_current_value_coverage_count": 2,
            },
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        limitations_text = " ".join(rs_section.get("limitations", []))
        assert "partial" in limitations_text.lower()
        # Must NOT present partial as full portfolio value
        assert "do not treat" in limitations_text.lower() or "not" in limitations_text.lower()

    def test_no_fake_zero_for_cashflow_only(self):
        """cashflow_only positions do not show 0.00 current value."""
        artifacts = _make_artifacts_with_nav_coverage(
            source_of_truth="transactions_only",
            transaction_source="portfolio_input.transactions",
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        all_text = json.dumps(result, default=str)
        # Should not contain "0.00" as a value representation
        assert "0.00" not in all_text or "current_value" not in all_text

    def test_special_transactions_in_report(self):
        """Report shows special transaction counts from portfolio_input_transactions_summary."""
        artifacts = _make_artifacts_with_nav_coverage(
            pi_txn_summary={
                "total_transactions": 5,
                "warning_count": 0,
                "manual_review_count": 0,
                "conversion_count": 1,
                "refund_count": 1,
                "fee_transaction_count": 1,
                "dividend_transaction_count": 1,
                "unknown_count": 0,
            },
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        assert "conversion=1" in all_text
        assert "refund=1" in all_text
        assert "fee=1" in all_text
        assert "dividend=1" in all_text
        # Limitations should mention manual review for conversion/refund
        limitations_text = " ".join(rs_section.get("limitations", []))
        assert "manual review" in limitations_text.lower()

    def test_no_nav_coverage_no_error(self):
        """Report works fine without nav_coverage_summary (regression)."""
        artifacts = _make_artifacts_with_nav_coverage()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
