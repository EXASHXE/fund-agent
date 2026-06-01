"""Superpowers-compatible skill surface tests.

The v0.4.4+ skill surface is a **composable collection of hyphenated
Markdown skills**, Superpowers-style: one `skills/<slug>/SKILL.md`
directory per skill, with the directory name matching the skill's
frontmatter `name` field.

- Primary / default skill: `fund-analysis`
- Supporting skills: `decision-support`, `news-research`,
  `sentiment-analysis`, `thesis-generation`

These tests guard the shape of that surface: canonical hyphenated
directories, frontmatter `name` matching the directory, primary /
supporting role metadata, and the absence of legacy underscore
directories and the archived `fund-analyst` persona directory.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
MANIFEST = ROOT / "skillpack" / "fund-agent.skillpack.yaml"

EXPECTED_PRIMARY = "fund-analysis"
EXPECTED_SUPPORTING = [
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
]
ALL_EXPECTED_SLUGS = [EXPECTED_PRIMARY] + EXPECTED_SUPPORTING


def _manifest_skill_ids() -> list[str]:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    return [skill["name"] for skill in manifest["skills"]]


def _slug(skill_id: str) -> str:
    return skill_id.replace("_", "-")


def _read_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{skill_md} must start with YAML frontmatter"
    end = text.find("\n---", 3)
    assert end > 0, f"{skill_md} frontmatter must be closed"
    return yaml.safe_load(text[3:end])


# ---------------------------------------------------------------------------
# Canonical hyphenated SKILL.md directories
# ---------------------------------------------------------------------------


def test_canonical_hyphenated_skill_dirs_exist():
    """The five canonical hyphenated SKILL.md directories must exist
    and contain a SKILL.md file. These are the only agent-facing skill
    directories in v0.4.4+."""
    for slug in ALL_EXPECTED_SLUGS:
        path = SKILLS_DIR / slug / "SKILL.md"
        assert path.exists(), f"missing canonical SKILL.md for '{slug}'"


def test_canonical_skill_md_files_have_minimum_size():
    """Canonical SKILL.md files must not be empty placeholders."""
    for slug in ALL_EXPECTED_SLUGS:
        path = SKILLS_DIR / slug / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) >= 30, (
            f"{path} looks too short to be a real skill doc"
        )


# ---------------------------------------------------------------------------
# Frontmatter `name` must match the directory name
# ---------------------------------------------------------------------------


def test_frontmatter_name_matches_directory():
    """Each canonical SKILL.md's frontmatter `name` field must be the
    hyphenated Markdown doc slug and must match its directory name."""
    for slug in ALL_EXPECTED_SLUGS:
        path = SKILLS_DIR / slug / "SKILL.md"
        frontmatter = _read_frontmatter(path)
        assert frontmatter.get("name") == slug, (
            f"{path} frontmatter name {frontmatter.get('name')!r} "
            f"does not match directory name '{slug}'"
        )


def test_frontmatter_id_is_underscore_runtime_id():
    """Each canonical SKILL.md's frontmatter `id` field must be the
    underscore Python runtime ID (the manifest runtime_id)."""
    manifest_ids = _manifest_skill_ids()
    for slug in ALL_EXPECTED_SLUGS:
        path = SKILLS_DIR / slug / "SKILL.md"
        frontmatter = _read_frontmatter(path)
        underscore_id = slug.replace("-", "_")
        assert frontmatter.get("id") == underscore_id, (
            f"{path} frontmatter id {frontmatter.get('id')!r} "
            f"does not match underscore runtime ID '{underscore_id}'"
        )
        assert underscore_id in manifest_ids, (
            f"{path} frontmatter id '{underscore_id}' is not in the manifest"
        )


# ---------------------------------------------------------------------------
# Primary / supporting role metadata
# ---------------------------------------------------------------------------


def test_fund_analysis_is_marked_primary_in_frontmatter():
    """fund-analysis is the primary / default skill. Its frontmatter
    must mark the role as primary."""
    path = SKILLS_DIR / EXPECTED_PRIMARY / "SKILL.md"
    frontmatter = _read_frontmatter(path)
    assert frontmatter.get("role") == "primary", (
        f"{path} frontmatter role {frontmatter.get('role')!r} "
        f"must be 'primary'"
    )


def test_supporting_skills_are_marked_supporting_in_frontmatter():
    """Each supporting skill's frontmatter must mark the role as
    supporting."""
    for slug in EXPECTED_SUPPORTING:
        path = SKILLS_DIR / slug / "SKILL.md"
        frontmatter = _read_frontmatter(path)
        assert frontmatter.get("role") == "supporting", (
            f"{path} frontmatter role {frontmatter.get('role')!r} "
            f"must be 'supporting'"
        )


def test_fund_analysis_doc_has_default_entrypoint_section():
    """fund-analysis must be the recommended default entrypoint. Its
    SKILL.md must include a 'Default entrypoint' section and a 'When
    to load supporting skills' table."""
    path = SKILLS_DIR / EXPECTED_PRIMARY / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^##\s+Default entrypoint\b", text, re.MULTILINE), (
        f"{path} must have a '## Default entrypoint' section"
    )
    assert "When to load supporting skills" in text, (
        f"{path} must have a 'When to load supporting skills' section"
    )
    # The four supporting slugs must all be mentioned in the table.
    for slug in EXPECTED_SUPPORTING:
        assert f"`{slug}`" in text, (
            f"{path} must mention supporting skill `{slug}` in its table"
        )


def test_supporting_skills_doc_have_supporting_skill_preamble():
    """Each supporting skill's SKILL.md must clearly mark itself as a
    supporting skill in the v0.4.4+ Superpowers-compatible surface."""
    for slug in EXPECTED_SUPPORTING:
        path = SKILLS_DIR / slug / "SKILL.md"
        text = path.read_text(encoding="utf-8").lower()
        assert "supporting skill" in text, (
            f"{path} must say it is a 'supporting skill'"
        )
        # Each supporting skill must say `fund-analysis` is the
        # primary / default and that it should only be loaded when
        # the subtask matches.
        assert "fund-analysis" in text, (
            f"{path} must reference the primary skill 'fund-analysis'"
        )


# ---------------------------------------------------------------------------
# No underscore skill directories
# ---------------------------------------------------------------------------


def test_no_underscore_skill_dir_under_skills_root():
    """No underscore `skills/<x>/` directory is part of the v0.4.4+
    surface. The only canonical skill directories are the five
    hyphenated slugs."""
    for entry in SKILLS_DIR.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("__"):
            continue
        assert "_" not in entry.name, (
            f"underscore skill directory {entry} is not part of the "
            f"v0.4.4+ skill surface; remove it or move its content to "
            f"the canonical hyphenated SKILL.md directory"
        )


def test_no_underscore_skill_dir_contains_skill_md():
    """For belt-and-braces: no directory under `skills/` whose name
    contains an underscore may contain a `SKILL.md` file. Such a
    file would risk being discovered as an agent-facing skill."""
    for entry in SKILLS_DIR.iterdir():
        if not entry.is_dir():
            continue
        if "_" not in entry.name:
            continue
        skill_md = entry / "SKILL.md"
        assert not skill_md.exists(), (
            f"{skill_md} exists in underscore directory '{entry.name}'; "
            f"v0.4.4+ skill surface is hyphenated only"
        )


def test_fund_analyst_dir_absent_from_skills_root():
    """The legacy `skills/fund-analyst/` persona directory has been
    archived to `docs/archive/fund-analyst/` and must not be present
    under `skills/`."""
    assert not (SKILLS_DIR / "fund-analyst").exists(), (
        "skills/fund-analyst/ has been archived to docs/archive/fund-analyst/"
    )


def test_fund_analyst_archive_dir_exists():
    """The archived legacy persona material must live under
    `docs/archive/fund-analyst/`, with a README explaining its status."""
    archive_dir = ROOT / "docs" / "archive" / "fund-analyst"
    assert archive_dir.is_dir(), (
        f"{archive_dir} must exist as the archive location for the "
        f"legacy persona material"
    )
    readme = archive_dir / "README.md"
    assert readme.exists(), (
        f"{readme} must explain the archive status"
    )
    readme_text = readme.read_text(encoding="utf-8").lower()
    assert "archived" in readme_text or "archive" in readme_text, (
        f"{readme} must mark the directory as archived"
    )
    assert "not a runtime" in readme_text or "not installed" in readme_text, (
        f"{readme} must mark the directory as not a runtime skill"
    )
