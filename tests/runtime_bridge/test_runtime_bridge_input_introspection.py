"""Runtime bridge input introspection command tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.skillpack import input_contracts
from tests.support.bridge_runner import run_bridge_inprocess_metadata, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]
INPUT_CONTRACT_PATH = ROOT / "skillpack" / "input-contracts.yaml"


def _fund_input_contract() -> dict:
    data = yaml.safe_load(INPUT_CONTRACT_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["fund_analysis"]


def _recommended_keys(contract: dict) -> list[str]:
    return [item["key"] for item in contract["recommended_fields"]]


def _optional_keys(contract: dict) -> list[str]:
    return [item["key"] for item in contract["optional_fields"]]


def test_explain_input_fund_analysis_returns_contract_without_input() -> None:
    out = run_bridge_inprocess_metadata(skill="fund_analysis", explain_input=True, pretty=True)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert out["doc_slug"] == "fund-analysis"
    assert out["command"] == "explain-input"

    contract = out["input_contract"]
    shape_names = {item["name"] for item in contract["accepted_envelope_shapes"]}
    assert {"full_skill_input", "payload_only"} <= shape_names

    modes = {item["mode"] for item in contract["minimum_required"]}
    assert "portfolio_snapshot" in modes
    assert "ledger_derived" in modes
    assert "related_entities_baseline" in modes

    rendered = json.dumps(contract).lower()
    assert "host owns all nav" in rendered
    assert "current_nav" in rendered


def test_explain_input_fund_analysis_uses_yaml_contract() -> None:
    out = run_bridge_inprocess_metadata(skill="fund_analysis", explain_input=True, pretty=True)
    contract = out["input_contract"]
    yaml_contract = _fund_input_contract()

    assert contract["contract_version"] == yaml_contract["contract_version"]
    assert contract["doc"] == yaml_contract["doc"]
    assert contract["accepted_envelope_shapes"] == yaml_contract["accepted_envelope_shapes"]
    assert contract["minimum_required"] == yaml_contract["minimum_required"]
    assert contract["recommended"] == _recommended_keys(yaml_contract)
    assert contract["optional"] == _optional_keys(yaml_contract)

    yaml_mapping = yaml_contract["host_data_capability_fields"]
    by_name = {item["name"]: item for item in contract["host_owned_data_capabilities"]}
    assert by_name["portfolio_snapshot"]["payload_fields"] == yaml_mapping[
        "portfolio_snapshot"
    ]["payload_fields"]
    assert by_name["fund_benchmark"]["payload_fields"] == yaml_mapping[
        "fund_benchmark"
    ]["payload_fields"]


def test_explain_input_fund_analysis_is_contract_loader_driven(monkeypatch) -> None:
    fake_contract = {
        "contract_version": "fake-input.v1",
        "doc": "docs/contracts/fake-input.md",
        "accepted_envelope_shapes": [
            {"name": "fake_shape", "description": "fake", "shape": {"payload": "object"}}
        ],
        "minimum_required": [
            {"mode": "fake_mode", "required": ["payload.fake"], "description": "fake"}
        ],
        "recommended_fields": [
            {"key": "fake_recommended", "description": "fake", "missing_behavior": "warning"}
        ],
        "optional_fields": [
            {"key": "fake_optional", "description": "fake", "missing_behavior": "missing"}
        ],
        "host_data_capability_fields": {
            "portfolio_snapshot": {"payload_fields": ["fake_portfolio"]}
        },
        "validation": {"severity_values": ["OK"]},
        "degradation_policy": ["fake degradation"],
        "required_mcp_capabilities": [],
    }

    monkeypatch.setattr(
        input_contracts,
        "get_skill_input_contract",
        lambda _skill_id, _path: fake_contract,
    )

    result = input_contracts.explain_skill_input("fund-analysis")
    contract = result["input_contract"]
    assert result["skill_name"] == "fund_analysis"
    assert contract["contract_version"] == "fake-input.v1"
    assert contract["accepted_envelope_shapes"][0]["name"] == "fake_shape"
    assert contract["minimum_required"][0]["mode"] == "fake_mode"
    assert contract["recommended"] == ["fake_recommended"]
    assert contract["optional"] == ["fake_optional"]
    by_name = {item["name"]: item for item in contract["host_owned_data_capabilities"]}
    assert by_name["portfolio_snapshot"]["payload_fields"] == ["fake_portfolio"]


@pytest.mark.subprocess
def test_explain_input_accepts_hyphenated_slug() -> None:
    proc = run_bridge_subprocess(["--skill", "fund-analysis", "--explain-input", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert out["doc_slug"] == "fund-analysis"


def test_explain_input_for_mcp_skill_lists_manifest_capabilities() -> None:
    out = run_bridge_inprocess_metadata(skill="news_research", explain_input=True, pretty=True)
    contract = out["input_contract"]
    assert contract["required_mcp_capabilities"] == [
        "web_search",
        "financial_news",
    ]
    rendered = json.dumps(contract).lower()
    assert "mcp_responses" in rendered
    assert "real provider calls belong to the external host" in rendered


@pytest.mark.subprocess
def test_existing_list_skills_command_still_works() -> None:
    proc = run_bridge_subprocess(["--list-skills", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert {skill["runtime_id"] for skill in out["skills"]} >= {
        "fund_analysis",
        "decision_support",
        "news_research",
        "sentiment_analysis",
        "thesis_generation",
    }
