"""Skill Markdown directory policy tests."""
from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"


def _manifest_skill_ids() -> list[str]:
    manifest = yaml.safe_load((ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8"))
    return [skill["name"] for skill in manifest["skills"]]


def _slug(skill_id: str) -> str:
    return skill_id.replace("_", "-")


def test_hyphenated_docs_exist_for_every_manifest_skill():
    for skill_id in _manifest_skill_ids():
        skill_doc = SKILLS_DIR / _slug(skill_id) / "SKILL.md"
        assert skill_doc.exists(), f"missing canonical SKILL.md for {skill_id}"


def test_every_runtime_skill_id_is_documented_in_skills_readme():
    readme = (SKILLS_DIR / "README.md").read_text(encoding="utf-8")
    for skill_id in _manifest_skill_ids():
        assert f"`{skill_id}`" in readme
        assert f"`{_slug(skill_id)}`" in readme


def test_underscore_docs_are_absent_or_marked_compatibility_only():
    for skill_id in _manifest_skill_ids():
        underscore_dir = SKILLS_DIR / skill_id
        if not underscore_dir.exists():
            continue
        assert not (underscore_dir / "SKILL.md").exists()
        readme = underscore_dir / "README.md"
        assert readme.exists(), f"{underscore_dir} needs a compatibility README"
        text = " ".join(readme.read_text(encoding="utf-8").lower().split())
        assert "compatibility-only" in text
        assert "not a canonical markdown skill doc" in text
        assert "not be presented as a second runtime skill" in text


def test_fund_analyst_is_legacy_reference_only():
    """fund-analyst is archived under docs/archive/fund-analyst/ in
    v0.4.4+. The archived SKILL.md must continue to mark itself as
    legacy / not a runtime entrypoint."""
    archive_path = ROOT / "docs" / "archive" / "fund-analyst" / "SKILL.md"
    assert archive_path.exists(), (
        "docs/archive/fund-analyst/SKILL.md must exist for legacy reference"
    )
    text = archive_path.read_text(encoding="utf-8").lower()
    assert "legacy" in text
    assert "not a runtime" in text or "not installed" in text or "archived" in text


def test_fund_analyst_is_not_under_skills_dir():
    """skills/fund-analyst/ must not exist in v0.4.4+; the persona
    material is archived under docs/archive/fund-analyst/."""
    assert not (SKILLS_DIR / "fund-analyst").exists(), (
        "skills/fund-analyst/ has been archived to docs/archive/fund-analyst/"
    )


def test_no_underscore_skill_dir_in_skills_root():
    """The v0.4.4+ skill surface has no underscore `skills/<x>/`
    directories. They are not exposed by the OpenCode plugin and are
    not canonical Markdown skill directories."""
    allowed = {"__pycache__"}  # pytest / build artefacts
    for entry in SKILLS_DIR.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in allowed:
            continue
        assert "_" not in entry.name, (
            f"underscore skill directory {entry} is no longer part of "
            f"the v0.4.4+ skill surface; the canonical Markdown skill "
            f"directories are hyphenated only"
        )


def test_skills_readme_documents_superpowers_compatible_surface():
    """skills/README.md must explain the Superpowers-compatible skill
    surface: primary skill, supporting skills, and that underscore
    directories are not part of the surface."""
    top_level = (SKILLS_DIR / "README.md").read_text(encoding="utf-8")
    assert "primary" in top_level.lower()
    assert "supporting" in top_level.lower()
    # The skill README must NOT present underscore directories as
    # compatibility shims any more (the v0.4.4+ surface is hyphenated
    # only).
    assert "compatibility shims only" not in top_level.lower()


def test_external_host_docs_do_not_call_skills_by_folder_name():
    docs = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "docs" / "agent-host-quickstart.md",
        ROOT / "docs" / "host-integration.md",
        ROOT / "docs" / "plugin-api.md",
        ROOT / "docs" / "skill-io-examples.md",
        ROOT / "docs" / "host-compatibility.md",
    ]
    folder_skill_name = re.compile(r"skill_name[\"']?\s*[:=]\s*[\"'][a-z]+-[a-z-]+[\"']")
    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert not folder_skill_name.search(text), f"{path} calls a skill by folder slug"
