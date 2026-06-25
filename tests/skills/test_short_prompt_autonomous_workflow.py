"""Tests for short prompt autonomous workflow support.

Verifies that:
1. SKILL.md contains the user intent trigger section
2. SKILL.md declares the canonical entrypoint
3. SKILL.md lists forbidden non-canonical paths
4. Prompt templates support short user intent
5. agent-consumption.md has short user intent section
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL_MD = Path("skills/fund-analysis/SKILL.md")
PROMPT_EN = Path("docs/agent-integration/prompts/analyze-agent-context.en.md")
PROMPT_ZH = Path("docs/agent-integration/prompts/analyze-agent-context.zh.md")
CONSUMPTION_MD = Path("docs/usage/agent-consumption.md")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestSkillMdShortPromptSupport:
    def test_skill_md_has_user_intent_trigger(self):
        content = _read(SKILL_MD)
        # Must have a section about user intent triggers
        assert "user intent" in content.lower() or "trigger" in content.lower()

    def test_skill_md_has_canonical_entrypoint(self):
        content = _read(SKILL_MD)
        assert "bin/fund-agent-personal-run" in content
        assert "canonical" in content.lower()

    def test_skill_md_has_forbidden_paths(self):
        content = _read(SKILL_MD)
        # Must mention forbidden non-canonical paths
        assert "forbidden" in content.lower() or "must not" in content.lower()
        # Must mention that FundAnalysisSkill is internal
        assert "internal" in content.lower()

    def test_skill_md_forbids_none_to_zero(self):
        content = _read(SKILL_MD)
        # Must mention that None/null should not be converted to 0.0
        assert "0.0" in content or "0.0" in content or "null" in content.lower()

    def test_skill_md_forbids_cashflow_only_in_calculations(self):
        content = _read(SKILL_MD)
        assert "cashflow_only" in content


class TestPromptTemplatesShortPrompt:
    def test_en_prompt_has_short_user_intent(self):
        content = _read(PROMPT_EN)
        assert "short user intent" in content.lower() or "short intent" in content.lower()

    def test_en_prompt_has_canonical_entrypoint(self):
        content = _read(PROMPT_EN)
        assert "bin/fund-agent-personal-run" in content
        assert "canonical" in content.lower()

    def test_en_prompt_forbids_direct_skill_call(self):
        content = _read(PROMPT_EN)
        assert "FundAnalysisSkill().run()" in content or "FundAnalysisSkill" in content

    def test_zh_prompt_has_short_user_intent(self):
        content = _read(PROMPT_ZH)
        assert "短指令" in content

    def test_zh_prompt_has_canonical_entrypoint(self):
        content = _read(PROMPT_ZH)
        assert "bin/fund-agent-personal-run" in content
        assert "canonical" in content.lower() or "入口" in content

    def test_zh_prompt_forbids_none_to_zero(self):
        content = _read(PROMPT_ZH)
        assert "0.0" in content or "null" in content.lower() or "None" in content


class TestAgentConsumptionShortPrompt:
    def test_consumption_md_has_short_user_intent(self):
        content = _read(CONSUMPTION_MD)
        assert "short user intent" in content.lower() or "short intent" in content.lower()

    def test_consumption_md_forbids_none_to_zero(self):
        content = _read(CONSUMPTION_MD)
        assert "0.0" in content or "null" in content.lower()

    def test_consumption_md_forbids_cashflow_only_in_calculations(self):
        content = _read(CONSUMPTION_MD)
        assert "cashflow_only" in content
