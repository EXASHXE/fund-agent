"""Tests for agent context contract validation.

Validates that agent_context output conforms to the contract defined in
docs/contracts/agent-context-contract.v1.md.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from src.tools.portfolio.agent_context import (
    REASON_CODES,
    SAFETY_CONSTRAINTS,
    SAFE_TO_ANALYZE_ITEMS,
    SCHEMA_VERSION,
    UNSAFE_TO_INFER_ITEMS,
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


# ── 1. Required fields ─────────────────────────────────────────────────


class TestAgentContextHasRequiredFields:
    """agent_context output must contain all contract-required fields."""

    REQUIRED_FIELDS = [
        "schema_version",
        "run_id",
        "overall_status",
        "confidence_level",
        "reason_codes",
        "safe_to_analyze",
        "unsafe_to_infer",
        "recommended_agent_questions",
        "artifact_paths",
        "safety_constraints",
    ]

    def test_all_required_fields_present(self):
        ctx = build_agent_context(_make_summary(), run_id="test-001")
        for field in self.REQUIRED_FIELDS:
            assert field in ctx, f"Missing required field: {field}"

    def test_schema_version_matches_constant(self):
        ctx = build_agent_context(_make_summary())
        assert ctx["schema_version"] == SCHEMA_VERSION
        assert ctx["schema_version"] == "fund_agent_context.v1"


# ── 2. Reason codes are from known enumeration ─────────────────────────


class TestAgentContextReasonCodesAreKnown:
    """All reason_codes must come from the stable REASON_CODES enumeration."""

    def test_reason_codes_subset_of_enum(self):
        ctx = build_agent_context(_make_summary(
            reason_codes=["partial_nav_coverage", "manual_review_transactions"]
        ))
        for code in ctx["reason_codes"]:
            assert code in REASON_CODES, f"Unknown reason code: {code}"

    def test_all_enum_codes_are_valid(self):
        """Verify the enumeration itself is non-empty and all codes are strings."""
        assert len(REASON_CODES) > 0
        for code in REASON_CODES:
            assert isinstance(code, str)
            assert code.strip() == code

    def test_empty_reason_codes_is_valid(self):
        ctx = build_agent_context(_make_summary(reason_codes=[]))
        # reason_codes comes from health report; empty means no issues detected
        assert isinstance(ctx["reason_codes"], list)


# ── 3. Artifact paths are relative and safe ────────────────────────────


class TestAgentContextArtifactPathsAreRelative:
    """artifact_paths must be relative and must not contain private_data."""

    def test_paths_are_relative(self):
        ctx = build_agent_context(_make_summary())
        for name, path in ctx["artifact_paths"].items():
            assert not path.startswith("/"), f"artifact {name} has absolute path: {path}"
            assert not path.startswith("\\"), f"artifact {name} has absolute path: {path}"
            assert "C:" not in path, f"artifact {name} has Windows absolute path: {path}"

    def test_no_private_data_in_paths(self):
        ctx = build_agent_context(_make_summary())
        ctx_json = json.dumps(ctx)
        assert "private_data" not in ctx_json
        assert "private/" not in ctx_json

    def test_custom_paths_preserved(self):
        ctx = build_agent_context(
            _make_summary(),
            artifact_paths={"custom": "custom_file.json"},
        )
        assert ctx["artifact_paths"]["custom"] == "custom_file.json"


# ── 4. Safety constraints present and complete ─────────────────────────


class TestAgentContextSafetyConstraintsPresent:
    """safety_constraints must include all required constraints."""

    REQUIRED_CONSTRAINTS = [
        "not_formal_decision",
        "no_auto_trading",
        "no_broker_or_order_execution",
        "estimated_values_are_not_confirmed",
        "partial_not_complete_market_value",
    ]

    def test_all_required_constraints_present(self):
        ctx = build_agent_context(_make_summary())
        for constraint in self.REQUIRED_CONSTRAINTS:
            assert constraint in ctx["safety_constraints"], f"Missing constraint: {constraint}"

    def test_constraints_subset_of_enum(self):
        ctx = build_agent_context(_make_summary())
        for c in ctx["safety_constraints"]:
            assert c in SAFETY_CONSTRAINTS, f"Unknown safety constraint: {c}"

    def test_no_formal_decision(self):
        ctx = build_agent_context(_make_summary())
        assert "not_formal_decision" in ctx["safety_constraints"]

    def test_no_broker_order_execution(self):
        ctx = build_agent_context(_make_summary())
        assert "no_broker_or_order_execution" in ctx["safety_constraints"]

    def test_no_auto_trading(self):
        ctx = build_agent_context(_make_summary())
        assert "no_auto_trading" in ctx["safety_constraints"]

    def test_estimated_not_confirmed(self):
        ctx = build_agent_context(_make_summary())
        assert "estimated_values_are_not_confirmed" in ctx["safety_constraints"]

    def test_partial_not_complete(self):
        ctx = build_agent_context(_make_summary())
        assert "partial_not_complete_market_value" in ctx["safety_constraints"]


# ── 5. Skill instructions reference personal run ───────────────────────


class TestSkillInstructionsReferencePersonalRun:
    """SKILL.md must reference fund-agent-personal-run and agent_context."""

    SKILL_PATH = "skills/fund-analysis/SKILL.md"

    def test_skill_references_personal_run(self):
        with open(self.SKILL_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "fund-agent-personal-run" in content

    def test_skill_references_agent_context(self):
        with open(self.SKILL_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "agent_context.md" in content
        assert "agent_context.json" in content

    def test_skill_forbids_formal_decision(self):
        with open(self.SKILL_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "formal Decision" in content or "formal `Decision`" in content

    def test_skill_forbids_auto_trading(self):
        with open(self.SKILL_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "auto trading" in content.lower() or "Auto-trade" in content

    def test_skill_forbids_broker_orders(self):
        with open(self.SKILL_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "broker" in content.lower() or "order execution" in content.lower()


# ── 6. Prompt templates contain required boundaries ────────────────────


class TestPromptTemplatesContainRequiredBoundaries:
    """Agent prompt templates must contain key safety boundaries."""

    PROMPT_DIR = "docs/agent-integration/prompts"

    def test_zh_prompt_estimated_not_confirmed(self):
        with open(f"{self.PROMPT_DIR}/analyze-agent-context.zh.md", encoding="utf-8") as f:
            content = f.read()
        assert "estimated" in content.lower()
        assert "confirmed" in content.lower()

    def test_zh_prompt_partial_not_complete(self):
        with open(f"{self.PROMPT_DIR}/analyze-agent-context.zh.md", encoding="utf-8") as f:
            content = f.read()
        assert "partial" in content.lower()

    def test_zh_prompt_no_trading_decision(self):
        with open(f"{self.PROMPT_DIR}/analyze-agent-context.zh.md", encoding="utf-8") as f:
            content = f.read()
        assert "Decision" in content or "decision" in content.lower()

    def test_zh_prompt_no_private_path_leak(self):
        with open(f"{self.PROMPT_DIR}/analyze-agent-context.zh.md", encoding="utf-8") as f:
            content = f.read()
        assert "private" in content.lower()

    def test_en_prompt_estimated_not_confirmed(self):
        with open(f"{self.PROMPT_DIR}/analyze-agent-context.en.md", encoding="utf-8") as f:
            content = f.read()
        assert "estimated" in content.lower()
        assert "confirmed" in content.lower()

    def test_en_prompt_no_trading_decision(self):
        with open(f"{self.PROMPT_DIR}/analyze-agent-context.en.md", encoding="utf-8") as f:
            content = f.read()
        assert "Decision" in content or "decision" in content.lower()


# ── 7. Contract docs match schema version ──────────────────────────────


class TestContractDocsMatchSchemaVersion:
    """Schema version in code must match contract documentation."""

    CONTRACT_PATH = "docs/contracts/agent-context-contract.v1.md"

    def test_schema_version_in_contract_doc(self):
        with open(self.CONTRACT_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "fund_agent_context.v1" in content

    def test_schema_version_in_code_matches(self):
        assert SCHEMA_VERSION == "fund_agent_context.v1"

    def test_reason_codes_in_contract_doc(self):
        with open(self.CONTRACT_PATH, encoding="utf-8") as f:
            content = f.read()
        for code in REASON_CODES:
            assert code in content, f"Reason code {code} not found in contract doc"

    def test_safety_constraints_in_contract_doc(self):
        with open(self.CONTRACT_PATH, encoding="utf-8") as f:
            content = f.read()
        for c in SAFETY_CONSTRAINTS:
            assert c in content, f"Safety constraint {c} not found in contract doc"


# ── 8. Safe/unsafe items match enumeration ─────────────────────────────


class TestSafeUnsafeItemsMatchEnumeration:
    """safe_to_analyze and unsafe_to_infer items must come from enumerations."""

    def test_safe_items_subset_of_enum(self):
        ctx = build_agent_context(_make_summary(overall_status="ok"))
        for item in ctx["safe_to_analyze"]:
            assert item in SAFE_TO_ANALYZE_ITEMS, f"Unknown safe_to_analyze item: {item}"

    def test_unsafe_items_subset_of_enum(self):
        ctx = build_agent_context(_make_summary())
        for item in ctx["unsafe_to_infer"]:
            assert item in UNSAFE_TO_INFER_ITEMS, f"Unknown unsafe_to_infer item: {item}"

    def test_unavailable_status_empty_safe(self):
        ctx = build_agent_context(_make_summary(overall_status="unavailable"))
        assert ctx["safe_to_analyze"] == []
