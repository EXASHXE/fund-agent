"""Architecture tests for the v0.4.4+ skill surface.

The skill surface in v0.4.4+ has no underscore `skills/<x>/`
directories. The legacy `skills/fund-analyst/` persona directory has
been archived to `docs/archive/fund-analyst/`. The `legacy/`
directory remains pointer-only (README.md only). The optional
`tests/deprecated` directory does not exist.

These tests guard the directory structure:

1. `skills/fund-analyst/` does not exist.
2. `docs/archive/fund-analyst/` exists with a README explaining the
   archive status.
3. `legacy/` is pointer-only (no implementation files).
4. `tests/deprecated` does not exist.
5. No underscore `skills/<x>/` directory exists.
6. No underscore skill directory contains a `SKILL.md` file.
"""
from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"
ARCHIVE_DIR = ROOT / "docs" / "archive" / "fund-analyst"
LEGACY_DIR = ROOT / "legacy"
TESTS_DIR = ROOT / "tests"


def _list_skill_dirs() -> list[Path]:
    """List top-level entries under skills/ that are real directories."""
    if not SKILLS_DIR.is_dir():
        return []
    out: list[Path] = []
    for entry in SKILLS_DIR.iterdir():
        if entry.is_dir() and not entry.name.startswith("__"):
            out.append(entry)
    return out


# ---------------------------------------------------------------------------
# skills/fund-analyst/ must be absent
# ---------------------------------------------------------------------------


def test_skills_fund_analyst_dir_absent():
    """The legacy `skills/fund-analyst/` persona directory must not
    exist; it has been moved to `docs/archive/fund-analyst/`."""
    path = SKILLS_DIR / "fund-analyst"
    assert not path.exists(), (
        f"{path} must be absent; the legacy persona material has been "
        f"archived to {ARCHIVE_DIR}"
    )


def test_docs_archive_fund_analyst_dir_exists():
    """The archived persona material must live under
    `docs/archive/fund-analyst/`, with a README and SKILL.md marking
    the archive status."""
    assert ARCHIVE_DIR.is_dir(), (
        f"{ARCHIVE_DIR} must exist as the archive location for the "
        f"legacy persona material"
    )
    readme = ARCHIVE_DIR / "README.md"
    skill_md = ARCHIVE_DIR / "SKILL.md"
    assert readme.exists(), f"{readme} must exist"
    assert skill_md.exists(), f"{skill_md} must exist"
    readme_text = readme.read_text(encoding="utf-8").lower()
    assert "archived" in readme_text or "archive" in readme_text, (
        f"{readme} must mark the directory as archived"
    )
    assert "not a runtime" in readme_text or "not installed" in readme_text, (
        f"{readme} must say it is not a runtime skill / not installed"
    )


# ---------------------------------------------------------------------------
# legacy/ must remain pointer-only
# ---------------------------------------------------------------------------


def test_legacy_dir_is_pointer_only():
    """`legacy/` must remain pointer-only: it may contain only
    `README.md` (and standard build artefacts like `__pycache__/`).
    No implementation files are allowed."""
    if not LEGACY_DIR.is_dir():
        return  # legacy/ absent is also acceptable
    allowed = {"README.md", "__pycache__", ".gitkeep"}
    for entry in LEGACY_DIR.iterdir():
        if entry.name in allowed:
            continue
        # Anything else is unexpected.
        assert False, (
            f"{entry} is not allowed under legacy/; legacy/ must be "
            f"pointer-only. Allowed: {sorted(allowed)}"
        )


def test_legacy_readme_points_to_v0_1_0_alpha_tag():
    """If `legacy/README.md` exists, it must reference the
    `v0.1.0-skillpack-alpha` tag as the historical archive location."""
    readme = LEGACY_DIR / "README.md"
    if not readme.exists():
        return
    text = readme.read_text(encoding="utf-8")
    assert "v0.1.0-skillpack-alpha" in text, (
        f"{readme} must point to the v0.1.0-skillpack-alpha tag"
    )


# ---------------------------------------------------------------------------
# tests/deprecated must not exist
# ---------------------------------------------------------------------------


def test_tests_deprecated_does_not_exist():
    """The optional `tests/deprecated` directory must not exist in
    v0.4.4+. Deprecated tests should be removed entirely."""
    deprecated = TESTS_DIR / "deprecated"
    assert not deprecated.exists(), (
        f"{deprecated} must not exist; v0.4.4+ removes deprecated tests"
    )


# ---------------------------------------------------------------------------
# No underscore skill directories
# ---------------------------------------------------------------------------


def test_no_underscore_skill_dir_in_skills_root():
    """No underscore `skills/<x>/` directory is part of the v0.4.4+
    skill surface. The canonical skill directories are the five
    hyphenated slugs only."""
    for entry in _list_skill_dirs():
        assert "_" not in entry.name, (
            f"underscore skill directory {entry} is not part of the "
            f"v0.4.4+ skill surface; remove it or move its content to "
            f"the canonical hyphenated SKILL.md directory"
        )


def test_no_underscore_skill_dir_contains_skill_md():
    """For belt-and-braces: no directory under `skills/` whose name
    contains an underscore may contain a `SKILL.md` file. Such a
    file would risk being discovered as an agent-facing skill."""
    for entry in _list_skill_dirs():
        if "_" not in entry.name:
            continue
        skill_md = entry / "SKILL.md"
        assert not skill_md.exists(), (
            f"{skill_md} exists in underscore directory '{entry.name}'; "
            f"v0.4.4+ skill surface is hyphenated only"
        )


def test_only_canonical_hyphenated_skill_dirs_under_skills():
    """The only top-level skill directories under `skills/` are the
    five canonical hyphenated slugs: `fund-analysis`,
    `decision-support`, `news-research`, `sentiment-analysis`,
    `thesis-generation`."""
    expected = {
        "fund-analysis",
        "decision-support",
        "news-research",
        "sentiment-analysis",
        "thesis-generation",
    }
    actual = {entry.name for entry in _list_skill_dirs()}
    unexpected = actual - expected
    missing = expected - actual
    assert not unexpected, (
        f"unexpected hyphenated skill directories: {sorted(unexpected)}"
    )
    assert not missing, (
        f"missing canonical skill directories: {sorted(missing)}"
    )
