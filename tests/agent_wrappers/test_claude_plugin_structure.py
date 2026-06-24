"""Claude Code plugin structure tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLAUDE_PLUGIN_DIR = REPO_ROOT / ".claude-plugin"
CLAUDE_SKILLS_DIR = REPO_ROOT / "skills"
CLAUDE_AGENTS_DIR = REPO_ROOT / "agents"


class TestClaudePluginStructure:
    def test_plugin_json_exists(self):
        pj = CLAUDE_PLUGIN_DIR / "plugin.json"
        assert pj.exists(), f"plugin.json not found at {pj}"

    def test_plugin_json_valid(self):
        pj = CLAUDE_PLUGIN_DIR / "plugin.json"
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert data.get("name") == "fund-agent"
        assert data.get("version") == "0.10.5"
        assert "description" in data
        assert data.get("author") == "EXASHXE"

    @pytest.mark.parametrize("skill_name", ["e2e-report", "setup-private-data", "audit-privacy"])
    def test_skill_exists(self, skill_name):
        skill_md = CLAUDE_SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Skill missing: {skill_md}"

    @pytest.mark.parametrize("skill_name", ["e2e-report", "setup-private-data", "audit-privacy"])
    def test_skill_has_frontmatter(self, skill_name):
        skill_md = CLAUDE_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---"), f"SKILL.md for {skill_name} missing frontmatter"
        assert "name:" in content.split("---")[1], f"SKILL.md for {skill_name} missing name in frontmatter"
        assert "description:" in content.split("---")[1], f"SKILL.md for {skill_name} missing description in frontmatter"

    @pytest.mark.parametrize("agent_name", ["fund-report-e2e.md", "fund-data-auditor.md"])
    def test_agent_exists(self, agent_name):
        agent_md = CLAUDE_AGENTS_DIR / agent_name
        assert agent_md.exists(), f"Agent missing: {agent_md}"

    def test_no_nested_skills_in_plugin_dir(self):
        """Claude Code expects skills/ beside .claude-plugin, not inside it."""
        nested = CLAUDE_PLUGIN_DIR / "skills"
        assert not nested.exists() or not any(nested.iterdir()), \
            "skills/ should not exist inside .claude-plugin/ — move to repo root skills/"

    def test_no_nested_agents_in_plugin_dir(self):
        """Claude Code expects agents/ beside .claude-plugin, not inside it."""
        nested = CLAUDE_PLUGIN_DIR / "agents"
        assert not nested.exists() or not any(nested.iterdir()), \
            "agents/ should not exist inside .claude-plugin/ — move to repo root agents/"
