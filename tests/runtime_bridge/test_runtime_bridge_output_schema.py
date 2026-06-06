"""Runtime bridge output schema summary command tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"


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


def test_fund_analysis_output_schema_lists_public_shape() -> None:
    proc = _run(["--skill", "fund_analysis", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
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
    artifact_keys = _artifact_keys(schema)
    assert "report_sections" in artifact_keys
    assert "report_quality_gate" in artifact_keys
    assert schema["status_values"] == ["OK", "PARTIAL", "FAILED"]


def test_decision_support_output_schema_mentions_formal_outputs() -> None:
    proc = _run(["--skill", "decision_support", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    artifact_keys = _artifact_keys(schema)
    assert "decision" in artifact_keys
    assert "execution_ledger" in artifact_keys
    rendered = json.dumps(schema).lower()
    assert "decision" in rendered
    assert "executionledger" in rendered
    assert "only decision_support may produce formal decision" in rendered


def test_thesis_generation_output_schema_forbids_formal_decisions() -> None:
    proc = _run(["--skill", "thesis_generation", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    artifact_keys = _artifact_keys(schema)
    assert artifact_keys == {"thesis_draft"}
    assert schema["artifacts"]["forbidden"] == ["formal_decision_generation"]
    rendered = json.dumps(schema).lower()
    assert "thesisdraft" in rendered
    assert "formal decision generation is forbidden" in rendered


def test_news_research_output_schema_mentions_soft_evidence() -> None:
    proc = _run(["--skill", "news_research", "--output-schema", "--pretty"])
    assert proc.returncode == 0, proc.stderr
    schema = _json(proc)["output_schema"]
    assert schema["evidence_items"]["produces"] == ["SoftEvidence"]
    assert "mcp_response" in _artifact_keys(schema)
