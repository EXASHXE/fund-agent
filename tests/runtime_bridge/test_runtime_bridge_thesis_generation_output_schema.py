"""Runtime bridge output-schema drift tests for thesis_generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
THESIS_CONTRACTS_PATH = ROOT / "skillpack" / "thesis-contracts.yaml"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _json(proc: subprocess.CompletedProcess) -> dict:
    assert proc.stdout.strip(), f"stdout must contain JSON, stderr={proc.stderr!r}"
    return json.loads(proc.stdout)


def _contract() -> dict:
    data = yaml.safe_load(THESIS_CONTRACTS_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["thesis_generation"]


def test_thesis_generation_output_schema_matches_contract_yaml() -> None:
    proc = _run(["--skill", "thesis_generation", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    envelope = _json(proc)
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


def test_thesis_generation_hyphenated_slug_output_schema_works() -> None:
    proc = _run(["--skill", "thesis-generation", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    envelope = _json(proc)
    assert envelope["ok"] is True
    assert envelope["skill_name"] == "thesis_generation"
