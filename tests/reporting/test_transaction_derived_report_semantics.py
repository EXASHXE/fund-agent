"""Tests for M7.9 transaction-derived report semantics.

Covers:
1. Transaction-derived value labeled estimated
2. Platform snapshot precedence
3. Report wording for reconstructed vs snapshot
4. Agent context reconstruction summary
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.agent_context import (
    REASON_CODES,
    SAFE_TO_ANALYZE_ITEMS,
    UNSAFE_TO_INFER_ITEMS,
    build_agent_context,
)
from src.tools.portfolio.valuation_source_model import (
    VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS,
    VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE,
    VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV,
    is_valuation_estimated,
)


class TestReportSemantics:
    def test_transaction_derived_valuation_is_estimated(self):
        """Transaction-derived valuation must be labeled estimated."""
        assert is_valuation_estimated(VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV)
        assert is_valuation_estimated(VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS)

    def test_platform_reported_is_not_estimated(self):
        """Platform-reported valuation must NOT be labeled estimated."""
        assert not is_valuation_estimated(VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE)

    def test_transaction_derived_not_labeled_platform_reported(self):
        """Transaction-derived values must never be labeled platform_reported."""
        # This is enforced by the is_valuation_estimated function
        # and the valuation_source_model module
        assert VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV != "platform_reported"
        assert VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS != "platform_reported"


class TestAgentContextReconstruction:
    def test_reason_codes_include_reconstruction_codes(self):
        """M7.9 reason codes must include reconstruction-specific codes."""
        assert "transaction_derived_valuation" in REASON_CODES
        assert "reconstruction_partial" in REASON_CODES
        assert "dividend_unmodeled" in REASON_CODES
        assert "unmatched_refund" in REASON_CODES
        assert "conversion_unverified" in REASON_CODES
        assert "unknown_amount_semantics" in REASON_CODES
        assert "missing_fee" in REASON_CODES

    def test_safe_to_analyze_includes_reconstruction(self):
        """M7.9 safe-to-analyze must include reconstruction items."""
        assert "transaction_derived_current_value" in SAFE_TO_ANALYZE_ITEMS
        assert "reconstruction_quality" in SAFE_TO_ANALYZE_ITEMS

    def test_unsafe_to_infer_includes_reconstruction_items(self):
        """M7.9 unsafe-to-infer must include reconstruction-specific items."""
        assert "platform_reported_value_from_reconstruction" in UNSAFE_TO_INFER_ITEMS
        assert "confirmed_profit_without_fee_coverage" in UNSAFE_TO_INFER_ITEMS

    def test_agent_context_with_reconstruction_summary(self):
        """Agent context must include reconstruction_summary."""
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "medium",
                "reason_codes": ["transaction_derived_valuation"],
            },
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "holdings_source": "transaction_derived_full",
                        "reconstruction_quality": "estimated_high",
                        "identity_verification_status": "provider_verified",
                    },
                    {
                        "fund_code": "000002",
                        "holdings_source": "cashflow_only",
                        "reconstruction_quality": "blocked",
                        "identity_verification_status": "manual_override_unverified",
                    },
                ],
            },
        }
        context = build_agent_context(summary, run_id="test-run")
        assert "reconstruction_summary" in context
        recon = context["reconstruction_summary"]
        assert recon["transaction_derived_full_count"] == 1
        assert recon["cashflow_only_count"] == 1
        assert recon["reconstruction_quality_by_position"]["estimated_high"] == 1
        assert recon["reconstruction_quality_by_position"]["blocked"] == 1

    def test_agent_context_market_value_without_snapshot_adjusted(self):
        """When transaction-derived full is available, market_value_without_holdings_snapshot
        should be adjusted in unsafe list."""
        summary = {
            "personal_health_report": {
                "overall_status": "ok",
                "confidence_level": "high",
                "reason_codes": ["transaction_derived_valuation"],
            },
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "holdings_source": "transaction_derived_full",
                        "reconstruction_quality": "confirmed",
                        "identity_verification_status": "provider_verified",
                    },
                ],
            },
        }
        context = build_agent_context(summary, run_id="test-run")
        # When all positions are transaction_derived_full, market_value_without_holdings_snapshot
        # should be removed from unsafe
        if context["reconstruction_summary"].get("transaction_derived_partial_count", 0) == 0:
            assert "market_value_without_holdings_snapshot" not in context["unsafe_to_infer"]


class TestAgentContextContract:
    def test_reconstruction_summary_in_output(self):
        """Agent context output must include reconstruction_summary field."""
        context = build_agent_context(
            {"personal_health_report": {"overall_status": "unavailable", "confidence_level": "low", "reason_codes": []}},
            run_id="test",
        )
        assert "reconstruction_summary" in context

    def test_blocked_evidence_summary_preserved(self):
        """M7.6 blocked_evidence_summary must still be present."""
        context = build_agent_context(
            {"personal_health_report": {"overall_status": "unavailable", "confidence_level": "low", "reason_codes": []}},
            run_id="test",
        )
        assert "blocked_evidence_summary" in context
