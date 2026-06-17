"""Cross-harness skill consistency tests.

Ensures that the three harness distributions (Claude Code, Codex, OpenCode)
have consistent operation content for equivalent skills.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _skill_body(skill_md_path: Path) -> str:
    """Extract the body of a SKILL.md (after frontmatter)."""
    content = skill_md_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return content.strip()


def _extract_operation_lines(body: str) -> list[str]:
    """Extract key operational lines (commands, pipeline references)."""
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if "bin/fund-agent-e2e" in stripped or "bin/fund-agent-privacy-check" in stripped:
            lines.append(stripped)
        if "fund-agent-e2e" in stripped and "skill" not in stripped.lower():
            lines.append(stripped)
    return lines


class TestHarnessSkillConsistency:
    """The e2e-report / fund-agent-e2e skill should reference bin/fund-agent-e2e across all harnesses."""

    @pytest.mark.parametrize("skill_path", [
        "skills/e2e-report/SKILL.md",
        ".agents/skills/fund-agent-e2e/SKILL.md",
        ".opencode/skills/fund-agent-e2e/SKILL.md",
    ])
    def test_e2e_skill_references_bin_runner(self, skill_path):
        skill_md = REPO_ROOT / skill_path
        content = skill_md.read_text(encoding="utf-8")
        assert "bin/fund-agent-e2e" in content, f"{skill_path} does not reference bin/fund-agent-e2e"

    @pytest.mark.parametrize("skill_path", [
        "skills/audit-privacy/SKILL.md",
        ".agents/skills/fund-agent-privacy-audit/SKILL.md",
        ".opencode/skills/fund-agent-privacy-audit/SKILL.md",
    ])
    def test_privacy_skill_references_bin_runner(self, skill_path):
        skill_md = REPO_ROOT / skill_path
        content = skill_md.read_text(encoding="utf-8")
        assert "bin/fund-agent-privacy-check" in content or "privacy_check" in content, \
            f"{skill_path} does not reference privacy runner"

    @pytest.mark.parametrize("skill_path", [
        "skills/e2e-report/SKILL.md",
        ".agents/skills/fund-agent-e2e/SKILL.md",
        ".opencode/skills/fund-agent-e2e/SKILL.md",
    ])
    def test_e2e_skill_no_private_contents(self, skill_path):
        skill_md = REPO_ROOT / skill_path
        content = skill_md.read_text(encoding="utf-8").lower()
        assert "private_data/" not in content or "never" in content or "must not" in content
        assert "api_key=" not in content
