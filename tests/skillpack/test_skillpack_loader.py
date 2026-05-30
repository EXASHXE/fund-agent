"""Skill pack loader and resolver tests."""

from __future__ import annotations

from src.schemas.skill import SkillInput, SkillOutput
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.skillpack.manifest import SkillPackManifest
from src.skillpack.validator import validate_manifest
from src.skills_runtime.news_research import NewsResearchSkill


def test_loads_fund_agent_skillpack_manifest():
    manifest = load_skillpack_manifest()

    assert manifest.name == "fund-agent"
    assert manifest.type == "host-agnostic-financial-research-skill-pack"
    assert manifest.skill("news_research").runtime.endswith("NewsResearchSkill")


def test_skillpack_loader_resolves_runtime_class():
    manifest = load_skillpack_manifest()
    runtime = resolve_runtime(manifest.skill("news_research").runtime)

    assert runtime is NewsResearchSkill


def test_skillpack_loader_resolves_input_output_schema_paths():
    manifest = load_skillpack_manifest()
    spec = manifest.skill("fund_analysis")

    assert resolve_runtime(spec.input_schema) is SkillInput
    assert resolve_runtime(spec.output_schema) is SkillOutput


def test_skillpack_manifest_validates_mcp_capabilities():
    manifest = load_skillpack_manifest()
    declared = {
        item["name"]
        for item in manifest.mcp_capabilities
    }

    for skill in manifest.skills:
        assert set(skill.requires_mcp).issubset(declared)


def test_skillpack_validator_has_no_errors_for_default_manifest():
    manifest = load_skillpack_manifest(validate=False)

    assert validate_manifest(manifest) == []


def test_skillpack_loader_does_not_depend_on_research_os_or_legacy():
    manifest = load_skillpack_manifest()
    serialized = str(manifest.to_dict())

    assert "src.core.research_os" not in serialized
    assert "legacy" not in serialized


def test_skillpack_manifest_rejects_required_research_os_entrypoint():
    manifest = load_skillpack_manifest(validate=False)
    data = manifest.to_dict()
    data["host_integration"]["required_entrypoint"] = "src.core.research_os:run_research_task"
    invalid = SkillPackManifest.from_dict(data)

    try:
        validate_manifest(invalid)
    except ValueError as exc:
        assert "ResearchOS" in str(exc)
    else:
        raise AssertionError("Expected ResearchOS entrypoint validation failure")
