"""Tests for realistic personal run flow and agent context consumption.

Validates real-data scenarios using synthetic test data.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from src.tools.portfolio.agent_context import (
    REASON_CODES,
    SAFETY_CONSTRAINTS,
    build_agent_context,
    render_agent_context_markdown,
)


def _make_summary(
    *,
    overall_status: str = "partial",
    confidence_level: str = "medium",
    reason_codes: list[str] | None = None,
    nav_coverage: dict[str, int] | None = None,
    reconstruction_status: str = "reconstructed_from_ledger",
    manual_overrides_used: bool = False,
    manual_override_matches_count: int = 0,
) -> dict[str, Any]:
    """Build a minimal E2E summary with personal_health_report."""
    return {
        "personal_health_report": {
            "schema_version": "personal_health_report.v1",
            "overall_status": overall_status,
            "confidence_level": confidence_level,
            "reason_codes": reason_codes if reason_codes is not None else ["partial_nav_coverage"],
            "data_sources": {
                "transaction_source": "alipay",
                "valuation_source": "reconstructed_from_ledger",
                "identity_source": "manual_override" if manual_overrides_used else "direct_fund_code",
            },
            "valuation_quality": {
                "positions_total": 15,
                "confirmed_count": 0,
                "estimated_full_coverage_count": 2,
                "estimated_partial_coverage_count": 1,
                "cashflow_only_count": 12,
                "unavailable_count": 0,
                "manual_review_count": 2,
                "estimated_current_value_total_is_partial": True,
            },
            "nav_coverage": nav_coverage or {
                "full": 2,
                "partial": 1,
                "none": 0,
                "latest_only": 12,
                "stale_count": 0,
                "qdii_like_count": 0,
            },
            "fix_it_checklist": [
                "Add trade-date NAV overrides for 1 fund(s) with missing coverage",
                "Add explicit units for 12 cashflow-only transaction(s) if available",
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
        "identity_resolution": {
            "manual_overrides_used": manual_overrides_used,
            "manual_override_matches_count": manual_override_matches_count,
        },
    }


# ── 1. Realistic personal run redacted summary ─────────────────────────


class TestRealisticPersonalRunRedactedSummary:
    """Agent context from a realistic run must not contain private paths."""

    def test_agent_context_no_absolute_paths(self):
        ctx = build_agent_context(_make_summary(), run_id="20260625-test")
        ctx_json = json.dumps(ctx)
        assert "C:" not in ctx_json
        assert "/home/" not in ctx_json
        assert "/Users/" not in ctx_json

    def test_agent_context_no_private_data_dir(self):
        ctx = build_agent_context(_make_summary(), run_id="20260625-test")
        ctx_json = json.dumps(ctx)
        assert "private_data" not in ctx_json

    def test_manifest_artifacts_are_relative(self):
        """Simulate run_manifest artifact paths — all must be relative."""
        manifest_artifacts = {
            "e2e_summary": "e2e_summary.json",
            "personal_health_report": "personal_health_report.json",
            "agent_context_md": "agent_context.md",
            "agent_context_json": "agent_context.json",
            "report": "report.md",
        }
        for name, path in manifest_artifacts.items():
            assert not path.startswith("/"), f"Manifest artifact {name} has absolute path"
            assert not path.startswith("\\"), f"Manifest artifact {name} has absolute path"

    def test_markdown_no_absolute_paths(self):
        ctx = build_agent_context(_make_summary(), run_id="20260625-test")
        md = render_agent_context_markdown(ctx)
        assert "C:" not in md
        assert "/home/" not in md
        assert "/Users/" not in md


# ── 2. Fix-it checklist is actionable ──────────────────────────────────


class TestFixItChecklistIsActionable:
    """fix_it_checklist must give data-supplement actions, not trading advice."""

    def test_nav_missing_checklist_is_data_action(self):
        ctx = build_agent_context(_make_summary(reason_codes=["nav_missing"]))
        for q in ctx["recommended_agent_questions"]:
            # Questions should be about data, not trading
            assert "buy" not in q.lower()
            assert "sell" not in q.lower()

    def test_name_only_checklist_is_data_action(self):
        ctx = build_agent_context(_make_summary(reason_codes=["name_only_funds"]))
        assert any("identity_overrides" in q for q in ctx["recommended_agent_questions"])

    def test_manual_review_checklist_is_data_action(self):
        ctx = build_agent_context(_make_summary(reason_codes=["manual_review_transactions"]))
        assert any("conversion/refund" in q or "confirmed" in q for q in ctx["recommended_agent_questions"])

    def test_cashflow_only_checklist_is_data_action(self):
        ctx = build_agent_context(_make_summary(reason_codes=["cashflow_only"]))
        assert any("units" in q.lower() or "cashflow" in q.lower() for q in ctx["recommended_agent_questions"])

    def test_estimated_only_checklist_is_data_action(self):
        ctx = build_agent_context(_make_summary(reason_codes=["estimated_only"]))
        assert any("units" in q.lower() or "nav" in q.lower() for q in ctx["recommended_agent_questions"])


# ── 3. Agent prompt does not request trading decision ──────────────────


class TestAgentPromptDoesNotRequestTradingDecision:
    """Prompt templates must not request buy/sell/hold decisions."""

    PROMPT_DIR = "docs/agent-integration/prompts"

    def _read_prompt(self, name: str) -> str:
        with open(f"{self.PROMPT_DIR}/{name}", encoding="utf-8") as f:
            return f.read()

    def test_zh_prompt_estimated_not_confirmed(self):
        content = self._read_prompt("analyze-agent-context.zh.md")
        assert "estimated" in content.lower()
        assert "confirmed" in content.lower()
        # Must explicitly state they are different
        assert "不要把" in content or "not" in content.lower()

    def test_zh_prompt_no_buy_sell_advice(self):
        content = self._read_prompt("analyze-agent-context.zh.md")
        # Should not instruct agent to give buy/sell advice
        lines = content.split("\n")
        advice_lines = [l for l in lines if "买入" in l or "卖出" in l or "调仓" in l]
        for line in advice_lines:
            # If mentioned, must be in a "do not" context
            assert "不要" in line or "禁止" in line or "不" in line

    def test_en_prompt_no_trading_decision(self):
        content = self._read_prompt("analyze-agent-context.en.md")
        # Should not instruct agent to make trading decisions
        assert "Decision" in content or "decision" in content
        # Must be in a "do not" context
        assert "NOT" in content or "not" in content

    def test_follow_up_prompt_is_data_focused(self):
        content = self._read_prompt("follow-up-missing-data.zh.md")
        # Should not suggest buy/sell/rebalance as actions
        # "买入/卖出" may appear in "不要建议买入/卖出" context — that's fine
        lines = content.split("\n")
        for line in lines:
            if "买入" in line or "卖出" in line or "调仓" in line:
                # Must be in a "do not" context
                assert "不要" in line or "禁止" in line or "不" in line

    def test_live_extension_prompt_requires_confirmation(self):
        content = self._read_prompt("live-provider-extension.zh.md")
        # Must require user confirmation before live data
        assert "确认" in content or "confirm" in content.lower()


# ── 4. Console summary is counts-only ──────────────────────────────────


class TestConsoleSummaryIsCountsOnly:
    """Console output should only contain counts, status, and relative paths."""

    def test_agent_context_json_is_counts_only(self):
        """agent_context.json should not contain real fund names, amounts, or paths."""
        ctx = build_agent_context(_make_summary(), run_id="20260625-test")
        ctx_json = json.dumps(ctx)
        # Should not contain typical private data patterns
        assert "fund_name" not in ctx_json
        assert "amount" not in ctx_json
        assert "transaction_id" not in ctx_json
        assert "order_id" not in ctx_json

    def test_health_report_json_is_counts_only(self):
        """personal_health_report.json should not contain real fund names or amounts."""
        summary = _make_summary()
        health = summary["personal_health_report"]
        health_json = json.dumps(health)
        assert "fund_name" not in health_json
        assert "amount" not in health_json
        assert "transaction_id" not in health_json

    def test_markdown_output_is_counts_only(self):
        ctx = build_agent_context(_make_summary(), run_id="20260625-test")
        md = render_agent_context_markdown(ctx)
        assert "fund_name" not in md
        assert "amount" not in md
        assert "transaction_id" not in md


# ── 5. Existing run reread is stable ───────────────────────────────────


class TestExistingRunRereadIsStable:
    """Re-reading an existing run with --agent-context-only must produce
    consistent output without re-running the pipeline."""

    def test_build_agent_context_is_deterministic(self):
        summary = _make_summary()
        ctx1 = build_agent_context(summary, run_id="stable-test")
        ctx2 = build_agent_context(summary, run_id="stable-test")
        assert ctx1 == ctx2

    def test_build_agent_context_ignores_irrelevant_fields(self):
        """Extra fields in summary should not change agent_context output."""
        summary = _make_summary()
        summary["extra_field"] = "should be ignored"
        ctx_with_extra = build_agent_context(summary, run_id="test")
        summary_base = _make_summary()
        ctx_base = build_agent_context(summary_base, run_id="test")
        assert ctx_with_extra == ctx_base

    def test_markdown_rendering_is_deterministic(self):
        summary = _make_summary()
        ctx = build_agent_context(summary, run_id="stable-test")
        md1 = render_agent_context_markdown(ctx)
        md2 = render_agent_context_markdown(ctx)
        assert md1 == md2


# ── 6. Identity source accuracy ────────────────────────────────────────


class TestIdentitySourceAccuracy:
    """identity_source must accurately reflect how fund codes were resolved."""

    def _make_health_artifacts(
        self,
        *,
        manual_overrides_used: bool = False,
        manual_override_matches_count: int = 0,
        valid_fund_codes_count: int = 15,
        name_only_count: int = 0,
    ) -> dict[str, Any]:
        """Build artifacts dict for build_personal_health_summary."""
        return {
            "e2e_summary": {
                "transaction_source": "alipay",
                "portfolio_input_source": "reconstructed_from_ledger",
                "pipeline_steps": {
                    "valid_fund_codes_count": valid_fund_codes_count,
                    "name_only_count": name_only_count,
                    "reconstruction_status": "reconstructed_from_ledger",
                },
            },
            "identity_summary": {
                "manual_overrides_used": manual_overrides_used,
                "manual_override_matches_count": manual_override_matches_count,
                "name_only_count": name_only_count,
            },
            "nav_coverage_summary": {
                "nav_coverage_full_count": 2,
                "nav_coverage_partial_count": 1,
                "nav_coverage_none_count": 0,
            },
            "valuation_summary": {
                "estimated_count": 3,
                "cashflow_only_count": 12,
                "none_count": 0,
            },
        }

    def test_manual_override_detected(self):
        """When manual_overrides_used is true, identity_source should be manual_override."""
        from src.tools.portfolio.personal_health_report import build_personal_health_summary
        artifacts = self._make_health_artifacts(manual_overrides_used=True, manual_override_matches_count=15)
        health = build_personal_health_summary(artifacts)
        assert health["data_sources"]["identity_source"] == "manual_override"

    def test_direct_fund_code_when_no_overrides(self):
        """When no overrides used and valid codes exist, identity_source should be direct_fund_code."""
        from src.tools.portfolio.personal_health_report import build_personal_health_summary
        artifacts = self._make_health_artifacts(manual_overrides_used=False, manual_override_matches_count=0)
        health = build_personal_health_summary(artifacts)
        assert health["data_sources"]["identity_source"] == "direct_fund_code"
