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
