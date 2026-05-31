"""Skillpack v1 JSON schema tests — lightweight manual validation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

SCHEMA_PATH = Path("skillpack/schema/skillpack.v1.schema.json")
MANIFEST_PATH = Path("skillpack/fund-agent.skillpack.yaml")


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_skillpack_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_skillpack_manifest_validates_against_schema():
    """Lightweight manual validation against schema requirements."""
    schema = _schema()
    manifest = _manifest()

    required = schema.get("required", [])
    for key in required:
        assert key in manifest, f"manifest missing required key: {key}"

    for key, prop in schema.get("properties", {}).items():
        if "const" in prop and key in manifest:
            assert manifest[key] == prop["const"], (
                f"manifest.{key} = {manifest[key]}, schema requires {prop['const']}"
            )

    for skill in manifest.get("skills", []):
        skill_schema = schema["properties"]["skills"]["items"]
        for key in skill_schema.get("required", []):
            assert key in skill, f"skill {skill.get('name','?')} missing {key}"


def test_schema_requires_external_orchestration_owner():
    schema = _schema()
    assert schema["properties"]["orchestration_owner"]["const"] == "external_agent"


def test_schema_rejects_missing_skills():
    schema = _schema()
    assert schema["properties"]["skills"]["minItems"] >= 1


def test_schema_rejects_research_os_required_entrypoint():
    schema = _schema()
    assert "research_os" not in json.dumps(schema).lower()
    manifest = _manifest()
    entry = manifest.get("host_integration", {}).get("required_entrypoint", "")
    assert "research_os" not in entry
