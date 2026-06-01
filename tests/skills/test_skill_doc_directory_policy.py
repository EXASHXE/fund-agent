"""Skill Markdown directory policy tests."""
from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"


def _manifest_skill_ids() -> list[str]:
    manifest = yaml.safe_load((ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text())
    return [skill["name"] for skill in manifest["skills"]]


def _slug(skill_id: str) -> str:
    return skill_id.replace("_", "-")


def test_hyphenated_docs_exist_for_every_manifest_skill():
    for skill_id in _manifest_skill_ids():
        skill_doc = SKILLS_DIR / _slug(skill_id) / "SKILL.md"
        assert skill_doc.exists(), f"missing canonical SKILL.md for {skill_id}"


def test_every_runtime_skill_id_is_documented_in_skills_readme():
    readme = (SKILLS_DIR / "README.md").read_text()
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
        text = " ".join(readme.read_text().lower().split())
        assert "compatibility-only" in text
        assert "not a canonical markdown skill doc" in text
        assert "not be presented as a second runtime skill" in text


def test_fund_analyst_is_legacy_reference_only():
    text = (SKILLS_DIR / "fund-analyst" / "SKILL.md").read_text().lower()
    assert "legacy/reference-only" in text
    assert "not a runtime entrypoint" in text


def test_no_duplicate_directory_is_presented_as_second_runtime_skill():
    top_level = (SKILLS_DIR / "README.md").read_text().lower()
    assert "underscore directories" in top_level
    assert "compatibility shims only" in top_level
    assert "must not be presented as second runtime skills" in top_level


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
        text = path.read_text()
        assert not folder_skill_name.search(text), f"{path} calls a skill by folder slug"
