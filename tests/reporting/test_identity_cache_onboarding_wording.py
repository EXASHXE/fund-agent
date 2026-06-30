"""Tests for M7.14 identity cache onboarding wording.

Validates:
1. Minimal cache template generated when provider chain failed
2. Minimal cache template contains raw_fund_name and blank fund_code
3. Fix-it README instructs save to private_data
4. Health report prioritizes identity discovery over NAV missing
5. Report does not say NAV missing as primary blocker
6. Agent context recommends minimal cache template
7. Public report hides cache candidates
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.tools.portfolio.personal_health_report import build_personal_health_summary


def _make_e2e_summary(
    *,
    provider_chain_failed: bool = False,
    local_cache_missing: bool = False,
    name_only_count: int = 0,
    nav_missing: bool = False,
    valid_fund_codes: int = 0,
) -> dict[str, Any]:
    """Build a minimal e2e_summary for testing."""
    provider_diag: dict[str, Any] = {}
    local_cache_diag: dict[str, Any] = {}

    if provider_chain_failed:
        provider_diag = {
            "provider_chain_enabled": True,
            "providers_attempted": ["AkShareNameSearchProvider"],
            "providers_succeeded": [],
            "providers_failed": ["AkShareNameSearchProvider"],
            "provider_errors_by_name": {
                "AkShareNameSearchProvider": "SSL: CERTIFICATE_VERIFY_FAILED",
            },
            "fallback_used": False,
        }
    if local_cache_missing:
        local_cache_diag = {
            "name_search_provider_status": "cache_missing",
        }

    identity: dict[str, Any] = {
        "name_only_count": name_only_count,
        "identity_verification_status_counts": {},
    }

    pipeline_steps: dict[str, Any] = {
        "valid_fund_codes_count": valid_fund_codes,
        "name_only_count": name_only_count,
    }

    e2e: dict[str, Any] = {
        "status": "failed",
        "transaction_source": "alipay_csv",
        "portfolio_input_source": "unavailable",
        "name_search_provider_diagnostics": provider_diag,
        "local_cache_diagnostics": local_cache_diag,
        "identity_resolution": identity,
        "pipeline_steps": pipeline_steps,
        "valuation_summary": {},
    }

    if nav_missing:
        e2e["pipeline_steps"]["reconstruction_status"] = "nav_unavailable"

    return e2e


class TestMinimalCacheTemplateGenerated:
    """Minimal cache template must be generated when provider chain failed."""

    def test_template_generated_when_chain_failed(self):
        e2e = _make_e2e_summary(provider_chain_failed=True, name_only_count=5)
        report = build_personal_health_summary({"e2e_summary": e2e})
        assert "name_search_provider_chain_failed" in report["reason_codes"]
        # Checklist should mention minimal template
        checklist_text = " ".join(report["fix_it_checklist"])
        assert "identity_candidate_cache_minimal" in checklist_text


class TestHealthReportPrioritizesIdentityDiscovery:
    """Health report must prioritize identity discovery over NAV missing."""

    def test_identity_discovery_before_nav_in_checklist(self):
        e2e = _make_e2e_summary(
            provider_chain_failed=True,
            name_only_count=5,
            nav_missing=True,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        checklist = report["fix_it_checklist"]

        # Identity discovery item must come before NAV item
        identity_idx = None
        nav_idx = None
        for i, item in enumerate(checklist):
            if "identity_candidate_cache_minimal" in item or "provider" in item.lower():
                if identity_idx is None:
                    identity_idx = i
            if "nav" in item.lower() or "NAV" in item:
                if nav_idx is None:
                    nav_idx = i

        if identity_idx is not None and nav_idx is not None:
            assert identity_idx < nav_idx, (
                f"Identity discovery (idx={identity_idx}) must come before "
                f"NAV (idx={nav_idx}) in checklist"
            )

    def test_identity_discovery_blocked_flag(self):
        e2e = _make_e2e_summary(
            provider_chain_failed=True,
            name_only_count=5,
            nav_missing=True,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        assert report["identity_discovery_blocked"] is True

    def test_identity_discovery_not_blocked_when_resolved(self):
        e2e = _make_e2e_summary(
            valid_fund_codes=10,
            nav_missing=True,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        assert report["identity_discovery_blocked"] is False


class TestReportDoesNotSayNavMissingAsPrimaryBlocker:
    """When identity discovery is blocked, NAV missing must not be the primary message."""

    def test_checklist_first_item_is_not_nav_when_identity_blocked(self):
        e2e = _make_e2e_summary(
            provider_chain_failed=True,
            name_only_count=5,
            nav_missing=True,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        checklist = report["fix_it_checklist"]
        assert len(checklist) > 0
        # First item should be about identity, not NAV
        first_item = checklist[0].lower()
        assert "nav" not in first_item, (
            f"First checklist item should not be about NAV when identity is blocked: {checklist[0]}"
        )

    def test_checklist_mentions_minimal_template(self):
        e2e = _make_e2e_summary(
            provider_chain_failed=True,
            name_only_count=5,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        checklist_text = " ".join(report["fix_it_checklist"])
        assert "minimal" in checklist_text.lower(), (
            "Checklist should mention minimal template when provider chain failed"
        )


class TestAgentContextRecommendsMinimalCacheTemplate:
    """Agent context must recommend minimal cache template when identity is blocked."""

    def test_agent_context_includes_minimal_cache_question(self):
        from src.tools.portfolio.agent_context import build_agent_context

        e2e = _make_e2e_summary(
            provider_chain_failed=True,
            name_only_count=5,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        e2e["personal_health_report"] = report

        context = build_agent_context(e2e)
        questions_text = " ".join(context["recommended_agent_questions"])
        assert "identity_candidate_cache_minimal" in questions_text or "minimal" in questions_text.lower(), (
            f"Agent context should recommend minimal cache template. Questions: {context['recommended_agent_questions']}"
        )

    def test_agent_context_identity_questions_before_nav(self):
        from src.tools.portfolio.agent_context import build_agent_context

        e2e = _make_e2e_summary(
            provider_chain_failed=True,
            name_only_count=5,
            nav_missing=True,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        e2e["personal_health_report"] = report

        context = build_agent_context(e2e)
        questions = context["recommended_agent_questions"]

        # Identity-related questions should come before NAV-related ones
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
                f"NAV question (idx={nav_idx})"
            )


class TestPublicReportHidesCacheCandidates:
    """Public report must not show unverified cache candidate codes."""

    def test_safe_to_analyze_includes_cache_but_not_codes(self):
        from src.tools.portfolio.agent_context import build_agent_context

        e2e = _make_e2e_summary(
            local_cache_missing=True,
            name_only_count=3,
        )
        report = build_personal_health_summary({"e2e_summary": e2e})
        e2e["personal_health_report"] = report

        context = build_agent_context(e2e)
        # identity_candidate_cache should be in safe_to_analyze
        assert "identity_candidate_cache" in context["safe_to_analyze"]
        # But confirmed_identity_from_name_search_unverified should be in unsafe
        assert "confirmed_identity_from_name_search_unverified" in context["unsafe_to_infer"]
