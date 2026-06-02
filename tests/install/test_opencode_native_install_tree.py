"""Native OpenCode Agent Skills install tree smoke test
(v0.4.6 install-packaging-smoke).

This test simulates a real project-local install: a fresh, empty
project directory with a ``.opencode/skills/`` target. It runs
``scripts/install_opencode_skills.py`` against that target and
asserts the resulting install tree matches the contract documented
in ``.opencode/INSTALL.md`` and ``docs/install/opencode.md``:

- Exactly five canonical hyphenated skill directories are written.
- Each contains a valid ``SKILL.md`` with a frontmatter ``name``
  matching the directory slug and a non-empty ``description``.
- ``references/`` subdirectories are copied when the source has
  them.
- No underscore runtime directories, no archived ``fund-analyst``
  persona, and no Python build artifacts are written.
- The marker file ``.fund-agent-generated.json`` lists exactly the
  five canonical skills.
- ``--clean`` removes only the skills this script wrote, leaving
  any user-authored files in the target untouched.

This test does NOT require the OpenCode binary; it only exercises
the sync helper against a temporary directory.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install_opencode_skills.py"
SKILLS_DIR = ROOT / "skills"

CANONICAL_SKILLS = (
    "fund-analysis",
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
)


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
        timeout=30,
    )


def _make_empty_target(parent: Path, name: str) -> Path:
    target = parent / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return target


# ---------------------------------------------------------------------------
# Full install-tree simulation
# ---------------------------------------------------------------------------


def test_install_tree_simulation_full_project(tmp_path: Path):
    """Simulate a fresh project: create ``<project>/.opencode/skills/``,
    run the sync helper, and assert the resulting install tree
    matches the v0.4.6 contract."""
    project = tmp_path / "demo-project"
    project.mkdir()
    target = project / ".opencode" / "skills"
    target.mkdir(parents=True)

    # The target starts empty.
    assert list(target.iterdir()) == [], "fresh .opencode/skills must start empty"

    result = _run(["--target", str(target)])
    assert result.returncode == 0, (
        f"sync failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    # Exactly five skill directories were created.
    created = sorted(p.name for p in target.iterdir() if p.is_dir())
    assert created == sorted(CANONICAL_SKILLS), (
        f"install tree must contain exactly the five canonical skills, "
        f"got {created}"
    )

    # Each skill dir contains a valid SKILL.md.
    for slug in CANONICAL_SKILLS:
        skill_md = target / slug / "SKILL.md"
        assert skill_md.is_file(), (
            f"install tree must include {slug}/SKILL.md at {skill_md}"
        )
        text = skill_md.read_text(encoding="utf-8")
        # Frontmatter must declare name=<slug> and a non-empty description.
        assert text.startswith("---\n"), (
            f"{slug}/SKILL.md must start with YAML frontmatter; got: {text[:60]!r}"
        )
        end = text.find("\n---\n", 4)
        assert end > 0, (
            f"{slug}/SKILL.md must have closing frontmatter; got: {text[:200]!r}"
        )
        front = text[4:end]
        assert f"name: {slug}" in front, (
            f"{slug}/SKILL.md frontmatter must declare 'name: {slug}'; "
            f"frontmatter was: {front!r}"
        )
        # Description must exist and be non-empty (any quoted or
        # unquoted YAML scalar). We accept a non-empty scalar
        # following `description:` on any line within the frontmatter.
        desc_match = re.search(
            r"^description:\s*(.+)$", front, flags=re.MULTILINE
        )
        assert desc_match is not None, (
            f"{slug}/SKILL.md frontmatter must declare a 'description'"
        )
        desc_value = desc_match.group(1).strip()
        # Allow quoted strings or unquoted scalars.
        assert desc_value, (
            f"{slug}/SKILL.md frontmatter description must be non-empty; "
            f"got: {desc_match.group(1)!r}"
        )

    # References copied where source has them.
    for slug in CANONICAL_SKILLS:
        src_refs = SKILLS_DIR / slug / "references"
        if not src_refs.is_dir():
            continue
        dst_refs = target / slug / "references"
        assert dst_refs.is_dir(), (
            f"install tree must include {slug}/references/ at {dst_refs}"
        )
        for path in src_refs.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(src_refs)
            assert (dst_refs / rel).is_file(), (
                f"install tree missing reference: {slug}/references/{rel}"
            )

    # No underscore runtime skill dirs.
    underscore_dirs = [
        p for p in target.iterdir()
        if p.is_dir() and "_" in p.name
    ]
    assert not underscore_dirs, (
        f"install tree must not contain underscore runtime dirs: "
        f"{[p.name for p in underscore_dirs]}"
    )

    # No archived fund-analyst.
    assert not (target / "fund-analyst").exists(), (
        f"install tree must not contain fund-analyst at {target / 'fund-analyst'}"
    )

    # No Python artifacts in the install tree.
    pyc_files = list(target.rglob("*.pyc"))
    assert not pyc_files, (
        f"install tree must not contain .pyc files: {pyc_files}"
    )
    init_files = list(target.rglob("__init__.py"))
    assert not init_files, (
        f"install tree must not contain __init__.py: {init_files}"
    )
    pycache_dirs = [
        p for p in target.rglob("__pycache__") if p.is_dir()
    ]
    assert not pycache_dirs, (
        f"install tree must not contain __pycache__/: {pycache_dirs}"
    )


def test_install_tree_marker_file_lists_exactly_five_skills(tmp_path: Path):
    """The marker file written by the helper must list exactly the
    five canonical hyphenated skills, in canonical order."""
    target = _make_empty_target(tmp_path, "marker-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    marker = target / ".fund-agent-generated.json"
    assert marker.is_file(), "marker file must be written"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload.get("plugin") == "fund-agent"
    assert payload.get("skills") == list(CANONICAL_SKILLS), (
        f"marker must list exactly the five canonical skills, got: "
        f"{payload.get('skills')!r}"
    )
    # No archived or underscore skills in the marker.
    for forbidden in ("fund-analyst", "fund_analysis", "decision_support",
                      "news_research", "sentiment_analysis",
                      "thesis_generation"):
        assert forbidden not in payload.get("skills", []), (
            f"marker must not list '{forbidden}' as a generated skill"
        )


def test_install_tree_clean_removes_only_generated_skills(tmp_path: Path):
    """After ``--clean``, only the five canonical skills and the
    marker are removed. A user-authored skill in the same target
    directory is preserved."""
    target = _make_empty_target(tmp_path, "clean-target")
    # Add a user-authored skill BEFORE running sync so the marker
    # is written by sync and we can verify clean doesn't touch it.
    user_skill = target / "user-skill"
    user_skill.mkdir()
    (user_skill / "SKILL.md").write_text(
        "name: user-skill\ndescription: a user-authored skill\n",
        encoding="utf-8",
    )
    (user_skill / "data.json").write_text('{"user": true}\n', encoding="utf-8")

    # Sync: this writes the five canonical skills and the marker.
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr

    # The user-authored skill must still be there.
    assert (target / "user-skill").is_dir(), "user-authored skill must be preserved"
    assert (target / "user-skill" / "SKILL.md").is_file()

    # The five canonical skills must be there.
    for slug in CANONICAL_SKILLS:
        assert (target / slug).is_dir(), f"{slug} must be present after sync"

    # Run --clean.
    result = _run(["--target", str(target), "--clean"])
    assert result.returncode == 0, result.stderr

    # The five canonical skills must be gone.
    for slug in CANONICAL_SKILLS:
        assert not (target / slug).exists(), (
            f"clean must remove {slug}"
        )
    # The marker must be gone.
    assert not (target / ".fund-agent-generated.json").exists(), (
        "clean must remove the marker"
    )
    # The user-authored skill must still be there.
    assert (target / "user-skill").is_dir(), (
        "clean must not remove user-authored skill dirs"
    )
    assert (target / "user-skill" / "SKILL.md").is_file(), (
        "clean must not remove user-authored skill files"
    )
    assert (target / "user-skill" / "data.json").is_file(), (
        "clean must not remove user-authored skill data"
    )


def test_install_tree_dry_run_does_not_write_anything(tmp_path: Path):
    """``--dry-run`` must not write any files to the target."""
    target = _make_empty_target(tmp_path, "dry-run-target")
    result = _run(["--target", str(target), "--dry-run"])
    assert result.returncode == 0, result.stderr
    # No files or directories were written.
    contents = list(target.iterdir())
    assert contents == [], (
        f"dry-run must not write to target; got: "
        f"{[p.name for p in contents]}"
    )


def test_install_tree_idempotent_under_repeated_apply(tmp_path: Path):
    """Running the sync helper twice in a row is safe: the second
    run produces the same install tree and the marker reflects the
    current run."""
    target = _make_empty_target(tmp_path, "idempotent-target")
    result1 = _run(["--target", str(target)])
    assert result1.returncode == 0, result1.stderr
    contents_after_first = sorted(p.name for p in target.iterdir())
    result2 = _run(["--target", str(target)])
    assert result2.returncode == 0, result2.stderr
    contents_after_second = sorted(p.name for p in target.iterdir())
    # Both runs must produce the same top-level structure.
    assert contents_after_first == contents_after_second, (
        f"idempotent apply must preserve tree, got: {contents_after_first} "
        f"vs {contents_after_second}"
    )
    # The five canonical skills + marker are present.
    for slug in CANONICAL_SKILLS:
        assert (target / slug / "SKILL.md").is_file(), (
            f"idempotent apply must keep {slug}/SKILL.md"
        )
    assert (target / ".fund-agent-generated.json").is_file(), (
        "idempotent apply must keep the marker"
    )


# ---------------------------------------------------------------------------
# Cross-check: install tree == source skills (modulo stale Python files)
# ---------------------------------------------------------------------------


def test_install_tree_skill_md_content_matches_source(tmp_path: Path):
    """The installed SKILL.md must be byte-identical to the source
    SKILL.md. (The sync helper does not rewrite skill contents; the
    install tree is a pure mirror of the source canonical skills.)"""
    target = _make_empty_target(tmp_path, "mirror-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    for slug in CANONICAL_SKILLS:
        src = SKILLS_DIR / slug / "SKILL.md"
        dst = target / slug / "SKILL.md"
        assert dst.read_bytes() == src.read_bytes(), (
            f"installed {slug}/SKILL.md content differs from source"
        )
