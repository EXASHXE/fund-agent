"""Manifest <-> SKILL.md frontmatter consistency tests.

For each canonical skill, read skills/<slug>/SKILL.md frontmatter and
verify it matches the manifest. Also enforce canonical skill directory
structure rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "skillpack" / "fund-agent.skillpack.yaml"
SKILLS_DIR = ROOT / "skills"

CANONICAL_SKILL_SLUGS = {
    "fund-analysis",
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
}


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _manifest_skills_by_name() -> dict[str, dict]:
    return {s["name"]: s for s in _manifest()["skills"]}


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a SKILL.md file."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1))


def _read_skill_frontmatter(slug: str) -> dict:
    path = SKILLS_DIR / slug / "SKILL.md"
    assert path.exists(), f"Missing SKILL.md for slug '{slug}' at {path}"
    text = path.read_text(encoding="utf-8")
    return _parse_frontmatter(text)


class TestFrontmatterMatchesManifest:
    """For each canonical skill, validate frontmatter fields match manifest."""

    @classmethod
    def _slug_to_runtime_id(cls, slug: str) -> str:
        return slug.replace("-", "_")

    def test_frontmatter_id_matches_manifest_runtime_name(self):
        manifest_skills = _manifest_skills_by_name()
        for slug in sorted(CANONICAL_SKILL_SLUGS):
            fm = _read_skill_frontmatter(slug)
            expected_id = self._slug_to_runtime_id(slug)
            actual_id = fm.get("id")
            assert actual_id == expected_id, (
                f"skills/{slug}/SKILL.md frontmatter id={actual_id!r} "
                f"!= manifest runtime name={expected_id!r}"
            )

    def test_frontmatter_name_matches_hyphenated_slug(self):
        for slug in sorted(CANONICAL_SKILL_SLUGS):
            fm = _read_skill_frontmatter(slug)
            actual_name = fm.get("name")
            assert actual_name == slug, (
                f"skills/{slug}/SKILL.md frontmatter name={actual_name!r} "
                f"!= hyphenated slug={slug!r}"
            )

    def test_frontmatter_runtime_matches_manifest(self):
        manifest_skills = _manifest_skills_by_name()
        for slug in sorted(CANONICAL_SKILL_SLUGS):
            fm = _read_skill_frontmatter(slug)
            runtime_id = self._slug_to_runtime_id(slug)
            expected_runtime = manifest_skills[runtime_id]["runtime"]
            actual_runtime = fm.get("runtime")
            assert actual_runtime == expected_runtime, (
                f"skills/{slug}/SKILL.md frontmatter runtime={actual_runtime!r} "
                f"!= manifest runtime={expected_runtime!r}"
            )

    def test_frontmatter_input_schema_matches_manifest(self):
        manifest_skills = _manifest_skills_by_name()
        for slug in sorted(CANONICAL_SKILL_SLUGS):
            fm = _read_skill_frontmatter(slug)
            runtime_id = self._slug_to_runtime_id(slug)
            expected = manifest_skills[runtime_id]["input_schema"]
            actual = fm.get("input_schema")
            assert actual == expected, (
                f"skills/{slug}/SKILL.md frontmatter input_schema={actual!r} "
                f"!= manifest input_schema={expected!r}"
            )

    def test_frontmatter_output_schema_matches_manifest(self):
        manifest_skills = _manifest_skills_by_name()
        for slug in sorted(CANONICAL_SKILL_SLUGS):
            fm = _read_skill_frontmatter(slug)
            runtime_id = self._slug_to_runtime_id(slug)
            expected = manifest_skills[runtime_id]["output_schema"]
            actual = fm.get("output_schema")
            assert actual == expected, (
                f"skills/{slug}/SKILL.md frontmatter output_schema={actual!r} "
                f"!= manifest output_schema={expected!r}"
            )

    def test_frontmatter_required_mcp_capabilities_matches_manifest(self):
        manifest_skills = _manifest_skills_by_name()
        for slug in sorted(CANONICAL_SKILL_SLUGS):
            fm = _read_skill_frontmatter(slug)
            runtime_id = self._slug_to_runtime_id(slug)
            expected = sorted(manifest_skills[runtime_id].get("requires_mcp", []))
            actual = sorted(fm.get("required_mcp_capabilities", []))
            assert actual == expected, (
                f"skills/{slug}/SKILL.md frontmatter "
                f"required_mcp_capabilities={actual!r} "
                f"!= manifest requires_mcp={expected!r}"
            )

    def test_frontmatter_role_matches_manifest(self):
        manifest_skills = _manifest_skills_by_name()
        for slug in sorted(CANONICAL_SKILL_SLUGS):
            fm = _read_skill_frontmatter(slug)
            runtime_id = self._slug_to_runtime_id(slug)
            expected = manifest_skills[runtime_id].get("role", "supporting")
            actual = fm.get("role")
            assert actual == expected, (
                f"skills/{slug}/SKILL.md frontmatter role={actual!r} "
                f"!= manifest role={expected!r}"
            )


class TestCanonicalSkillDirectoryStructure:
    """Enforce canonical skill directory rules."""

    def test_canonical_skill_directories_are_exactly_the_five(self):
        actual_dirs = set()
        for entry in SKILLS_DIR.iterdir():
            if entry.is_dir() and (entry / "SKILL.md").exists():
                actual_dirs.add(entry.name)
        assert actual_dirs == CANONICAL_SKILL_SLUGS, (
            f"Skill directories with SKILL.md: {sorted(actual_dirs)} != "
            f"expected canonical: {sorted(CANONICAL_SKILL_SLUGS)}"
        )

    def test_no_underscore_skill_directory(self):
        for entry in SKILLS_DIR.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            if name.startswith("__") and name.endswith("__"):
                continue
            if name.startswith("."):
                continue
            assert "_" not in name, (
                f"skills/ contains underscore directory '{name}'. "
                f"Agent-facing skill directories must use hyphenated slugs."
            )

    def test_no_fund_analyst_skill_directory(self):
        fa_path = SKILLS_DIR / "fund-analyst"
        assert not (fa_path / "SKILL.md").exists(), (
            "skills/fund-analyst/SKILL.md exists but fund-analyst is "
            "archived legacy material and must not be an installable skill."
        )

    def test_manifest_does_not_reference_fund_analyst(self):
        data = _manifest()
        serialized = yaml.safe_dump(data)
        assert "fund-analyst" not in serialized, (
            "skillpack manifest references 'fund-analyst' as a runtime "
            "entrypoint or installable skill. fund-analyst is archived."
        )

    def test_plugin_does_not_reference_fund_analyst(self):
        plugin_path = ROOT / "opencode.plugin.js"
        text = plugin_path.read_text(encoding="utf-8")
        catalog_match = re.search(
            r"const SKILL_CATALOG\s*=\s*Object\.freeze\(\[(.+?)\]\)",
            text,
            re.DOTALL,
        )
        assert catalog_match, "Could not find SKILL_CATALOG in opencode.plugin.js"
        catalog_body = catalog_match.group(1)
        assert "fund-analyst" not in catalog_body, (
            "opencode.plugin.js SKILL_CATALOG references 'fund-analyst'. "
            "fund-analyst is archived legacy material and must not be "
            "exposed as an installable skill."
        )

    def test_docs_archive_fund_analyst_not_referenced_as_runtime_entrypoint(self):
        manifest = _manifest()
        for skill in manifest["skills"]:
            assert "fund-analyst" not in skill.get("runtime", ""), (
                f"manifest skill '{skill['name']}' runtime references "
                f"fund-analyst: {skill['runtime']!r}"
            )
