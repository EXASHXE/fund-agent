"""Runtime checks for the fund_analysis artifact contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
INPUT = ROOT / "examples" / "runtime_bridge_personal_report_quality_input.json"
CONTRACT_PATH = ROOT / "skillpack" / "artifact-contracts.yaml"


def _run_personal_report_quality_example() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--skill",
            "fund_analysis",
            "--input",
            str(INPUT),
            "--pretty",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _fund_contract() -> dict:
    data = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["fund_analysis"]


def test_runtime_artifacts_respect_fund_analysis_artifact_contract() -> None:
    output = _run_personal_report_quality_example()
    assert output["ok"] is True
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
