"""Claude Code official plugin layout validation.

Claude Code expects:
  <plugin-root>/.claude-plugin/plugin.json
  <plugin-root>/skills/<name>/SKILL.md
  <plugin-root>/agents/<name>.md

Skills and agents must be BESIDE .claude-plugin, not inside it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestClaudePluginOfficialLayout:
    def test_plugin_json_at_correct_location(self):
        pj = REPO_ROOT / ".claude-plugin" / "plugin.json"
        assert pj.exists(), f"plugin.json not found at {pj}"

    def test_plugin_json_has_required_fields(self):
        pj = REPO_ROOT / ".claude-plugin" / "plugin.json"
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert data.get("name") == "fund-agent"
        assert data.get("version") == "0.10.5"
        assert "description" in data
        assert data.get("author") == "EXASHXE"

    @pytest.mark.parametrize("skill_name", ["e2e-report", "setup-private-data", "audit-privacy"])
    def test_skill_at_repo_root(self, skill_name):
        """Skills must be at <repo-root>/skills/<name>/SKILL.md, not inside .claude-plugin."""
        skill_md = REPO_ROOT / "skills" / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Skill not at repo root: {skill_md}"

    @pytest.mark.parametrize("agent_name", ["fund-report-e2e.md", "fund-data-auditor.md"])
    def test_agent_at_repo_root(self, agent_name):
        """Agents must be at <repo-root>/agents/<name>.md, not inside .claude-plugin."""
        agent_md = REPO_ROOT / "agents" / agent_name
        assert agent_md.exists(), f"Agent not at repo root: {agent_md}"

    def test_no_skills_nested_inside_claude_plugin_dir(self):
        """Claude Code does not look for skills inside .claude-plugin/."""
        nested_skills = REPO_ROOT / ".claude-plugin" / "skills"
        if nested_skills.exists():
            contents = list(nested_skills.iterdir())
            assert len(contents) == 0, \
                f".claude-plugin/skills/ should be empty — skills moved to repo root. Found: {contents}"

    def test_no_agents_nested_inside_claude_plugin_dir(self):
        """Claude Code does not look for agents inside .claude-plugin/."""
        nested_agents = REPO_ROOT / ".claude-plugin" / "agents"
        if nested_agents.exists():
            contents = list(nested_agents.iterdir())
            assert len(contents) == 0, \
                f".claude-plugin/agents/ should be empty — agents moved to repo root. Found: {contents}"

    def test_e2e_report_has_disable_model_invocation(self):
        skill_md = REPO_ROOT / "skills" / "e2e-report" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert "disable-model-invocation: true" in content.lower(), \
            "e2e-report skill must have disable-model-invocation: true"

    def test_bin_e2e_runner_exists(self):
        assert (REPO_ROOT / "bin" / "fund-agent-e2e").exists()

    def test_bin_privacy_check_exists(self):
        assert (REPO_ROOT / "bin" / "fund-agent-privacy-check").exists()
