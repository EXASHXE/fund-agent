"""Runtime bridge output schema command tests for decision_support."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
DECISION_CONTRACTS_PATH = ROOT / "skillpack" / "decision-contracts.yaml"


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


def _artifact_keys(schema: dict) -> set[str]:
    return {
        item["key"]
        for item in schema["artifacts"]["known_keys"]
        if isinstance(item, dict)
    }


def _decision_contract() -> dict:
    data = yaml.safe_load(DECISION_CONTRACTS_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["decision_support"]


def test_decision_support_output_schema_returns_ok():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    assert out["ok"] is True


def test_known_keys_match_decision_contracts_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    contract_keys = {a["key"] for a in contract["artifact_keys"]}
    schema_keys = _artifact_keys(schema)
    assert schema_keys == contract_keys


def test_known_artifact_entries_match_decision_contracts_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    assert schema["artifacts"]["known_keys"] == contract["artifact_keys"]


def test_formal_outputs_include_decision_and_execution_ledger():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    formal = set(schema["artifacts"]["formal_outputs"])
    assert {"Decision", "ExecutionLedger"} <= formal


def test_active_actions_match_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    assert set(schema["active_actions"]) == set(contract["active_actions"])


def test_decision_fields_match_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    assert schema["decision_fields"] == contract["decision_fields"]


def test_reason_codes_match_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    assert schema["reason_codes"] == contract["reason_codes"]


def test_evidence_states_match_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    assert schema["evidence_states"] == contract["evidence_states"]


def test_passive_actions_match_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    assert set(schema["passive_actions"]) == set(contract["passive_actions"])


def test_status_values_match_yaml():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    contract = _decision_contract()
    assert set(schema["status_values"]) == set(contract["status_values"])


def test_evidence_items_says_consumes_evidence_graph():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    evidence = schema.get("evidence_items") or {}
    produces = evidence.get("produces") or []
    assert produces == []
    notes_text = json.dumps(evidence.get("notes") or []).lower()
    assert "evidencegraph" in notes_text or "evidence graph" in notes_text


def test_output_schema_mentions_only_decision_support_may_produce_formal():
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    rendered = json.dumps(_json(proc)["output_schema"]).lower()
    assert "only decision_support may produce" in rendered


def test_hyphen_slug_also_works():
    proc = _run(["--skill", "decision-support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    assert out["skill_name"] == "decision_support"
