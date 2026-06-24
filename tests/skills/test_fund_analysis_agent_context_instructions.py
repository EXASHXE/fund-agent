"""Tests for fund_analysis agent context instructions in SKILL.md.

Validates that the SKILL.md contains the agent-facing personal analysis
package section with required content.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import pytest


SKILL_PATH = "skills/fund-analysis/SKILL.md"


def _read_skill() -> str:
    with open(SKILL_PATH, encoding="utf-8") as f:
        return f.read()


class TestSkillAgentContextSection:
    """SKILL.md must have an agent-facing personal analysis package section."""

    def test_has_agent_facing_section(self):
        content = _read_skill()
        assert "Agent-facing personal analysis package" in content

    def test_references_personal_run_command(self):
        content = _read_skill()
        assert "bin/fund-agent-personal-run" in content

    def test_references_agent_context_only_flag(self):
        content = _read_skill()
        assert "--agent-context-only" in content

    def test_references_reading_order(self):
        content = _read_skill()
        assert "agent_context.json" in content
        assert "agent_context.md" in content
        assert "personal_health_report.json" in content

    def test_forbids_formal_decision(self):
        content = _read_skill()
        assert "formal" in content.lower()
        assert "Decision" in content

    def test_forbids_broker_orders(self):
        content = _read_skill()
        assert "broker" in content.lower() or "order execution" in content.lower()

    def test_forbids_auto_trading(self):
        content = _read_skill()
        assert "auto trading" in content.lower() or "Auto-trade" in content

    def test_estimated_not_confirmed(self):
        content = _read_skill()
        assert "estimated" in content.lower()
        assert "confirmed" in content.lower()

    def test_partial_not_complete(self):
        content = _read_skill()
        # Must mention that partial valuation is not complete market value
        assert "partial" in content.lower()

    def test_references_prompt_templates(self):
        content = _read_skill()
        assert "docs/agent-integration/prompts/" in content

    def test_references_contract(self):
        content = _read_skill()
        assert "agent-context-contract.v1.md" in content

    def test_references_consumption_contract(self):
        content = _read_skill()
        assert "agent-context-consumption-contract.md" in content

    def test_has_agent_output_limits(self):
        content = _read_skill()
        assert "Agent output limits" in content or "output limits" in content.lower()

    def test_has_response_structure(self):
        content = _read_skill()
        assert "Agent response structure" in content or "response structure" in content.lower()


class TestSkillReportTemplateAgentSection:
    """report-template.md must reference agent consumption."""

    REPORT_TEMPLATE_PATH = "skills/fund-analysis/references/report-template.md"

    def test_report_template_references_agent_consumption(self):
        with open(self.REPORT_TEMPLATE_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "agent_context" in content or "Agent consumption" in content
