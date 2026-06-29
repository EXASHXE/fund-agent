"""Tests for M7.13 agent context identity discovery contract.

Validates that agent_context correctly includes provider chain diagnostics,
local cache info, and new reason codes.
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.agent_context import (
    REASON_CODES,
    SAFE_TO_ANALYZE_ITEMS,
    UNSAFE_TO_INFER_ITEMS,
    build_agent_context,
)


class TestReasonCodesContract:
    """New M7.13 reason codes must be in the stable enumeration."""

    def test_provider_name_search_network_error_in_reason_codes(self):
        assert "provider_name_search_network_error" in REASON_CODES

    def test_provider_name_search_unavailable_in_reason_codes(self):
        assert "provider_name_search_unavailable" in REASON_CODES

    def test_identity_candidate_cache_missing_in_reason_codes(self):
        assert "identity_candidate_cache_missing" in REASON_CODES

    def test_identity_candidate_cache_used_in_reason_codes(self):
        assert "identity_candidate_cache_used" in REASON_CODES

    def test_identity_candidates_generated_from_cache_in_reason_codes(self):
        assert "identity_candidates_generated_from_cache" in REASON_CODES

    def test_name_search_provider_chain_failed_in_reason_codes(self):
        assert "name_search_provider_chain_failed" in REASON_CODES


class TestSafeToAnalyzeContract:
    """identity_candidate_cache must be in safe-to-analyze."""

    def test_identity_candidate_cache_in_safe_to_analyze(self):
        assert "identity_candidate_cache" in SAFE_TO_ANALYZE_ITEMS


class TestAgentContextProviderChainDiagnostics:
    """agent_context must include provider chain diagnostics."""

    def test_chain_diagnostics_in_context(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "medium",
                "reason_codes": ["provider_name_search_network_error"],
            },
            "name_search_provider_diagnostics": {
                "provider_chain_enabled": True,
                "providers_attempted": ["local_cache", "akshare"],
                "providers_succeeded": ["local_cache"],
                "providers_failed": ["akshare"],
                "fallback_used": False,
            },
            "local_cache_diagnostics": {
                "name_search_provider_type": "local_cache",
                "name_search_provider_status": "available",
                "name_search_provider_entry_count": 10,
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")

        ns_diag = context["name_search_diagnostics"]
        assert ns_diag.get("provider_chain_enabled") is True
        assert "local_cache" in ns_diag.get("providers_succeeded", [])
        assert "akshare" in ns_diag.get("providers_failed", [])
        assert ns_diag.get("local_cache_present") is True
        assert ns_diag.get("local_cache_candidate_count") == 10
        assert ns_diag.get("network_provider_status") == "network_error"

    def test_local_cache_question_for_missing_cache(self):
        """When cache is missing, recommended questions must include cache guidance."""
        summary = {
            "personal_health_report": {
                "overall_status": "needs_data",
                "confidence_level": "unavailable",
                "reason_codes": [
                    "name_search_provider_chain_failed",
                    "identity_candidate_cache_missing",
                ],
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")
        questions = context["recommended_agent_questions"]
        assert any("local identity candidate cache" in q.lower() or "candidate cache" in q.lower() for q in questions)
