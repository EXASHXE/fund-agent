"""Runtime bridge output-schema drift tests for thesis_generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tests.support.bridge_runner import run_bridge_inprocess_metadata, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]
THESIS_CONTRACTS_PATH = ROOT / "skillpack" / "thesis-contracts.yaml"


def _contract() -> dict:
    data = yaml.safe_load(THESIS_CONTRACTS_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["thesis_generation"]


def test_thesis_generation_output_schema_matches_contract_yaml() -> None:
    envelope = run_bridge_inprocess_metadata(skill="thesis_generation", output_schema=True, pretty=True)
    assert envelope["ok"] is True

    schema = envelope["output_schema"]
    contract = _contract()
    artifacts = schema["artifacts"]

    assert schema["thesis_draft_fields"] == contract["thesis_draft_fields"]
    assert artifacts["formal_outputs_forbidden"] == contract["formal_outputs_forbidden"]
    assert schema["status_values"] == contract["status_values"]

    thesis_keys = [
        item for item in artifacts["known_keys"]
        if item.get("key") == "thesis_draft"
    ]
    assert thesis_keys == [
        {
            "key": "thesis_draft",
            "required": True,
            "fields": contract["thesis_draft_fields"],
        }
    ]

    forbidden_artifacts = set(artifacts.get("forbidden_artifacts") or [])
    assert {"decision", "decisions", "execution_ledger", "execution_ledgers"} <= forbidden_artifacts
    assert {"Decision", "ExecutionLedger"} <= set(artifacts["formal_outputs_forbidden"])


@pytest.mark.subprocess
def test_thesis_generation_hyphenated_slug_output_schema_works() -> None:
    proc = run_bridge_subprocess(["--skill", "thesis-generation", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    envelope = json.loads(proc.stdout)
    assert envelope["ok"] is True
    assert envelope["skill_name"] == "thesis_generation"
