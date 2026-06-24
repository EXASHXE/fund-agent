"""Tests for agent context builder.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from src.tools.portfolio.agent_context import (
    SCHEMA_VERSION,
    build_agent_context,
    render_agent_context_markdown,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def _make_summary(
    *,
    overall_status: str = "partial",
    confidence_level: str = "medium",
    reason_codes: list[str] | None = None,
    nav_coverage: dict[str, int] | None = None,
    reconstruction_status: str = "reconstructed_from_ledger",
) -> dict[str, Any]:
    """Build a minimal E2E summary with personal_health_report."""
    return {
        "personal_health_report": {
            "schema_version": "personal_health_report.v1",
            "overall_status": overall_status,
            "confidence_level": confidence_level,
            "reason_codes": reason_codes or ["partial_nav_coverage"],
            "data_sources": {
                "transaction_source": "alipay",
                "valuation_source": "reconstructed_from_ledger",
                "identity_source": "direct_fund_code",
            },
            "valuation_quality": {
                "positions_total": 3,
                "confirmed_count": 0,
                "estimated_full_coverage_count": 1,
                "estimated_partial_coverage_count": 2,
                "cashflow_only_count": 0,
                "unavailable_count": 0,
                "manual_review_count": 0,
                "estimated_current_value_total_is_partial": True,
            },
            "nav_coverage": nav_coverage or {
                "full": 1,
                "partial": 2,
                "none": 0,
                "latest_only": 0,
                "stale_count": 0,
                "qdii_like_count": 0,
            },
            "fix_it_checklist": [
                "Add trade-date NAV overrides for 2 fund(s) with missing coverage"
            ],
            "safety_notes": [
                "This is not a formal investment decision — no BUY/SELL/HOLD instruction.",
                "No broker/order execution capability.",
                "No auto trading.",
                "Estimated values are not confirmed market values.",
                "Partial coverage means incomplete valuation.",
            ],
        },
        "pipeline_steps": {
            "reconstruction_status": reconstruction_status,
        },
    }


# ── Test: agent_context_contains_safe_to_analyze_scope ────────────────


class TestSafeToAnalyze:
    def test_partial_status_has_safe_scope(self):
        ctx = build_agent_context(_make_summary())
        assert len(ctx["safe_to_analyze"]) > 0
        assert "cashflow_trend" in ctx["safe_to_analyze"]
        assert "nav_coverage_quality" in ctx["safe_to_analyze"]

    def test_ok_status_has_safe_scope(self):
        ctx = build_agent_context(_make_summary(overall_status="ok"))
        assert len(ctx["safe_to_analyze"]) > 0

    def test_unavailable_status_has_empty_safe_scope(self):
        ctx = build_agent_context(_make_summary(overall_status="unavailable"))
        assert ctx["safe_to_analyze"] == []


# ── Test: agent_context_contains_unsafe_to_infer_scope ────────────────


class TestUnsafeToInfer:
    def test_partial_coverage_has_unsafe_infer(self):
        ctx = build_agent_context(_make_summary())
        assert len(ctx["unsafe_to_infer"]) > 0
        assert "trading_decision" in ctx["unsafe_to_infer"]
        assert "broker_or_order_execution" in ctx["unsafe_to_infer"]

    def test_full_coverage_removes_market_value_warning(self):
        ctx = build_agent_context(_make_summary(
            nav_coverage={"full": 3, "partial": 0, "none": 0, "latest_only": 0, "stale_count": 0, "qdii_like_count": 0}
        ))
        assert "complete_market_value_if_coverage_partial" not in ctx["unsafe_to_infer"]

    def test_partial_coverage_includes_market_value_warning(self):
        ctx = build_agent_context(_make_summary(
            nav_coverage={"full": 1, "partial": 2, "none": 0, "latest_only": 0, "stale_count": 0, "qdii_like_count": 0}
        ))
        assert "complete_market_value_if_coverage_partial" in ctx["unsafe_to_infer"]


# ── Test: agent_context_paths_are_relative ────────────────────────────


class TestRelativePaths:
    def test_default_artifact_paths_are_relative(self):
        ctx = build_agent_context(_make_summary())
        for name, path in ctx["artifact_paths"].items():
            assert not path.startswith("/"), f"artifact {name} has absolute path: {path}"
            assert not path.startswith("\\"), f"artifact {name} has absolute path: {path}"
            assert "C:" not in path, f"artifact {name} has Windows absolute path: {path}"

    def test_custom_artifact_paths_preserved(self):
        ctx = build_agent_context(
            _make_summary(),
            artifact_paths={"custom": "custom_file.json"},
        )
        assert ctx["artifact_paths"]["custom"] == "custom_file.json"
        # Default paths still present
        assert "e2e_summary" in ctx["artifact_paths"]


# ── Test: agent_context_does_not_leak_private_paths ───────────────────


class TestNoPrivatePaths:
    def test_no_private_data_dir_in_output(self):
        ctx = build_agent_context(_make_summary())
        ctx_json = json.dumps(ctx)
        assert "private_data" not in ctx_json
        assert "private/" not in ctx_json

    def test_no_absolute_paths_in_markdown(self):
        ctx = build_agent_context(_make_summary())
        md = render_agent_context_markdown(ctx)
        assert "C:" not in md
        assert "/home/" not in md
        assert "/Users/" not in md


# ── Test: agent_context_has_no_trading_advice ─────────────────────────


class TestNoTradingAdvice:
    def test_safety_constraints_present(self):
        ctx = build_agent_context(_make_summary())
        assert len(ctx["safety_constraints"]) > 0
        assert "not_formal_decision" in ctx["safety_constraints"]
        assert "no_auto_trading" in ctx["safety_constraints"]
        assert "no_broker_or_order_execution" in ctx["safety_constraints"]

    def test_recommended_questions_are_data_quality(self):
        ctx = build_agent_context(_make_summary())
        for q in ctx["recommended_agent_questions"]:
            # Questions should be about data quality, not trading
            assert "buy" not in q.lower()
            assert "sell" not in q.lower()
            # "trade-date" is OK (NAV term), but standalone "trade" as verb is not
            import re
            assert not re.search(r"\btrade\b(?!-date)", q.lower())

    def test_markdown_has_safety_constraints(self):
        ctx = build_agent_context(_make_summary())
        md = render_agent_context_markdown(ctx)
        assert "Safety Constraints" in md
        assert "not_formal_decision" in md
        assert "no_auto_trading" in md


# ── Test: agent_context_schema ────────────────────────────────────────


class TestSchema:
    def test_schema_version(self):
        ctx = build_agent_context(_make_summary())
        assert ctx["schema_version"] == SCHEMA_VERSION

    def test_required_fields_present(self):
        ctx = build_agent_context(_make_summary(), run_id="test-001")
        assert ctx["run_id"] == "test-001"
        assert "overall_status" in ctx
        assert "confidence_level" in ctx
        assert "reason_codes" in ctx
        assert "safe_to_analyze" in ctx
        assert "unsafe_to_infer" in ctx
        assert "recommended_agent_questions" in ctx
        assert "artifact_paths" in ctx
        assert "safety_constraints" in ctx


# ── Test: recommended_questions_match_reason_codes ────────────────────


class TestRecommendedQuestions:
    def test_name_only_triggers_identity_question(self):
        ctx = build_agent_context(_make_summary(reason_codes=["name_only_funds"]))
        assert any("identity_overrides" in q for q in ctx["recommended_agent_questions"])

    def test_partial_nav_triggers_nav_question(self):
        ctx = build_agent_context(_make_summary(reason_codes=["partial_nav_coverage"]))
        assert any("trade-date NAV" in q for q in ctx["recommended_agent_questions"])

    def test_manual_review_triggers_confirmation_question(self):
        ctx = build_agent_context(_make_summary(reason_codes=["manual_review_transactions"]))
        assert any("conversion/refund" in q for q in ctx["recommended_agent_questions"])

    def test_stale_nav_triggers_live_data_question(self):
        ctx = build_agent_context(_make_summary(reason_codes=["stale_nav"]))
        assert any("live NAV" in q for q in ctx["recommended_agent_questions"])

    def test_no_reason_codes_triggers_default_question(self):
        ctx = build_agent_context(_make_summary(reason_codes=[]))
        assert len(ctx["recommended_agent_questions"]) > 0


# ── Test: markdown rendering ──────────────────────────────────────────


class TestMarkdownRendering:
    def test_markdown_contains_all_sections(self):
        ctx = build_agent_context(_make_summary())
        md = render_agent_context_markdown(ctx)
        assert "## Data Readiness" in md
        assert "## Safe-to-Analyze Scope" in md
        assert "## Unsafe-to-Infer Scope" in md
        assert "## Evidence Map" in md
        assert "## Suggested Agent Follow-up Questions" in md
        assert "## Safety Constraints" in md

    def test_markdown_contains_status(self):
        ctx = build_agent_context(_make_summary(overall_status="partial"))
        md = render_agent_context_markdown(ctx)
        assert "partial" in md

    def test_markdown_contains_artifact_paths(self):
        ctx = build_agent_context(_make_summary())
        md = render_agent_context_markdown(ctx)
        assert "e2e_summary.json" in md
        assert "report.md" in md


# ── Test: empty/missing data ──────────────────────────────────────────


class TestEdgeCases:
    def test_empty_summary(self):
        ctx = build_agent_context({})
        assert ctx["overall_status"] == "unavailable"
        assert ctx["confidence_level"] == "unavailable"
        assert ctx["safe_to_analyze"] == []

    def test_missing_health_report(self):
        ctx = build_agent_context({"pipeline_steps": {}})
        assert ctx["overall_status"] == "unavailable"

    def test_reconstructed_portfolio_in_artifacts(self):
        ctx = build_agent_context(_make_summary(reconstruction_status="reconstructed_from_ledger"))
        assert "portfolio" in ctx["artifact_paths"]

    def test_no_reconstructed_portfolio_not_in_artifacts(self):
        ctx = build_agent_context(_make_summary(reconstruction_status="nav_unavailable"))
        assert "portfolio" not in ctx["artifact_paths"]
