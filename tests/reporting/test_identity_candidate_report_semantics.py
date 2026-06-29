"""Tests for M7.13 identity candidate report semantics.

Validates that public reports hide cache candidate codes and
provider failures are structurally recorded.
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.agent_context import build_agent_context, render_agent_context_markdown
from src.tools.portfolio.evidence_visibility import is_identity_blocked


class TestPublicReportHidesCacheCandidateCodes:
    """Public report must not display unverified candidate codes from cache."""

    def test_blocked_identity_status_includes_name_only(self):
        """name_only status must block identity display."""
        assert is_identity_blocked({"identity_verification_status": "name_only"})

    def test_blocked_identity_status_includes_name_search_unverified(self):
        """name_search_candidate_unverified status must block identity display."""
        assert is_identity_blocked({"identity_verification_status": "name_search_candidate_unverified"})

    def test_agent_context_markdown_no_candidate_codes(self):
        """Rendered markdown must not contain raw candidate codes."""
        summary = {
            "personal_health_report": {
                "overall_status": "needs_data",
                "confidence_level": "unavailable",
                "reason_codes": ["provider_name_search_network_error", "identity_candidate_cache_missing"],
            },
            "name_search_provider_diagnostics": {
                "provider_chain_enabled": True,
                "providers_attempted": ["local_cache", "akshare"],
                "providers_succeeded": [],
                "providers_failed": ["local_cache", "akshare"],
                "fallback_used": False,
            },
            "local_cache_diagnostics": {
                "name_search_provider_type": "local_cache",
                "name_search_provider_status": "cache_missing",
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")
        md = render_agent_context_markdown(context)

        # Must contain reason codes but not candidate codes
        assert "provider_name_search_network_error" in md
        assert "identity_candidate_cache_missing" in md
        # Must not contain any 6-digit codes (candidate codes)
        import re
        codes = re.findall(r'\b\d{6}\b', md)
        assert len(codes) == 0, f"Found candidate codes in public report: {codes}"


class TestProviderFailureStructuredRecording:
    """Provider failures must be structurally recorded, not silent."""

    def test_network_error_in_reason_codes(self):
        summary = {
            "personal_health_report": {
                "overall_status": "needs_data",
                "confidence_level": "unavailable",
                "reason_codes": ["provider_name_search_network_error"],
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")
        assert "provider_name_search_network_error" in context["reason_codes"]

    def test_chain_failed_in_reason_codes(self):
        summary = {
            "personal_health_report": {
                "overall_status": "needs_data",
                "confidence_level": "unavailable",
                "reason_codes": ["name_search_provider_chain_failed"],
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")
        assert "name_search_provider_chain_failed" in context["reason_codes"]
