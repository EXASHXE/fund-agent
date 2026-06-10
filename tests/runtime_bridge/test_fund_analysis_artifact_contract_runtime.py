"""Runtime checks for the fund_analysis artifact contract."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from tests.support.bridge_runner import run_bridge_inprocess_json


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "examples" / "runtime_bridge_personal_report_quality_input.json"
CONTRACT_PATH = ROOT / "skillpack" / "artifact-contracts.yaml"


def _run_personal_report_quality_example() -> dict:
    input_text = INPUT.read_text(encoding="utf-8")
    output = run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text)
    assert output.get("ok") is True
    return output


def _fund_contract() -> dict:
    data = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["fund_analysis"]


def test_runtime_artifacts_respect_fund_analysis_artifact_contract() -> None:
    output = _run_personal_report_quality_example()
    artifacts = output["artifacts"]
    assert isinstance(artifacts, dict)

    contract = _fund_contract()
    forbidden = set(contract["forbidden_artifacts"])
    assert not (set(artifacts) & forbidden)

    for key in ("report_sections", "report_outline", "report_quality_gate"):
        assert key in artifacts

    top_level_contract_keys = {
        artifact["key"]
        for artifact in contract["artifacts"]
        if artifact.get("top_level", True)
    }
    undocumented = set(artifacts) - top_level_contract_keys
    assert not undocumented, f"runtime emitted undocumented artifact keys: {sorted(undocumented)}"
