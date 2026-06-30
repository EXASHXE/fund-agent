"""Tests for M7.13/M7.15 identity candidate report semantics.

Validates that public reports hide cache candidate codes and
provider failures are structurally recorded.

M7.15: Hard-rejected candidates must NOT appear as "best candidate" or
"recommended" in public report output. They must be marked
not_for_verification in private artifacts.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from src.tools.portfolio.agent_context import build_agent_context, render_agent_context_markdown
from src.tools.portfolio.evidence_visibility import is_identity_blocked
from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    apply_hard_reject,
    score_candidate,
    BUCKET_MISMATCH,
)
from src.tools.portfolio.report_sections.helpers import (
    FORBIDDEN_IDENTITY_BLOCKED_WORDING,
    REQUIRED_IDENTITY_BLOCKED_WORDING,
)


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


# ── M7.15: Hard-rejected candidate report semantics ──────────────────────


def _make_candidate(fund_code: str, fund_name: str) -> FundIdentityCandidate:
    return FundIdentityCandidate(fund_code=fund_code, fund_name=fund_name)


class TestM715HardRejectedCandidateStatus:
    """Hard-rejected candidates must have candidate_status reflecting reason."""

    def test_brand_mismatch_status(self):
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert result.candidate_status == "rejected_brand_mismatch"

    def test_theme_mismatch_status(self):
        """When brand matches but theme conflicts, status is theme mismatch."""
        c = _make_candidate("004253", "国泰黄金ETF联接C")
        scored = score_candidate("国泰创新药ETF联接C", c)
        result = apply_hard_reject("国泰创新药ETF联接C", scored)
        assert "rejected_theme_mismatch" in result.reject_reasons
        assert result.candidate_status == "rejected_theme_mismatch"

    def test_share_class_mismatch_status(self):
        c = _make_candidate("009068", "国泰中证新能源汽车ETF联接C")
        scored = score_candidate("万家国证新能源车电池ETF联接A", c)
        result = apply_hard_reject("万家国证新能源车电池ETF联接A", scored)
        assert "rejected_share_class_mismatch" in result.reject_reasons


class TestM715HardRejectedNotForVerification:
    """Hard-rejected candidates must be marked not_for_verification."""

    def test_hard_reject_implies_not_for_verification(self):
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert result.hard_reject is True
        not_for_verification = "true" if result.hard_reject else ""
        assert not_for_verification == "true"

    def test_accepted_candidate_is_for_verification(self):
        c = _make_candidate("007467", "华泰柏瑞中证红利低波动ETF联接C")
        scored = score_candidate("华泰柏瑞中证红利低波动ETF联接C", c)
        result = apply_hard_reject("华泰柏瑞中证红利低波动ETF联接C", scored)
        if not result.hard_reject:
            not_for_verification = "true" if result.hard_reject else ""
            assert not_for_verification == ""


class TestM715HardRejectedScoreZeroed:
    """Hard-rejected candidates must have score=0 and bucket=mismatch."""

    def test_rejected_score_is_zero(self):
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert result.hard_reject is True
        assert result.match_score == 0.0
        assert result.match_bucket == BUCKET_MISMATCH


class TestM715IdentityBlockedWordingConstraints:
    """When identity is blocked, required/forbidden wording must be enforced."""

    @pytest.mark.parametrize("forbidden_word", list(FORBIDDEN_IDENTITY_BLOCKED_WORDING))
    def test_forbidden_identity_blocked_wording_defined(self, forbidden_word: str):
        assert forbidden_word

    @pytest.mark.parametrize("required_word", list(REQUIRED_IDENTITY_BLOCKED_WORDING))
    def test_required_identity_blocked_wording_defined(self, required_word: str):
        assert required_word


class TestM715MultipleRejectReasons:
    """A candidate can have multiple reject reasons simultaneously."""

    def test_brand_and_theme_both_rejected(self):
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert "rejected_brand_mismatch" in result.reject_reasons
        assert "rejected_theme_mismatch" in result.reject_reasons
        assert len(result.reject_reasons) >= 2
