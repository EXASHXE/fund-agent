"""Tests for M7.13/M7.14/M7.15 agent context identity discovery contract.

Validates that agent_context correctly includes provider chain diagnostics,
local cache info, new reason codes, and M7.14 minimal cache template guidance.

M7.15: Validates FundIdentityCandidate M7.15 fields, discovery pipeline
contract shape, and should_auto_verify hard-reject/token-overlap gates.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.tools.portfolio.agent_context import (
    REASON_CODES,
    SAFE_TO_ANALYZE_ITEMS,
    UNSAFE_TO_INFER_ITEMS,
    build_agent_context,
)
from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    NullFundIdentitySearchProvider,
    apply_hard_reject,
    compute_discovery_summary,
    discover_candidates,
    score_candidate,
    should_auto_verify,
    BUCKET_MISMATCH,
    EXACT_FUND_UNIVERSE_NAME_MATCH,
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


class TestM714MinimalCacheTemplateGuidance:
    """M7.14: Agent context must recommend minimal cache template when identity is blocked."""

    def test_minimal_cache_template_question_for_chain_failed(self):
        """When provider chain failed, recommended questions must include minimal template."""
        summary = {
            "personal_health_report": {
                "overall_status": "needs_data",
                "confidence_level": "unavailable",
                "reason_codes": [
                    "name_search_provider_chain_failed",
                    "provider_name_search_network_error",
                ],
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")
        questions = context["recommended_agent_questions"]
        assert any("minimal" in q.lower() for q in questions), (
            f"Expected minimal template question. Got: {questions}"
        )

    def test_minimal_cache_template_question_for_cache_missing(self):
        """When cache is missing, recommended questions must include minimal template."""
        summary = {
            "personal_health_report": {
                "overall_status": "needs_data",
                "confidence_level": "unavailable",
                "reason_codes": [
                    "identity_candidate_cache_missing",
                    "name_only_funds",
                ],
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")
        questions = context["recommended_agent_questions"]
        assert any("minimal" in q.lower() for q in questions), (
            f"Expected minimal template question. Got: {questions}"
        )

    def test_identity_questions_before_nav_questions(self):
        """Identity discovery questions must come before NAV questions."""
        summary = {
            "personal_health_report": {
                "overall_status": "needs_data",
                "confidence_level": "unavailable",
                "reason_codes": [
                    "name_search_provider_chain_failed",
                    "provider_name_search_network_error",
                    "nav_missing",
                ],
            },
            "holdings_snapshot": {"loaded": False},
        }

        context = build_agent_context(summary, run_id="test")
        questions = context["recommended_agent_questions"]

        identity_idx = None
        nav_idx = None
        for i, q in enumerate(questions):
            if "identity" in q.lower() or "cache" in q.lower() or "candidate" in q.lower():
                if identity_idx is None:
                    identity_idx = i
            if "nav" in q.lower():
                if nav_idx is None:
                    nav_idx = i

        if identity_idx is not None and nav_idx is not None:
            assert identity_idx < nav_idx, (
                f"Identity question (idx={identity_idx}) must come before "
                f"NAV question (idx={nav_idx}). Questions: {questions}"
            )


# ── M7.15: FundIdentityCandidate contract and discovery pipeline ─────────


def _make_candidate(**kwargs) -> FundIdentityCandidate:
    defaults = {"fund_code": "000001", "fund_name": "Synthetic Fund C"}
    defaults.update(kwargs)
    return FundIdentityCandidate(**defaults)


class TestM715FundIdentityCandidateFields:
    """FundIdentityCandidate must have all M7.15 fields with correct defaults."""

    def test_default_hard_reject_false(self):
        c = FundIdentityCandidate(fund_code="000001", fund_name="Test")
        assert c.hard_reject is False

    def test_default_reject_reasons_empty(self):
        c = FundIdentityCandidate(fund_code="000001", fund_name="Test")
        assert c.reject_reasons == []

    def test_default_critical_token_mismatch_empty(self):
        c = FundIdentityCandidate(fund_code="000001", fund_name="Test")
        assert c.critical_token_mismatch == []

    def test_default_identity_token_overlap_zero(self):
        c = FundIdentityCandidate(fund_code="000001", fund_name="Test")
        assert c.identity_token_overlap == 0.0

    def test_default_candidate_status_accepted(self):
        c = FundIdentityCandidate(fund_code="000001", fund_name="Test")
        assert c.candidate_status == "accepted_candidate"

    def test_all_fields_settable(self):
        c = FundIdentityCandidate(
            fund_code="000001", fund_name="Test",
            hard_reject=True,
            reject_reasons=["rejected_brand_mismatch"],
            critical_token_mismatch=["brand:A!=B"],
            identity_token_overlap=0.25,
            candidate_status="rejected_brand_mismatch",
        )
        assert c.hard_reject is True
        assert c.reject_reasons == ["rejected_brand_mismatch"]
        assert c.critical_token_mismatch == ["brand:A!=B"]
        assert c.identity_token_overlap == 0.25
        assert c.candidate_status == "rejected_brand_mismatch"


class TestM715DiscoverCandidatesContract:
    """discover_candidates must return properly shaped results."""

    def test_empty_names_returns_empty(self):
        result = discover_candidates([])
        assert result == {}

    def test_null_provider_returns_no_candidates(self):
        result = discover_candidates(["Test Fund A"])
        assert isinstance(result, dict)

    def test_discovery_result_shape(self):
        result = discover_candidates(["Test Fund A"], NullFundIdentitySearchProvider())
        for norm_name, candidates in result.items():
            assert isinstance(norm_name, str)
            assert isinstance(candidates, list)
            for c in candidates:
                assert isinstance(c, FundIdentityCandidate)


class TestM715ComputeDiscoverySummaryContract:
    """compute_discovery_summary must return expected keys."""

    def test_summary_has_required_keys(self):
        discovery_results: dict[str, list[FundIdentityCandidate]] = {
            "Test Fund A": [
                _make_candidate(
                    fund_code="000001", fund_name="Test Fund A",
                    match_score=0.95, match_bucket="high",
                ),
            ],
        }
        summary = compute_discovery_summary(discovery_results)
        required_keys = {
            "name_search_requested_count",
            "name_search_candidate_count",
            "name_search_unique_high_confidence_count",
            "name_search_ambiguous_count",
            "name_search_no_result_count",
            "name_search_promoted_provider_verified_count",
            "name_search_unverified_count",
        }
        assert required_keys.issubset(set(summary.keys()))

    def test_hard_rejected_not_promoted(self):
        hard_rejected = _make_candidate(
            fund_code="000001", fund_name="Mismatch Fund",
            match_score=0.0, match_bucket=BUCKET_MISMATCH,
            hard_reject=True, reject_reasons=["rejected_brand_mismatch"],
            candidate_status="rejected_brand_mismatch",
        )
        summary = compute_discovery_summary({"Test": [hard_rejected]})
        assert summary["name_search_promoted_provider_verified_count"] == 0
        assert summary["name_search_unverified_count"] >= 1


class TestM715ShouldAutoVerifyContract:
    """should_auto_verify must respect M7.15 hard-reject and token overlap."""

    def test_hard_reject_blocks_auto_verify(self):
        c = _make_candidate(
            fund_code="000001", fund_name="Test Fund",
            match_score=0.95, match_bucket="high",
            hard_reject=True, reject_reasons=["rejected_brand_mismatch"],
        )
        can_verify, reason = should_auto_verify([c])
        assert can_verify is False
        assert "hard_reject" in reason

    def test_critical_token_mismatch_blocks_auto_verify(self):
        c = _make_candidate(
            fund_code="000001", fund_name="Test Fund",
            match_score=0.95, match_bucket="high",
            hard_reject=False,
            critical_token_mismatch=["brand:A!=B"],
            identity_token_overlap=0.3,
        )
        can_verify, reason = should_auto_verify([c])
        assert can_verify is False
        assert "critical_token_mismatch" in reason

    def test_zero_token_overlap_blocks_auto_verify(self):
        c = _make_candidate(
            fund_code="000001", fund_name="Test Fund",
            match_score=0.95, match_bucket="high",
            hard_reject=False,
            critical_token_mismatch=[],
            identity_token_overlap=0.0,
        )
        can_verify, reason = should_auto_verify([c])
        assert can_verify is False
        assert "no_identity_token_overlap" in reason

    def test_valid_candidate_auto_verifies(self):
        c = _make_candidate(
            fund_code="000001", fund_name="Test Fund",
            match_score=0.95, match_bucket="high",
            hard_reject=False,
            critical_token_mismatch=[],
            identity_token_overlap=0.8,
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH],
        )
        can_verify, reason = should_auto_verify([c])
        assert can_verify is True
        assert reason == "auto_verified"


class TestM715ApplyHardRejectContract:
    """apply_hard_reject must always set all M7.15 fields."""

    def test_reject_sets_all_fields(self):
        c = _make_candidate(fund_code="000217", fund_name="华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert isinstance(result.hard_reject, bool)
        assert isinstance(result.reject_reasons, list)
        assert isinstance(result.critical_token_mismatch, list)
        assert isinstance(result.identity_token_overlap, float)
        assert isinstance(result.candidate_status, str)
        assert result.hard_reject is True
        assert len(result.reject_reasons) > 0
        assert result.candidate_status != "accepted_candidate"

    def test_accept_sets_all_fields(self):
        c = _make_candidate(fund_code="007467", fund_name="华泰柏瑞中证红利低波动ETF联接C")
        scored = score_candidate("华泰柏瑞中证红利低波动ETF联接C", c)
        result = apply_hard_reject("华泰柏瑞中证红利低波动ETF联接C", scored)
        assert isinstance(result.hard_reject, bool)
        assert isinstance(result.reject_reasons, list)
        assert isinstance(result.critical_token_mismatch, list)
        assert isinstance(result.identity_token_overlap, float)
        assert isinstance(result.candidate_status, str)
        if not result.hard_reject:
            assert result.candidate_status == "accepted_candidate"
            assert result.reject_reasons == []


# ── M7.16: Exact fund universe reverse lookup contract ──────────────────


class TestM716ExactLookupContract:
    """M7.16: Agent context must include exact lookup diagnostics."""

    def test_exact_lookup_diagnostics_in_context(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "medium",
                "reason_codes": ["identity_unverified"],
            },
            "name_search_provider_diagnostics": {
                "name_search_provider_type": "akshare",
                "name_search_provider_status": "available",
                "fund_universe_size": 12000,
                "exact_full_name_match_count": 5,
                "exact_without_punctuation_match_count": 2,
                "core_share_class_match_count": 1,
                "fuzzy_fallback_count": 3,
                "search_strategy_used": "exact_full_name",
            },
            "identity_resolution": {
                "exact_lookup_failed_count": 2,
                "fuzzy_candidate_count": 3,
                "hard_rejected_candidate_count": 1,
            },
            "holdings_snapshot": {"loaded": False},
        }
        context = build_agent_context(summary, run_id="test")
        ns_diag = context["name_search_diagnostics"]
        assert ns_diag.get("fund_universe_size") == 12000
        assert ns_diag.get("exact_full_name_match_count") == 5
        assert ns_diag.get("exact_without_punctuation_match_count") == 2
        assert ns_diag.get("core_share_class_match_count") == 1
        assert ns_diag.get("fuzzy_fallback_count") == 3
        assert ns_diag.get("exact_lookup_failed_count") == 2

    def test_exact_match_reason_required_for_auto_verify(self):
        """M7.16: should_auto_verify must require exact match reason."""
        from src.tools.portfolio.fund_identity_candidate_discovery import (
            EXACT_FUND_UNIVERSE_NAME_MATCH,
        )
        # Without exact match reason → no auto-verify
        c_no_exact = _make_candidate(
            fund_code="000001", fund_name="Test Fund",
            match_score=0.95, match_bucket="high",
            hard_reject=False, identity_token_overlap=0.8,
            match_reasons=["high_name_similarity"],
        )
        ok, reason = should_auto_verify([c_no_exact])
        assert not ok
        assert "no_exact_universe_match_reason" in reason

        # With exact match reason → auto-verify
        c_exact = _make_candidate(
            fund_code="000001", fund_name="Test Fund",
            match_score=0.95, match_bucket="high",
            hard_reject=False, identity_token_overlap=0.8,
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH],
        )
        ok, reason = should_auto_verify([c_exact])
        assert ok
        assert reason == "auto_verified"

    def test_non_exact_candidate_codes_not_in_public_context(self):
        """M7.16: Non-exact candidate codes must not appear in public agent context."""
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
            "holdings_snapshot": {"loaded": False},
        }
        context = build_agent_context(summary, run_id="test")
        # Verify no fund codes leak into safe-to-analyze or other public fields
        context_str = str(context.get("safe_to_analyze", []))
        assert "000001" not in context_str
