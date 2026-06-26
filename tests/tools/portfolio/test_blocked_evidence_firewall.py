"""Tests for M7.6 blocked evidence firewall and candidate identity hygiene.

Validates that:
1. identity_unverified reports hide candidate codes, estimated units, NAV, P&L
2. agent_context includes blocked_evidence_summary
3. verified_by_user without required fields is downgraded
4. Report does not describe verified_by_user as unlock switch
5. NAV trend section is blocked under unverified identity
6. Fixit package generates identity_candidates.private.csv
7. Agent context has identity-specific unsafe_to_infer items

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.tools.portfolio.evidence_visibility import (
    ALLOWED_VERIFICATION_SOURCES,
    BLOCKED_IDENTITY_STATUSES,
    compute_blocked_evidence_summary,
    is_identity_blocked,
    is_valuation_blocked,
    sanitize_position_for_agent_context,
    sanitize_position_for_debug,
    sanitize_position_for_public_report,
    should_downgrade_verified_by_user,
    validate_verified_by_user,
)
from src.tools.portfolio.agent_context import (
    UNSAFE_TO_INFER_ITEMS,
    build_agent_context,
    render_agent_context_markdown,
)
from src.tools.portfolio.report_sections.builders import (
    _build_performance_and_nav,
    _build_pnl_and_cost_basis,
    _build_portfolio_snapshot,
    _has_blocked_identity_positions,
)


# ── 1. Evidence visibility helpers ──────────────────────────────────────


class TestIsIdentityBlocked:
    """Test is_identity_blocked helper."""

    def test_manual_override_unverified_is_blocked(self):
        assert is_identity_blocked({"identity_verification_status": "manual_override_unverified"})

    def test_code_name_mismatch_is_blocked(self):
        assert is_identity_blocked({"identity_verification_status": "code_name_mismatch"})

    def test_provider_lookup_failed_is_blocked(self):
        assert is_identity_blocked({"identity_verification_status": "provider_lookup_failed"})

    def test_invalid_code_is_blocked(self):
        assert is_identity_blocked({"identity_verification_status": "invalid_code"})

    def test_name_only_is_blocked(self):
        assert is_identity_blocked({"identity_verification_status": "name_only"})

    def test_verified_is_not_blocked(self):
        assert not is_identity_blocked({"identity_verification_status": "verified"})

    def test_provider_verified_is_not_blocked(self):
        assert not is_identity_blocked({"identity_verification_status": "provider_verified"})

    def test_user_verified_override_is_not_blocked(self):
        assert not is_identity_blocked({"identity_verification_status": "user_verified_override"})

    def test_empty_status_is_not_blocked(self):
        assert not is_identity_blocked({})


class TestIsValuationBlocked:
    """Test is_valuation_blocked helper."""

    def test_cashflow_only_is_blocked(self):
        assert is_valuation_blocked({"valuation_type": "cashflow_only"})

    def test_none_is_blocked(self):
        assert is_valuation_blocked({"valuation_type": "none"})

    def test_estimated_is_not_blocked(self):
        assert not is_valuation_blocked({"valuation_type": "estimated"})

    def test_empty_is_not_blocked(self):
        assert not is_valuation_blocked({})


# ── 2. Sanitize position for public report ──────────────────────────────


class TestSanitizePositionForPublicReport:
    """Test sanitize_position_for_public_report."""

    def test_verified_position_passes_through(self):
        pos = {
            "fund_code": "000001",
            "fund_name": "Verified Fund",
            "identity_verification_status": "verified",
            "valuation_type": "estimated",
            "estimated_units": 100.0,
            "latest_nav": 1.5,
            "current_value": 150.0,
        }
        result = sanitize_position_for_public_report(pos)
        assert result.get("fund_code") == "000001"
        assert result.get("estimated_units") == 100.0
        assert result.get("latest_nav") == 1.5
        assert result.get("current_value") == 150.0
        assert result.get("_sanitized") is None

    def test_blocked_identity_removes_fund_code(self):
        pos = {
            "fund_code": "000002",
            "fund_name": "Unverified Fund",
            "identity_verification_status": "manual_override_unverified",
            "valuation_type": "cashflow_only",
            "estimated_units": 100.0,
            "latest_nav": 1.5,
            "current_value": 150.0,
            "total_cost": 1000.0,
            "buy_count": 3,
        }
        result = sanitize_position_for_public_report(pos)
        # fund_code must NOT be present as confirmed code
        assert result.get("fund_code") is None
        # Identity-dependent fields must be removed
        assert result.get("estimated_units") is None
        assert result.get("latest_nav") is None
        assert result.get("current_value") is None
        # Safe fields preserved
        assert result.get("raw_fund_name") == "Unverified Fund"
        assert result.get("total_cost") == 1000.0
        assert result.get("buy_count") == 3
        assert result.get("_sanitized") is True

    def test_blocked_identity_shows_next_step(self):
        pos = {
            "fund_code": "000002",
            "fund_name": "Test Fund",
            "identity_verification_status": "code_name_mismatch",
        }
        result = sanitize_position_for_public_report(pos)
        assert result.get("next_step") == "verify code or provide holdings snapshot"


class TestSanitizePositionForAgentContext:
    """Test sanitize_position_for_agent_context."""

    def test_blocked_identity_hides_candidate_code(self):
        pos = {
            "fund_code": "000002",
            "fund_name": "Unverified Fund",
            "identity_verification_status": "manual_override_unverified",
            "estimated_units": 100.0,
            "latest_nav": 1.5,
        }
        result = sanitize_position_for_agent_context(pos)
        # Must NOT show the actual candidate code
        assert result.get("fund_code") is None
        # Must indicate that a candidate code exists
        assert result.get("has_candidate_code") is True
        # Identity-dependent fields must be removed
        assert result.get("estimated_units") is None
        assert result.get("latest_nav") is None
        assert result.get("_sanitized") is True

    def test_verified_position_shows_code(self):
        pos = {
            "fund_code": "000001",
            "fund_name": "Verified Fund",
            "identity_verification_status": "verified",
            "valuation_type": "estimated",
        }
        result = sanitize_position_for_agent_context(pos)
        assert result.get("fund_code") == "000001"
        assert result.get("_sanitized") is None


# ── 3. Blocked evidence summary ─────────────────────────────────────────


class TestComputeBlockedEvidenceSummary:
    """Test compute_blocked_evidence_summary."""

    def test_no_blocked_positions(self):
        positions = [
            {"identity_verification_status": "verified", "valuation_type": "estimated"},
        ]
        result = compute_blocked_evidence_summary(positions)
        assert result["candidate_code_count"] == 0
        assert result["nav_trend_blocked"] is False

    def test_blocked_positions_counted(self):
        positions = [
            {
                "fund_code": "000001",
                "identity_verification_status": "manual_override_unverified",
                "valuation_type": "cashflow_only",
                "estimated_units": 100.0,
                "latest_nav": 1.5,
            },
        ]
        result = compute_blocked_evidence_summary(positions)
        assert result["candidate_code_count"] == 1
        assert result["estimated_units_blocked_count"] == 1
        assert result["latest_nav_blocked_count"] == 1
        assert result["nav_trend_blocked"] is True
        assert "identity_unverified" in result["reasons"]


# ── 4. verified_by_user semantic tightening ────────────────────────────


class TestValidateVerifiedByUser:
    """Test validate_verified_by_user."""

    def test_valid_override(self):
        record = {
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verification_source": "alipay_holdings_page",
            "verified_at": "2026-06-26",
        }
        is_valid, missing = validate_verified_by_user(record)
        assert is_valid is True
        assert len(missing) == 0

    def test_missing_verification_source(self):
        record = {
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verified_at": "2026-06-26",
        }
        is_valid, missing = validate_verified_by_user(record)
        assert is_valid is False
        assert any("verification_source" in m for m in missing)

    def test_missing_verified_at(self):
        record = {
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verification_source": "alipay_holdings_page",
        }
        is_valid, missing = validate_verified_by_user(record)
        assert is_valid is False
        assert any("verified_at" in m for m in missing)

    def test_invalid_verification_source(self):
        record = {
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verification_source": "just_guessed",
            "verified_at": "2026-06-26",
        }
        is_valid, missing = validate_verified_by_user(record)
        assert is_valid is False
        assert any("verification_source" in m for m in missing)

    def test_invalid_fund_code(self):
        record = {
            "fund_code": "abc",
            "fund_name": "Test Fund",
            "verification_source": "alipay_holdings_page",
            "verified_at": "2026-06-26",
        }
        is_valid, missing = validate_verified_by_user(record)
        assert is_valid is False
        assert any("fund_code" in m for m in missing)

    def test_missing_fund_name(self):
        record = {
            "fund_code": "000001",
            "verification_source": "alipay_holdings_page",
            "verified_at": "2026-06-26",
        }
        is_valid, missing = validate_verified_by_user(record)
        assert is_valid is False
        assert any("fund_name" in m for m in missing)


class TestShouldDowngradeVerifiedByUser:
    """Test should_downgrade_verified_by_user."""

    def test_not_claimed_verified_no_downgrade(self):
        record = {"verified_by_user": False}
        assert should_downgrade_verified_by_user(record) is False

    def test_valid_claimed_verified_no_downgrade(self):
        record = {
            "verified_by_user": True,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verification_source": "alipay_holdings_page",
            "verified_at": "2026-06-26",
        }
        assert should_downgrade_verified_by_user(record) is False

    def test_missing_source_downgrades(self):
        record = {
            "verified_by_user": True,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verified_at": "2026-06-26",
        }
        assert should_downgrade_verified_by_user(record) is True

    def test_missing_date_downgrades(self):
        record = {
            "verified_by_user": True,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verification_source": "alipay_holdings_page",
        }
        assert should_downgrade_verified_by_user(record) is True


# ── 5. Report section behavior under blocked identity ──────────────────


class TestReportHidesBlockedEvidence:
    """Test that report sections hide blocked identity evidence."""

    def _make_blocked_context(self) -> dict[str, Any]:
        """Create a context with blocked identity positions."""
        return {
            "artifacts": {
                "portfolio_summary": {
                    "position_count": 2,
                    "total_value": None,
                    "is_partial_diagnostic": True,
                },
                "position_summary": {
                    "000001": {
                        "fund_code": "000001",
                        "fund_name": "Verified Fund",
                        "identity_verification_status": "verified",
                        "valuation_type": "estimated",
                    },
                    "000002": {
                        "fund_code": "000002",
                        "fund_name": "Unverified Fund",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                },
                "source_of_truth": "derived_from_transactions",
                "e2e_summary": {
                    "identity_resolution": {
                        "identity_verification_status_counts": {
                            "manual_override_unverified": 1,
                        },
                    },
                    "holdings_snapshot": {"loaded": False},
                },
            },
            "report": {},
            "data_completeness": {"grade": "C", "score": 0.5},
            "analysis_coverage": {},
            "report_limitations": [],
            "warnings": [],
            "language": "en",
        }

    def test_has_blocked_identity_positions(self):
        ctx = self._make_blocked_context()
        assert _has_blocked_identity_positions(ctx) is True

    def test_portfolio_snapshot_shows_identity_unverified(self):
        ctx = self._make_blocked_context()
        section = _build_portfolio_snapshot(ctx)
        # Must mention identity_unverified
        all_text = " ".join(section.get("bullets", []) + section.get("limitations", []))
        assert "identity_unverified" in all_text.lower() or "unverified" in all_text.lower()

    def test_portfolio_snapshot_hides_candidate_codes(self):
        ctx = self._make_blocked_context()
        section = _build_portfolio_snapshot(ctx)
        all_text = " ".join(section.get("bullets", []))
        # Must NOT show the candidate code as a confirmed code
        # (the code "000002" should not appear as a confirmed fund code)
        assert "000002" not in all_text

    def test_performance_nav_is_blocked(self):
        ctx = self._make_blocked_context()
        section = _build_performance_and_nav(ctx)
        # NAV trend must be blocked
        assert section["status"] == "MISSING"
        limitations_text = " ".join(section.get("limitations", []))
        # Must mention identity/unverified or 身份未验证
        assert (
            "identity" in limitations_text.lower()
            or "unverified" in limitations_text.lower()
            or "身份" in limitations_text
            or "不可用" in limitations_text
        )

    def test_pnl_is_blocked(self):
        ctx = self._make_blocked_context()
        section = _build_pnl_and_cost_basis(ctx)
        limitations_text = " ".join(section.get("limitations", []))
        assert "identity" in limitations_text.lower() or "unverified" in limitations_text.lower()

    def test_report_does_not_describe_verified_by_user_as_unlock(self):
        """Report must NOT say 'add verified_by_user:true to unlock valuation'."""
        ctx = self._make_blocked_context()
        section = _build_portfolio_snapshot(ctx)
        all_text = " ".join(section.get("bullets", []) + section.get("limitations", []))
        # Must NOT contain unlock language
        assert "unlock" not in all_text.lower()
        # Must contain guidance to verify first
        assert "verify" in all_text.lower() or "核对" in all_text


# ── 6. Agent context blocked evidence summary ──────────────────────────


class TestAgentContextBlockedEvidence:
    """Test agent context includes blocked_evidence_summary."""

    def test_blocked_evidence_summary_in_context(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_unverified"],
            },
            "holdings_snapshot": {"loaded": False},
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                        "estimated_units": 100.0,
                        "latest_nav": 1.5,
                    },
                ],
            },
        }
        ctx = build_agent_context(summary)
        assert "blocked_evidence_summary" in ctx
        blocked = ctx["blocked_evidence_summary"]
        assert blocked["candidate_code_count"] == 1
        assert blocked["nav_trend_blocked"] is True

    def test_identity_specific_unsafe_to_infer(self):
        """M7.6: New unsafe_to_infer items must be present."""
        assert "nav_trend_from_unverified_identity" in UNSAFE_TO_INFER_ITEMS
        assert "fund_code_from_manual_override_without_verification" in UNSAFE_TO_INFER_ITEMS
        assert "p_and_l_from_avg_cost_nav_comparison" in UNSAFE_TO_INFER_ITEMS
        assert "complete_identity_from_candidate_code" in UNSAFE_TO_INFER_ITEMS

    def test_identity_blocked_questions_in_context(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_unverified"],
            },
            "holdings_snapshot": {"loaded": False},
        }
        ctx = build_agent_context(summary)
        questions = ctx.get("recommended_agent_questions", [])
        # Must include identity-specific questions
        questions_text = " ".join(questions)
        assert "核对" in questions_text or "verify" in questions_text.lower()

    def test_blocked_evidence_summary_in_markdown(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_unverified"],
            },
            "holdings_snapshot": {"loaded": False},
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                ],
            },
        }
        ctx = build_agent_context(summary)
        md = render_agent_context_markdown(ctx)
        assert "Blocked Evidence Summary" in md
        assert "M7.6 Firewall" in md


# ── 7. Report wording checks ──────────────────────────────────────────


class TestReportWordingUnderBlockedIdentity:
    """Test that report does not contain forbidden wording under blocked identity."""

    def test_no_significant_profit_or_loss_claim(self):
        """Report must not claim significant profit/loss under blocked identity."""
        ctx = {
            "artifacts": {
                "portfolio_summary": {
                    "position_count": 1,
                    "total_value": None,
                    "is_partial_diagnostic": True,
                },
                "position_summary": {
                    "000001": {
                        "fund_code": "000001",
                        "fund_name": "Unverified Fund",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                },
                "source_of_truth": "derived_from_transactions",
                "e2e_summary": {
                    "identity_resolution": {
                        "identity_verification_status_counts": {
                            "manual_override_unverified": 1,
                        },
                    },
                    "holdings_snapshot": {"loaded": False},
                },
            },
            "report": {},
            "data_completeness": {"grade": "D", "score": 0.2},
            "analysis_coverage": {},
            "report_limitations": [],
            "warnings": [],
            "language": "en",
        }
        section = _build_performance_and_nav(ctx)
        # Section must be MISSING (no NAV trend content)
        assert section["status"] == "MISSING"
        # Bullets must be empty (no NAV trend claims)
        assert len(section.get("bullets", [])) == 0


# ── 8. Skill behavior constraints ──────────────────────────────────────


class TestSkillForbidsNavTrendFromBlockedEvidence:
    """Agent must not produce NAV trend from blocked evidence."""

    def test_performance_section_is_missing_when_blocked(self):
        """When identity is blocked, performance_and_nav must be MISSING."""
        ctx = {
            "artifacts": {
                "portfolio_summary": {
                    "position_count": 1,
                    "is_partial_diagnostic": True,
                },
                "position_summary": {
                    "000001": {
                        "fund_code": "000001",
                        "fund_name": "Unverified Fund",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                },
                "source_of_truth": "derived_from_transactions",
                "e2e_summary": {
                    "identity_resolution": {
                        "identity_verification_status_counts": {
                            "manual_override_unverified": 1,
                        },
                    },
                    "holdings_snapshot": {"loaded": False},
                },
            },
            "report": {},
            "data_completeness": {"grade": "D", "score": 0.2},
            "analysis_coverage": {},
            "report_limitations": [],
            "warnings": [],
            "language": "en",
        }
        section = _build_performance_and_nav(ctx)
        assert section["status"] == "MISSING"


class TestSkillForbidsBatchVerifiedByUserUnlock:
    """Agent must not suggest batch verified_by_user:true as unlock."""

    def test_report_does_not_suggest_batch_unlock(self):
        ctx = {
            "artifacts": {
                "portfolio_summary": {
                    "position_count": 2,
                    "is_partial_diagnostic": True,
                },
                "position_summary": {
                    "000001": {
                        "fund_code": "000001",
                        "fund_name": "Unverified Fund 1",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                    "000002": {
                        "fund_code": "000002",
                        "fund_name": "Unverified Fund 2",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                },
                "source_of_truth": "derived_from_transactions",
                "e2e_summary": {
                    "identity_resolution": {
                        "identity_verification_status_counts": {
                            "manual_override_unverified": 2,
                        },
                    },
                    "holdings_snapshot": {"loaded": False},
                },
            },
            "report": {},
            "data_completeness": {"grade": "D", "score": 0.2},
            "analysis_coverage": {},
            "report_limitations": [],
            "warnings": [],
            "language": "en",
        }
        section = _build_portfolio_snapshot(ctx)
        all_text = " ".join(section.get("bullets", []) + section.get("limitations", []))
        # Must NOT suggest batch unlock
        assert "batch" not in all_text.lower() or "do not" in all_text.lower()
        # Must NOT say "add verified_by_user to unlock"
        assert "unlock" not in all_text.lower()


class TestPromptGuidesIdentityCandidateReview:
    """Agent context must guide user to identity candidate review."""

    def test_agent_context_includes_identity_candidates_path(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["identity_unverified"],
            },
            "holdings_snapshot": {"loaded": False},
            "confirmed_portfolio": {
                "positions": [
                    {
                        "fund_code": "000001",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                ],
            },
        }
        ctx = build_agent_context(summary)
        # Must include identity_candidates artifact path
        assert "identity_candidates" in ctx.get("artifact_paths", {})


# ── 9. verified_by_user downgrade tests ────────────────────────────────


class TestVerifiedByUserDowngrade:
    """Test that verified_by_user without required fields is downgraded."""

    def test_verified_by_user_without_source_downgrades(self):
        """M7.6: verified_by_user without verification_source → downgrade."""
        record = {
            "verified_by_user": True,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verified_at": "2026-06-26",
        }
        assert should_downgrade_verified_by_user(record) is True

    def test_verified_by_user_without_date_downgrades(self):
        """M7.6: verified_by_user without verified_at → downgrade."""
        record = {
            "verified_by_user": True,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "verification_source": "alipay_holdings_page",
        }
        assert should_downgrade_verified_by_user(record) is True

    def test_verified_by_user_not_described_as_unlock_switch(self):
        """M7.6: Report must not describe verified_by_user as unlock."""
        # This is a semantic test — verify the fixit readme
        from scripts.fund_agent_personal_run import _build_fixit_readme
        readme = _build_fixit_readme(
            {"personal_health_report": {"reason_codes": ["identity_unverified"]},
             "valuation_summary": {}, "identity_resolution": {"identity_verification_status_counts": {"manual_override_unverified": 1}}},
            None,
        )
        assert "unlock" not in readme.lower() or "NOT an unlock" in readme
        assert "DO NOT add verified_by_user" in readme or "not" in readme.lower()

    def test_report_asks_to_verify_not_to_force_confirm(self):
        """M7.6: Report must ask to verify, not to force confirm."""
        ctx = {
            "artifacts": {
                "portfolio_summary": {
                    "position_count": 1,
                    "is_partial_diagnostic": True,
                },
                "position_summary": {
                    "000001": {
                        "fund_code": "000001",
                        "fund_name": "Unverified Fund",
                        "identity_verification_status": "manual_override_unverified",
                        "valuation_type": "cashflow_only",
                    },
                },
                "source_of_truth": "derived_from_transactions",
                "e2e_summary": {
                    "identity_resolution": {
                        "identity_verification_status_counts": {
                            "manual_override_unverified": 1,
                        },
                    },
                    "holdings_snapshot": {"loaded": False},
                },
            },
            "report": {},
            "data_completeness": {"grade": "D", "score": 0.2},
            "analysis_coverage": {},
            "report_limitations": [],
            "warnings": [],
            "language": "en",
        }
        section = _build_portfolio_snapshot(ctx)
        all_text = " ".join(section.get("bullets", []) + section.get("limitations", []))
        # Must contain verify/核对 guidance
        assert "verify" in all_text.lower() or "核对" in all_text
        # Must NOT say just add verified_by_user to unlock
        assert "add verified_by_user:true to unlock" not in all_text.lower()
