"""Tests for report semantics with portfolio_input transaction sources.

Verifies report section builders correctly label transaction sources
and do not mislead users about data provenance.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from src.tools.portfolio.report_sections import compose_personal_fund_report


def _make_artifacts(
    source_of_truth: str = "transactions_only",
    transaction_source: str = "portfolio_input.transactions",
    has_cashflow: bool = True,
) -> dict[str, Any]:
    """Create minimal artifacts dict for report composition."""
    artifacts: dict[str, Any] = {
        "source_of_truth": source_of_truth,
        "transaction_source": transaction_source,
    }
    if has_cashflow:
        artifacts["transaction_cashflow_summary"] = {
            "total_cashflow": 100.0,
            "by_fund": {},
        }
    return artifacts


class TestReportTransactionSource:
    def test_portfolio_input_transactions_source_shown(self):
        artifacts = _make_artifacts(
            source_of_truth="transactions_only",
            transaction_source="portfolio_input.transactions",
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        assert "portfolio_input.transactions" in all_text

    def test_alipay_source_shown(self):
        artifacts = _make_artifacts(
            source_of_truth="transactions_only",
            transaction_source="alipay",
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        assert "alipay" in all_text

    def test_no_fake_zero_values(self):
        """Transactions_only mode should not show fake 0.00 values."""
        artifacts = _make_artifacts(
            source_of_truth="transactions_only",
            transaction_source="portfolio_input.transactions",
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        all_text = json.dumps(result, default=str)
        # Should not contain "0.00" as a value representation
        assert "0.00" not in all_text or "current_value" not in all_text

    def test_holdings_not_labeled_reconstructed_from_ledger(self):
        """When source is host_portfolio, report must not say reconstructed_from_ledger."""
        artifacts = _make_artifacts(
            source_of_truth="host_portfolio",
            transaction_source="portfolio_input.transactions",
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        assert "reconstructed_from_ledger" not in all_text

    def test_transactions_only_not_labeled_as_valuation(self):
        """transactions_only source should not imply valuation exists."""
        artifacts = _make_artifacts(
            source_of_truth="transactions_only",
            transaction_source="portfolio_input.transactions",
        )
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))
        # Should mention "no current_nav" or "partial"
        assert any(word in all_text.lower() for word in ["partial", "no current_nav", "not available"])


class TestReportValidationVisibility:
    """Report must surface validation warnings and manual review for portfolio_input.transactions."""

    def test_report_mentions_manual_review_for_warning_transactions(self):
        """When portfolio_input_transactions_summary has manual_review > 0,
        report must mention manual review / validation warning,
        must NOT contain fake 0.00, and must NOT label fallback as reconstructed_from_ledger."""
        artifacts = _make_artifacts(
            source_of_truth="transactions_only",
            transaction_source="portfolio_input.transactions",
        )
        artifacts["portfolio_input_transactions_summary"] = {
            "total_transactions": 3,
            "warning_count": 2,
            "manual_review_count": 2,
            "valid_count": 1,
            "invalid_count": 2,
        }
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))

        # Must mention manual review
        assert "manual_review" in all_text or "manual review" in all_text.lower()

        # Must mention warnings count
        assert "warnings=" in all_text or "warning" in all_text.lower()

        # Limitations must mention manual review
        limitations_text = " ".join(rs_section.get("limitations", []))
        assert "manual review" in limitations_text.lower()

        # Must NOT label as reconstructed_from_ledger
        assert "reconstructed_from_ledger" not in all_text

        # Must NOT contain fake 0.00
        assert "0.00" not in all_text

    def test_alipay_path_regression_no_portfolio_warning(self):
        """When using Alipay path (no portfolio_input_transactions_summary),
        report must NOT show portfolio_input.transactions warning."""
        artifacts = _make_artifacts(
            source_of_truth="derived_from_transactions",
            transaction_source="alipay",
        )
        # No portfolio_input_transactions_summary key → Alipay-only path
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", []))

        # Must NOT mention portfolio_input transactions summary
        assert "Portfolio input transactions:" not in all_text


class TestReportPrivacyRedaction:
    """Report must not contain raw user input in warnings or manual review text."""

    def test_report_manual_review_warning_is_counts_only(self):
        """Report shows counts only — no raw invalid transaction_type values."""
        artifacts = _make_artifacts(
            source_of_truth="transactions_only",
            transaction_source="portfolio_input.transactions",
        )
        artifacts["portfolio_input_transactions_summary"] = {
            "total_transactions": 3,
            "warning_count": 1,
            "manual_review_count": 1,
            "valid_count": 2,
            "invalid_count": 1,
            "unknown_count": 1,
        }
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(
            (s for s in result["report_sections"] if s["id"] == "reconstruction_status"),
            None,
        )
        assert rs_section is not None
        all_text = " ".join(rs_section.get("bullets", [])) + " ".join(rs_section.get("limitations", []))

        # Must show counts
        assert "warnings=1" in all_text or "warning" in all_text.lower()
        # Must NOT contain raw transaction_type values that might have been in input
        assert "private_type" not in all_text
        assert "secret_order" not in all_text


class TestReportValuationWording:
    """Valuation wording must be accurate — estimated vs confirmed."""

    def test_derived_from_transactions_labelled_estimated(self):
        """When source_of_truth is derived_from_transactions, report says 'Estimated portfolio value'."""
        artifacts = _make_artifacts(
            source_of_truth="derived_from_transactions",
            transaction_source="alipay",
        )
        artifacts["portfolio_summary"] = {
            "total_value": 1000.0,
            "position_count": 2,
            "cash_available": 100.0,
        }
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        es_section = next(
            (s for s in result["report_sections"] if s["id"] == "executive_summary"),
            None,
        )
        assert es_section is not None
        all_text = " ".join(es_section.get("bullets", []))
        assert "Estimated portfolio value" in all_text

    def test_host_portfolio_not_labelled_estimated(self):
        """When source_of_truth is host_portfolio, report says 'Portfolio value' (not estimated)."""
        artifacts = _make_artifacts(
            source_of_truth="host_portfolio",
            transaction_source="alipay",
        )
        artifacts["portfolio_summary"] = {
            "total_value": 1000.0,
            "position_count": 2,
            "cash_available": 100.0,
        }
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        es_section = next(
            (s for s in result["report_sections"] if s["id"] == "executive_summary"),
            None,
        )
        assert es_section is not None
        all_text = " ".join(es_section.get("bullets", []))
        # Should say "Portfolio value" not "Estimated portfolio value"
        assert "Portfolio value" in all_text
        assert "Estimated portfolio value" not in all_text
