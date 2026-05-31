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

    assert data["host_integration"]["required_entrypoint"] == str(MANIFEST_PATH)
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
    ):
        assert path.exists()


def test_skillpack_manifest_is_json_serializable():
    data = _manifest()
    json.dumps(data)


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())
