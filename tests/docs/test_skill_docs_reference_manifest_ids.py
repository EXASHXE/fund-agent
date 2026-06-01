"""Skill docs should reference manifest IDs explicitly."""
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"


def _manifest_skill_ids() -> list[str]:
    manifest = yaml.safe_load((ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text())
    return [skill["name"] for skill in manifest["skills"]]


def _slug(skill_id: str) -> str:
    return skill_id.replace("_", "-")


def test_each_skill_doc_references_runtime_manifest_id():
    for skill_id in _manifest_skill_ids():
        text = (SKILLS_DIR / _slug(skill_id) / "SKILL.md").read_text()
        assert f"`{skill_id}`" in text


def test_skills_readme_maps_manifest_ids_to_slugs():
    text = (SKILLS_DIR / "README.md").read_text()
    assert "skillpack/fund-agent.skillpack.yaml" in text
    for skill_id in _manifest_skill_ids():
        assert f"`{skill_id}`" in text
        assert f"`{_slug(skill_id)}`" in text


def test_project_docs_state_manifest_discovery_not_folder_discovery():
    docs = [
        ROOT / "README.md",
        ROOT / "docs" / "host-integration.md",
        ROOT / "docs" / "plugin-api.md",
        ROOT / "docs" / "host-compatibility.md",
    ]
    for path in docs:
        text = path.read_text()
        normalized = " ".join(text.split())
        assert "skillpack/fund-agent.skillpack.yaml" in text
        assert "Do not infer runtime skill IDs from folder names" in normalized
