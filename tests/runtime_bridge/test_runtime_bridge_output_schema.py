"""Runtime bridge output schema summary command tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.skillpack import input_contracts
from tests.support.bridge_runner import run_bridge_inprocess_metadata


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_CONTRACT_PATH = ROOT / "skillpack" / "artifact-contracts.yaml"


def _artifact_keys(schema: dict) -> set[str]:
    return {
        item["key"]
        for item in schema["artifacts"]["known_keys"]
        if isinstance(item, dict)
    }


def _fund_artifact_contract() -> dict:
    data = yaml.safe_load(ARTIFACT_CONTRACT_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["fund_analysis"]


def _output_schema(skill: str) -> dict:
    return run_bridge_inprocess_metadata(skill=skill, output_schema=True, pretty=True)


def test_fund_analysis_output_schema_lists_public_shape() -> None:
    out = _output_schema("fund_analysis")
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    schema = out["output_schema"]
    for key in (
        "bridge_envelope",
        "skill_output_fields",
        "artifacts",
        "evidence_items",
            "status_values",
    ):
        assert key in schema

    contract = _fund_artifact_contract()
    contract_entries = {item["key"]: item for item in contract["artifacts"]}
    schema_entries = {
        item["key"]: item
        for item in schema["artifacts"]["known_keys"]
        if isinstance(item, dict)
    }
    assert set(schema_entries) == set(contract_entries)
    for key, contract_entry in contract_entries.items():
        schema_entry = schema_entries[key]
        assert schema_entry["category"] == contract_entry["category"]
        assert schema_entry["required"] == contract_entry["required"]
        assert schema_entry["type"] == contract_entry["type"]
        assert schema_entry["produced_when"] == contract_entry["produced_when"]
        assert schema_entry["description"] == contract_entry["description"]

    assert schema["artifacts"]["forbidden_artifacts"] == contract["forbidden_artifacts"]
    assert {"decision", "execution_ledger"} <= set(
        schema["artifacts"]["forbidden_artifacts"]
    )
    assert schema["status_values"] == contract["status_values"]


def test_fund_analysis_output_schema_is_contract_loader_driven(monkeypatch) -> None:
    fake_contract = {
        "contract_version": "fake.v1",
        "doc": "docs/contracts/fake.md",
        "forbidden_artifacts": ["decision"],
        "status_values": ["OK", "FAILED"],
        "artifact_categories": {
            "diagnostics": {"description": "fake diagnostics"},
        },
        "artifacts": [
            {
                "key": "fake_contract_key",
                "category": "diagnostics",
                "required": True,
                "type": "object",
                "produced_when": "test patch",
                "description": "Synthetic artifact from patched loader.",
            }
        ],
    }

    monkeypatch.setattr(
        input_contracts,
        "get_skill_artifact_contract",
        lambda _skill_id, _path: fake_contract,
    )

    result = input_contracts.output_schema_for_skill("fund-analysis")
    schema = result["output_schema"]
    assert result["skill_name"] == "fund_analysis"
    assert schema["status_values"] == ["OK", "FAILED"]
    assert schema["artifacts"]["forbidden_artifacts"] == ["decision"]
    assert schema["artifacts"]["known_keys"] == [
        {
            "key": "fake_contract_key",
            "required": True,
            "category": "diagnostics",
            "type": "object",
            "produced_when": "test patch",
            "description": "Synthetic artifact from patched loader.",
        }
    ]


def test_decision_support_output_schema_mentions_formal_outputs() -> None:
    schema = _output_schema("decision_support")["output_schema"]
    artifact_keys = _artifact_keys(schema)
    assert "decision" in artifact_keys
    assert "execution_ledger" in artifact_keys
    rendered = json.dumps(schema).lower()
    assert "decision" in rendered
    assert "executionledger" in rendered
    assert "only decision_support may produce formal decision" in rendered


def test_thesis_generation_output_schema_forbids_formal_decisions() -> None:
    schema = _output_schema("thesis_generation")["output_schema"]
    artifact_keys = _artifact_keys(schema)
    assert artifact_keys == {"thesis_draft"}
    assert schema["artifacts"]["forbidden"] == ["formal_decision_generation"]
    rendered = json.dumps(schema).lower()
    assert "thesisdraft" in rendered
    assert "formal decision generation is forbidden" in rendered


def test_news_research_output_schema_mentions_soft_evidence() -> None:
    schema = _output_schema("news_research")["output_schema"]
    assert schema["evidence_items"]["produces"] == ["SoftEvidence"]
    assert "mcp_response" in _artifact_keys(schema)
