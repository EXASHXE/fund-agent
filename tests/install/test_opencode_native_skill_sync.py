"""Tests for scripts/install_opencode_skills.py — the v0.4.5 native
OpenCode Agent Skills sync helper.

The helper is a plain file copy. It must:

- List the five canonical hyphenated skills in dry-run.
- Copy exactly those five skills in apply mode (no archived
  ``fund-analyst``, no underscore runtime IDs, no other repo
  metadata).
- Preserve SKILL.md and references/ for each skill.
- Refuse to --clean a target that has no marker file.
- Remove only the skills it wrote, leaving user-authored files
  alone.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

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
FORBIDDEN_SKILLS = (
    "fund-analyst",  # archived persona
    "fund_analysis",  # underscore runtime
    "news_research",
    "sentiment_analysis",
    "thesis_generation",
)


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
        timeout=30,
    )


def _make_target(parent: Path, name: str) -> Path:
    target = parent / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return target


def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), "scripts/install_opencode_skills.py must exist"
    assert os.access(SCRIPT, os.X_OK), (
        "scripts/install_opencode_skills.py must be executable (chmod +x)"
    )


def test_dry_run_lists_exactly_five_canonical_skills():
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "dry-run-target")
    result = _run(["--dry-run", "--target", str(target)])
    assert result.returncode == 0, (
        f"dry-run failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    for slug in CANONICAL_SKILLS:
        assert slug in result.stdout, (
            f"dry-run output must list canonical skill '{slug}'\n"
            f"stdout: {result.stdout}"
        )
    # The forbidden skills must not be listed.
    for bad in FORBIDDEN_SKILLS:
        assert bad not in result.stdout, (
            f"dry-run output must not list forbidden skill '{bad}'\n"
            f"stdout: {result.stdout}"
        )
    # The dry-run target directory must remain empty (no actual
    # writes happened).
    assert not any(target.iterdir()), (
        f"dry-run must not write to target; target contents: "
        f"{list(target.iterdir())}"
    )
    shutil.rmtree(parent, ignore_errors=True)


def test_apply_copies_exactly_five_canonical_skills():
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "apply-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, (
        f"apply failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    # Exactly five skill directories were created.
    created = sorted(p.name for p in target.iterdir() if p.is_dir())
    assert created == sorted(CANONICAL_SKILLS), (
        f"apply must create exactly the five canonical skill dirs, "
        f"got {created}"
    )
    # No archived / underscore / other paths were created.
    for bad in FORBIDDEN_SKILLS:
        assert not (target / bad).exists(), (
            f"apply must not create forbidden path {target / bad}"
        )
    shutil.rmtree(parent, ignore_errors=True)


def test_copied_skill_md_frontmatter_name_matches_directory():
    """Each copied SKILL.md must have a YAML frontmatter `name` field
    that matches its directory slug. This is the Superpowers /
    OpenCode Agent Skills contract."""
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "frontmatter-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    for slug in CANONICAL_SKILLS:
        skill_md = target / slug / "SKILL.md"
        assert skill_md.is_file(), (
            f"copied SKILL.md missing for {slug} at {skill_md}"
        )
        text = skill_md.read_text(encoding="utf-8")
        # Minimal YAML frontmatter: ``---\nname: <slug>\n---\n``
        assert text.startswith("---\n"), (
            f"{slug}/SKILL.md must start with YAML frontmatter; got: "
            f"{text[:60]!r}"
        )
        end = text.find("\n---\n", 4)
        assert end > 0, (
            f"{slug}/SKILL.md must have closing frontmatter; got: "
            f"{text[:200]!r}"
        )
        front = text[4:end]
        assert f"name: {slug}" in front, (
            f"{slug}/SKILL.md frontmatter must declare 'name: {slug}'; "
            f"frontmatter was: {front!r}"
        )
    shutil.rmtree(parent, ignore_errors=True)


def test_copied_skill_preserves_references_when_present():
    """Each copied skill must include its references/ directory if
    the source has one."""
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "refs-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    for slug in CANONICAL_SKILLS:
        src_refs = SKILLS_DIR / slug / "references"
        if not src_refs.is_dir():
            continue
        dst_refs = target / slug / "references"
        assert dst_refs.is_dir(), (
            f"copied skill {slug} must include references/ at {dst_refs}"
        )
        # Every file under source references/ must be present.
        for path in src_refs.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(src_refs)
            assert (dst_refs / rel).is_file(), (
                f"copied reference {slug}/references/{rel} missing"
            )
            # The content must match.
            assert (dst_refs / rel).read_bytes() == path.read_bytes(), (
                f"copied reference {slug}/references/{rel} content differs"
            )
    shutil.rmtree(parent, ignore_errors=True)


def test_apply_does_not_copy_fund_analyst_archive():
    """The archived legacy ``docs/archive/fund-analyst/`` must never
    be copied to the target."""
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "archive-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    assert not (target / "fund-analyst").exists(), (
        f"apply must not copy archived fund-analyst: "
        f"{target / 'fund-analyst'}"
    )
    # The marker must not list 'fund-analyst' as a generated skill.
    marker = target / ".fund-agent-generated.json"
    assert marker.is_file(), "apply must write a marker file"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert "fund-analyst" not in payload.get("skills", []), (
        f"marker must not list 'fund-analyst': {payload}"
    )
    shutil.rmtree(parent, ignore_errors=True)


def test_apply_does_not_copy_underscore_runtime_dirs():
    """Underscore runtime directories must not be copied, even if
    they were to appear in skills/."""
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    # Stage a fake underscore skill dir and re-run against it.
    fake_skills = parent / "fake_skills"
    if fake_skills.exists():
        shutil.rmtree(fake_skills)
    fake_skills.mkdir()
    for slug in CANONICAL_SKILLS:
        os.symlink(SKILLS_DIR / slug, fake_skills / slug)
    # Add an underscore dir that we should not copy.
    underscore_dir = fake_skills / "fund_analysis"
    underscore_dir.mkdir()
    (underscore_dir / "SKILL.md").write_text("name: fund_analysis\n", encoding="utf-8")
    target = _make_target(parent, "underscore-target")
    result = _run([
        "--target", str(target),
        "--skills-dir", str(fake_skills),
    ])
    assert result.returncode == 0, result.stderr
    # Only the five canonical dirs may be present.
    created = sorted(p.name for p in target.iterdir() if p.is_dir())
    assert created == sorted(CANONICAL_SKILLS), (
        f"apply must not copy underscore skill dirs, got {created}"
    )
    assert not (target / "fund_analysis").exists(), (
        "apply must not copy underscore skill dir 'fund_analysis'"
    )
    shutil.rmtree(parent, ignore_errors=True)


def test_apply_writes_marker_with_version_and_skill_list():
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "marker-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    marker = target / ".fund-agent-generated.json"
    assert marker.is_file(), "apply must write .fund-agent-generated.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload.get("plugin") == "fund-agent"
    assert payload.get("skills") == list(CANONICAL_SKILLS)
    assert "version" in payload and isinstance(payload["version"], str)
    shutil.rmtree(parent, ignore_errors=True)


def test_clean_refuses_to_run_without_marker():
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "no-marker-target")
    (target / "fund-analysis").mkdir()
    (target / "fund-analysis" / "SKILL.md").write_text(
        "name: fund-analysis\n", encoding="utf-8"
    )
    result = _run(["--target", str(target), "--clean"])
    assert result.returncode != 0, (
        "clean must refuse to run on a target without a marker; "
        f"stdout: {result.stdout!r} stderr: {result.stderr!r}"
    )
    # The user-authored directory must NOT have been removed.
    assert (target / "fund-analysis").is_dir(), (
        "clean must not delete files when refusing to run"
    )
    shutil.rmtree(parent, ignore_errors=True)


def test_clean_removes_only_generated_skills():
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "clean-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    # Add a user-authored skill dir that is NOT in the marker list.
    user_skill = target / "user-skill"
    user_skill.mkdir()
    (user_skill / "SKILL.md").write_text(
        "name: user-skill\n", encoding="utf-8"
    )
    # Run --clean.
    result = _run(["--target", str(target), "--clean"])
    assert result.returncode == 0, result.stderr
    # All five canonical skills must be gone.
    for slug in CANONICAL_SKILLS:
        assert not (target / slug).exists(), (
            f"clean must remove canonical skill dir {slug}"
        )
    # The marker must be gone.
    assert not (target / ".fund-agent-generated.json").exists(), (
        "clean must remove the .fund-agent-generated.json marker"
    )
    # The user-authored skill must still be there.
    assert (target / "user-skill").is_dir(), (
        "clean must not remove user-authored skill dirs"
    )
    assert (target / "user-skill" / "SKILL.md").is_file(), (
        "clean must not remove user-authored skill files"
    )
    shutil.rmtree(parent, ignore_errors=True)


def test_clean_dry_run_does_not_remove_anything():
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "clean-dry-run-target")
    result = _run(["--target", str(target)])
    assert result.returncode == 0, result.stderr
    result = _run(["--target", str(target), "--clean", "--dry-run"])
    assert result.returncode == 0, result.stderr
    # All five canonical skills must still be present.
    for slug in CANONICAL_SKILLS:
        assert (target / slug).is_dir(), (
            f"clean --dry-run must not remove canonical skill dir {slug}"
        )
    assert (target / ".fund-agent-generated.json").is_file(), (
        "clean --dry-run must not remove the marker"
    )
    shutil.rmtree(parent, ignore_errors=True)


def test_idempotent_reapply_preserves_content():
    """Running apply twice must produce the same result; the second
    run is a no-op for the skill files but rewrites the marker."""
    parent = ROOT / ".tmp" / "test_opencode_skills"
    parent.mkdir(parents=True, exist_ok=True)
    target = _make_target(parent, "idempotent-target")
    result1 = _run(["--target", str(target)])
    assert result1.returncode == 0, result1.stderr
    result2 = _run(["--target", str(target)])
    assert result2.returncode == 0, result2.stderr
    # All five canonical skills must still be present with the
    # expected files.
    for slug in CANONICAL_SKILLS:
        assert (target / slug / "SKILL.md").is_file()
    shutil.rmtree(parent, ignore_errors=True)
