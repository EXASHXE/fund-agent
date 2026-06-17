"""OpenCode skill/agent/plugin structure tests."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OPENCODE_DIR = REPO_ROOT / ".opencode"


class TestOpenCodeSkillStructure:
    @pytest.mark.parametrize("skill_name", ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"])
    def test_skill_exists(self, skill_name):
        skill_md = OPENCODE_DIR / "skills" / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Skill missing: {skill_md}"

    @pytest.mark.parametrize("skill_name", ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"])
    def test_skill_has_frontmatter(self, skill_name):
        skill_md = OPENCODE_DIR / "skills" / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---"), f"SKILL.md for {skill_name} missing frontmatter"
        assert "name:" in content.split("---")[1], f"SKILL.md for {skill_name} missing name in frontmatter"
        assert "description:" in content.split("---")[1], f"SKILL.md for {skill_name} missing description in frontmatter"

    @pytest.mark.parametrize("agent_name", ["fund-report-e2e.md", "fund-data-auditor.md"])
    def test_agent_exists(self, agent_name):
        agent_md = OPENCODE_DIR / "agents" / agent_name
        assert agent_md.exists(), f"Agent missing: {agent_md}"

    def test_privacy_plugin_exists(self):
        plugin_ts = OPENCODE_DIR / "plugins" / "fund-agent-privacy-protection.ts"
        assert plugin_ts.exists(), f"Privacy plugin missing: {plugin_ts}"

    def test_install_md_exists(self):
        install_md = OPENCODE_DIR / "INSTALL.md"
        assert install_md.exists(), f"INSTALL.md missing: {install_md}"
