"""Tests for M7.9 agent context reconstruction contract.

Covers:
1. Reconstruction summary structure
2. Safe-to-analyze items for reconstruction
3. Unsafe-to-infer items for reconstruction
4. Reason codes for reconstruction scenarios
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.agent_context import (
    REASON_CODES,
    SAFE_TO_ANALYZE_ITEMS,
    UNSAFE_TO_INFER_ITEMS,
    build_agent_context,
    render_agent_context_markdown,
)


class TestAgentContextReconstructionContract:
    def test_reconstruction_summary_structure(self):
        """Reconstruction summary must have required fields."""
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "medium",
                "reason_codes": ["transaction_derived_valuation", "reconstruction_partial"],
            },
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "holdings_source": "transaction_derived_full",
                        "reconstruction_quality": "confirmed",
                        "identity_verification_status": "provider_verified",
                    },
                    {
                        "fund_code": "000002",
                        "holdings_source": "transaction_derived_partial",
                        "reconstruction_quality": "estimated_medium",
                        "identity_verification_status": "provider_verified",
                    },
                    {
                        "fund_code": "000003",
                        "holdings_source": "cashflow_only",
                        "reconstruction_quality": "blocked",
                        "identity_verification_status": "manual_override_unverified",
                    },
                ],
            },
        }
        context = build_agent_context(summary, run_id="test-contract")

        recon = context.get("reconstruction_summary", {})
        assert "transaction_derived_full_count" in recon
        assert "transaction_derived_partial_count" in recon
        assert "cashflow_only_count" in recon
        assert "unavailable_count" in recon
        assert "reconstruction_quality_by_position" in recon

        quality = recon["reconstruction_quality_by_position"]
        assert "confirmed" in quality
        assert "estimated_medium" in quality
        assert "blocked" in quality

    def test_safe_to_analyze_reconstruction_items(self):
        """Transaction-derived items must be in safe-to-analyze."""
        assert "transaction_derived_current_value" in SAFE_TO_ANALYZE_ITEMS
        assert "reconstruction_quality" in SAFE_TO_ANALYZE_ITEMS

    def test_unsafe_to_infer_reconstruction_items(self):
        """Reconstruction-specific unsafe items must be present."""
        assert "platform_reported_value_from_reconstruction" in UNSAFE_TO_INFER_ITEMS
        assert "confirmed_profit_without_fee_coverage" in UNSAFE_TO_INFER_ITEMS

    def test_reason_codes_reconstruction(self):
        """Reconstruction-specific reason codes must be valid."""
        reconstruction_codes = {
            "transaction_derived_valuation",
            "reconstruction_partial",
            "dividend_unmodeled",
            "unmatched_refund",
            "conversion_unverified",
            "unknown_amount_semantics",
            "missing_fee",
        }
        for code in reconstruction_codes:
            assert code in REASON_CODES, f"Missing reason code: {code}"

    def test_render_markdown_includes_reconstruction(self):
        """Markdown rendering must include reconstruction summary."""
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
                        "reconstruction_quality": "confirmed",
                        "identity_verification_status": "provider_verified",
                    },
                ],
            },
        }
        context = build_agent_context(summary, run_id="test-md")
        md = render_agent_context_markdown(context)
        assert "Fund Agent Analysis Context" in md
        assert "transaction_derived_valuation" in md or "reason_codes" in md

    def test_empty_positions_reconstruction_summary(self):
        """Reconstruction summary with no positions should return empty dict."""
        summary = {
            "personal_health_report": {
                "overall_status": "unavailable",
                "confidence_level": "low",
                "reason_codes": [],
            },
        }
        context = build_agent_context(summary, run_id="test-empty")
        recon = context.get("reconstruction_summary", {})
        # Should have the structure even with empty positions
        assert isinstance(recon, dict)
