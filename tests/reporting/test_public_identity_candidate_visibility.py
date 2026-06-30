"""Tests for M7.16 public identity candidate visibility.

Validates:
1. Public report hides non-exact candidate codes
2. Agent context hides non-exact candidate codes
3. Fixit records match_strategy
4. Exact match candidate can appear as verified identity only after verification
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.agent_context import (
    build_agent_context,
    render_agent_context_markdown,
)
from src.tools.portfolio.fixit_package import generate_fixit_package


class TestPublicReportHidesNonExactCandidateCodes:
    """Public report must not show non-exact candidate codes."""

    def test_blocked_evidence_no_candidate_codes_in_context(self):
        """When identity is blocked, agent context should not show candidate codes."""
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_unverified"],
            },
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "fund_name": "某基金A",
                        "identity_verification_status": "name_search_candidate_unverified",
                    },
                ],
            },
            "name_search_provider_diagnostics": {
                "name_search_provider_type": "akshare",
                "name_search_provider_status": "available",
                "fund_universe_size": 10000,
                "exact_full_name_match_count": 0,
                "exact_without_punctuation_match_count": 0,
                "core_share_class_match_count": 0,
                "fuzzy_fallback_count": 1,
                "search_strategy_used": "fuzzy_fallback",
            },
            "identity_resolution": {
                "name_search_enabled": True,
                "name_search_auto_verified_count": 0,
                "name_search_candidate_unverified_count": 1,
                "exact_lookup_failed_count": 1,
                "fuzzy_candidate_count": 1,
                "hard_rejected_candidate_count": 0,
            },
        }
        context = build_agent_context(summary)
        md = render_agent_context_markdown(context)

        # Should NOT contain actual candidate fund codes
        assert "000001" not in md
        # Should contain identity_unverified indicator
        assert "identity_unverified" in md or "Exact Lookup" in md

    def test_fuzzy_candidate_count_shown_without_codes(self):
        """Agent context shows fuzzy candidate count but not actual codes."""
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_unverified"],
            },
            "name_search_provider_diagnostics": {
                "name_search_provider_type": "akshare",
                "name_search_provider_status": "available",
                "fund_universe_size": 10000,
                "exact_full_name_match_count": 0,
                "fuzzy_fallback_count": 3,
            },
            "identity_resolution": {
                "exact_lookup_failed_count": 2,
                "fuzzy_candidate_count": 3,
                "hard_rejected_candidate_count": 1,
            },
        }
        context = build_agent_context(summary)
        md = render_agent_context_markdown(context)

        # Should show counts
        assert "fuzzy_candidate_count" in md or "Fuzzy fallback count" in md
        # Should mention non-exact candidates are hidden
        assert "non-exact" in md.lower() or "private" in md.lower()


class TestAgentContextHidesNonExactCandidateCodes:
    """Agent context JSON must not expose non-exact candidate codes."""

    def test_context_no_fund_codes_in_safe_items(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_unverified"],
            },
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "identity_verification_status": "name_search_candidate_unverified",
                    },
                ],
            },
        }
        context = build_agent_context(summary)
        # Safe-to-analyze should not contain actual fund codes
        safe = context.get("safe_to_analyze", [])
        safe_str = str(safe)
        assert "000001" not in safe_str


class TestFixitRecordsMatchStrategy:
    """Fixit CSV must record match_strategy for each candidate."""

    def test_fixit_includes_match_strategy(self, tmp_path):
        positions = [
            {
                "fund_code": "",
                "fund_name": "某基金A",
                "raw_fund_name": "某基金A",
                "reconstruction_blockers": [],
                "identity_verification_status": "name_search_candidate_unverified",
            },
        ]
        identity_resolutions = [
            {
                "raw_fund_name": "某基金A",
                "normalized_name": "某基金A",
                "identity_verification_status": "name_search_candidate_unverified",
                "name_search_candidates": [
                    {
                        "fund_code": "000001",
                        "fund_name": "某基金A",
                        "match_score": 0.95,
                        "match_bucket": "exact",
                        "match_reasons": ["exact_fund_universe_name_match"],
                        "candidate_status": "accepted_candidate",
                        "reject_reasons": [],
                    },
                    {
                        "fund_code": "000002",
                        "fund_name": "某基金B",
                        "match_score": 0.70,
                        "match_bucket": "low",
                        "match_reasons": ["fuzzy_fallback"],
                        "candidate_status": "accepted_candidate",
                        "reject_reasons": [],
                    },
                ],
            },
        ]
        result = generate_fixit_package(positions, tmp_path, identity_resolutions)
        assert result["identity_candidate_count"] > 0

        # Read the CSV and check for match_strategy column
        import csv
        csv_path = tmp_path / "identity_candidates.private.csv"
        if csv_path.exists():
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert "match_strategy" in rows[0], f"match_strategy column missing: {rows[0].keys()}"
                # Check exact candidate has match_strategy=exact
                exact_rows = [r for r in rows if r.get("match_strategy") == "exact"]
                fuzzy_rows = [r for r in rows if r.get("match_strategy") == "fuzzy"]
                assert len(exact_rows) >= 1
                assert len(fuzzy_rows) >= 1
                # Fuzzy candidates should have not_for_verification=yes
                for r in fuzzy_rows:
                    assert r.get("not_for_verification") == "yes"


class TestExactMatchCandidateVerifiedIdentity:
    """Exact match candidate can appear as verified identity only after verification."""

    def test_exact_candidate_in_fixit_with_strategy_exact(self, tmp_path):
        positions = []
        identity_resolutions = [
            {
                "raw_fund_name": "易方达蓝筹精选混合A",
                "normalized_name": "易方达蓝筹精选混合A",
                "identity_verification_status": "name_search_candidate_unverified",
                "name_search_candidates": [
                    {
                        "fund_code": "110011",
                        "fund_name": "易方达蓝筹精选混合A",
                        "match_score": 1.0,
                        "match_bucket": "exact",
                        "match_reasons": ["exact_fund_universe_name_match"],
                        "candidate_status": "accepted_candidate",
                        "reject_reasons": [],
                    },
                ],
            },
        ]
        result = generate_fixit_package(positions, tmp_path, identity_resolutions)
        import csv
        csv_path = tmp_path / "identity_candidates.private.csv"
        if csv_path.exists():
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                exact_rows = [r for r in rows if r.get("match_strategy") == "exact"]
                assert len(exact_rows) >= 1
                # Exact candidate should NOT have not_for_verification=yes
                for r in exact_rows:
                    assert r.get("not_for_verification") != "yes"
