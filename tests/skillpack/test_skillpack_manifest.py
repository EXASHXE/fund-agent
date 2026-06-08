"""Skill pack manifest contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


MANIFEST_PATH = Path("skillpack/fund-agent.skillpack.yaml")


def test_skillpack_manifest_exists_and_has_required_top_level_fields():
    data = _manifest()

    for key in (
        "name",
        "version",
        "schema_version",
        "package_role",
        "type",
        "description",
        "orchestration_owner",
        "mcp_provider_owner",
        "skills",
        "tools",
        "schemas",
        "contracts",
        "mcp_capabilities",
        "host_integration",
        "forbidden_behaviors",
    ):
        assert key in data
    assert data["type"] == "host-agnostic-financial-research-skill-pack"


def test_skillpack_manifest_declares_required_skills():
    skills = {skill["name"]: skill for skill in _manifest()["skills"]}

    assert set(skills) >= {
        "fund_analysis",
        "news_research",
        "sentiment_analysis",
        "thesis_generation",
        "decision_support",
    }
    assert skills["fund_analysis"]["produces"] == ["HardEvidence"]
    assert skills["news_research"]["requires_mcp"] == ["web_search", "financial_news"]
    assert skills["sentiment_analysis"]["requires_mcp"] == ["social_sentiment"]
    assert "formal_decision_generation" in skills["thesis_generation"]["forbidden"]
    assert skills["decision_support"]["produces"] == ["Decision", "ExecutionLedger"]


def test_skillpack_manifest_does_not_require_research_os_entrypoint():
    data = _manifest()
    serialized = yaml.safe_dump(data)

    assert data["host_integration"]["required_entrypoint"] == MANIFEST_PATH.as_posix()
    assert "src.core.research_os" not in serialized
    assert "src/workflows/research_os.py" not in serialized


def test_skillpack_manifest_has_schema_version():
    data = _manifest()

    assert data["schema_version"] == "skillpack.v1"
    assert data["package_role"] == "agent_plugin"


def test_skillpack_manifest_declares_external_orchestration_owner():
    data = _manifest()

    assert data["orchestration_owner"] == "external_agent"
    assert data["host_integration"]["orchestration_owner"] == "external_agent"
    assert data["host_integration"]["planner_owner"] == "external_agent"


def test_skillpack_manifest_declares_external_mcp_provider_owner():
    data = _manifest()

    assert data["mcp_provider_owner"] == "external_host"
    assert data["host_integration"]["mcp_provider_owner"] == "external_host"


def test_skillpack_sidecar_files_exist():
    for path in (
        MANIFEST_PATH,
        Path("skillpack/capabilities.yaml"),
        Path("skillpack/tools.yaml"),
        Path("skillpack/contracts.yaml"),
        Path("skillpack/input-contracts.yaml"),
        Path("skillpack/artifact-contracts.yaml"),
    ):
        assert path.exists()


def test_manifest_references_decision_support_contract_doc():
    contracts = set(_manifest()["contracts"])

    assert "docs/contracts/decision-contract.v2.md" in contracts
    assert "docs/contracts/decision-support-contract.v1.md" in contracts


def test_skillpack_manifest_is_json_serializable():
    data = _manifest()
    json.dumps(data)


def test_manifest_version_matches_version_file():
    version = (MANIFEST_PATH.parent.parent / "VERSION").read_text(encoding="utf-8").strip()
    assert _manifest()["version"] == version


def test_all_skill_runtime_paths_do_not_point_to_legacy_or_research_os():
    data = _manifest()
    for skill in data["skills"]:
        runtime = skill["runtime"]
        assert "legacy" not in runtime, f"{skill['name']} runtime points to legacy: {runtime}"
        assert "research_os" not in runtime, f"{skill['name']} runtime points to ResearchOS: {runtime}"


def test_every_skill_has_required_fields():
    data = _manifest()
    for skill in data["skills"]:
        for key in ("name", "runtime", "input_schema", "output_schema", "requires_mcp"):
            assert key in skill, f"{skill.get('name', '?')} missing {key}"


def test_mcp_capabilities_declared_in_capabilities_yaml():
    import yaml as y

    data = _manifest()
    caps_yaml = y.safe_load(Path("skillpack/capabilities.yaml").read_text(encoding="utf-8"))
    declared = set(caps_yaml.get("mcp_capabilities", caps_yaml.get("capabilities", [])))
    if isinstance(next(iter(declared), None), dict):
        declared = {c["name"] for c in declared}

    for skill in data["skills"]:
        for cap in skill.get("requires_mcp", []):
            assert cap in declared, f"{skill['name']} requires undeclared MCP capability: {cap}"


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
