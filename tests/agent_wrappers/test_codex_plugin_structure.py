"""Codex plugin structure tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CODEX_PLUGIN_DIR = REPO_ROOT / ".codex-plugin"
CODEX_SKILLS_DIR = REPO_ROOT / ".agents" / "skills"


class TestCodexPluginStructure:
    def test_plugin_json_exists(self):
        pj = CODEX_PLUGIN_DIR / "plugin.json"
        assert pj.exists(), f"plugin.json not found at {pj}"

    def test_plugin_json_valid(self):
        pj = CODEX_PLUGIN_DIR / "plugin.json"
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert data.get("name") == "fund-agent"
        assert data.get("version") == "0.10.5"

    def test_codex_readme_exists(self):
        readme = CODEX_PLUGIN_DIR / "README.md"
        assert readme.exists(), f"README.md not found at {readme}"

    @pytest.mark.parametrize("skill_name", ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"])
    def test_skill_exists(self, skill_name):
        skill_md = CODEX_SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Skill missing: {skill_md}"

    @pytest.mark.parametrize("skill_name", ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"])
    def test_skill_has_frontmatter(self, skill_name):
        skill_md = CODEX_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---"), f"SKILL.md for {skill_name} missing frontmatter"
        assert "name:" in content.split("---")[1], f"SKILL.md for {skill_name} missing name in frontmatter"
        assert "description:" in content.split("---")[1], f"SKILL.md for {skill_name} missing description in frontmatter"
