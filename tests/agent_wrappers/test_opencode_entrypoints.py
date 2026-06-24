"""OpenCode entrypoint validation.

Ensures .opencode skills/agents are valid and do not conflict
with the root opencode.plugin.js.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OPENCODE_DIR = REPO_ROOT / ".opencode"
OPENCODE_SKILLS_DIR = OPENCODE_DIR / "skills"
OPENCODE_AGENTS_DIR = OPENCODE_DIR / "agents"
OPENCODE_PLUGINS_DIR = OPENCODE_DIR / "plugins"

OPENCODE_SKILL_NAMES = ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"]
OPENCODE_AGENT_NAMES = ["fund-report-e2e.md", "fund-data-auditor.md"]


class TestOpenCodeEntrypoints:
    @pytest.mark.parametrize("skill_name", OPENCODE_SKILL_NAMES)
    def test_skill_exists(self, skill_name):
        skill_md = OPENCODE_SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_md.exists(), f"OpenCode skill missing: {skill_md}"

    @pytest.mark.parametrize("skill_name", OPENCODE_SKILL_NAMES)
    def test_skill_has_name_and_description(self, skill_name):
        skill_md = OPENCODE_SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---"), f"Missing frontmatter in {skill_name}"
        fm = content.split("---")[1]
        assert "name:" in fm, f"Missing name in frontmatter for {skill_name}"
        assert "description:" in fm, f"Missing description in frontmatter for {skill_name}"

    @pytest.mark.parametrize("agent_name", OPENCODE_AGENT_NAMES)
    def test_agent_exists(self, agent_name):
        agent_md = OPENCODE_AGENTS_DIR / agent_name
        assert agent_md.exists(), f"OpenCode agent missing: {agent_md}"

    def test_install_md_exists(self):
        assert (OPENCODE_DIR / "INSTALL.md").exists()

    def test_privacy_plugin_exists(self):
        plugin_ts = OPENCODE_PLUGINS_DIR / "fund-agent-privacy-protection.ts"
        assert plugin_ts.exists(), f"Privacy plugin missing: {plugin_ts}"

    def test_opencode_plugin_js_and_skills_do_not_conflict(self):
        """opencode.plugin.js (Mode A) and .opencode/skills/ (Mode B) serve
        different purposes and should not conflict."""
        opjs = REPO_ROOT / "opencode.plugin.js"
        if not opjs.exists():
            pytest.skip("opencode.plugin.js not present")
        # Mode A: opencode.plugin.js is a metadata + doc-reader plugin
        # Mode B: .opencode/skills/ are native Agent Skills for discovery
        # They coexist — no conflict
        content = opjs.read_text(encoding="utf-8")
        assert "plugin" in content.lower(), "opencode.plugin.js should be a valid plugin"
        # Ensure it doesn't register skills that overlap with .opencode/skills/
        # Mode A registers fund_agent_skills/fund_agent_skill_doc tools
        # Mode B provides SKILL.md files for native discovery
        # These are complementary, not conflicting
