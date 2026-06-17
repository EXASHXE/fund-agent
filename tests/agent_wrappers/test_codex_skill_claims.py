"""Codex skill claims validation.

Ensures .agents/skills/ are valid and .codex-plugin does not
claim marketplace readiness.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CODEX_PLUGIN_DIR = REPO_ROOT / ".codex-plugin"
CODEX_SKILLS_DIR = REPO_ROOT / ".agents" / "skills"

CODEX_SKILL_NAMES = ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"]


class TestCodexSkillClaims:
    @pytest.mark.parametrize("skill_name", CODEX_SKILL_NAMES)
    def test_skill_exists(self, skill_name):
        skill_md = CODEX_SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Codex skill missing: {skill_md}"

    @pytest.mark.parametrize("skill_name", CODEX_SKILL_NAMES)
    def test_skill_has_name_and_description(self, skill_name):
        skill_md = CODEX_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---"), f"Missing frontmatter in {skill_name}"
        fm = content.split("---")[1]
        assert "name:" in fm, f"Missing name in frontmatter for {skill_name}"
        assert "description:" in fm, f"Missing description in frontmatter for {skill_name}"

    @pytest.mark.parametrize("skill_name", CODEX_SKILL_NAMES)
    def test_skill_names_are_unique(self, skill_name):
        """Each skill directory name should be unique (parameterized ensures no dupes)."""
        skill_md = CODEX_SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_md.exists()

    def test_codex_plugin_json_does_not_claim_marketplace(self):
        pj = CODEX_PLUGIN_DIR / "plugin.json"
        if not pj.exists():
            pytest.skip(".codex-plugin/plugin.json not present")
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert "marketplace" not in str(data).lower(), \
            ".codex-plugin/plugin.json should not claim marketplace readiness"

    def test_codex_plugin_marked_experimental(self):
        pj = CODEX_PLUGIN_DIR / "plugin.json"
        if not pj.exists():
            pytest.skip(".codex-plugin/plugin.json not present")
        content = pj.read_text(encoding="utf-8")
        assert "experimental" in content.lower() or "not yet stable" in content.lower(), \
            ".codex-plugin/plugin.json should mark itself as experimental"

    def test_codex_readme_says_not_marketplace_ready(self):
        readme = CODEX_PLUGIN_DIR / "README.md"
        if not readme.exists():
            pytest.skip(".codex-plugin/README.md not present")
        content = readme.read_text(encoding="utf-8").lower()
        assert "not implemented" in content or "not yet" in content or "experimental" in content, \
            ".codex-plugin/README.md must clearly state marketplace publishing is not implemented"
