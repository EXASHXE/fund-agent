"""Integration tests for thesis_generation fixtures."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = ROOT / "scripts" / "run_skill.py"

FORMAL_DECISION_ARTIFACTS = {"decision", "decisions", "execution_ledger", "execution_ledgers"}

THESIS_FIXTURES = [
    "examples/thesis_generation/thesis_with_mixed_evidence.json",
    "examples/thesis_generation/thesis_from_fund_analysis_artifacts.json",
    "examples/thesis_generation/thesis_missing_evidence_partial.json",
]

REQUIRED_THESIS_DRAFT_FIELDS = [
    "thesis_statement",
    "supporting_evidence",
    "counter_evidence",
    "missing_evidence",
    "confidence_assessment",
    "watch_conditions",
    "invalidating_conditions",
    "next_research_questions",
    "decision_boundary_note",
]


def _run_bridge(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(BRIDGE_SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_fixture_exists(fixture_path: str):
    assert (ROOT / fixture_path).exists(), f"Fixture not found: {fixture_path}"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_fixture_parses(fixture_path: str):
    data = json.loads((ROOT / fixture_path).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "skill_name" in data
    assert data["skill_name"] == "thesis_generation"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_fixture_runs_through_bridge(fixture_path: str):
    proc = _run_bridge(["--skill", "thesis_generation", "--input", fixture_path, "--pretty"])
    assert proc.returncode == 0, f"Bridge failed for {fixture_path}: {proc.stderr}"
    envelope = json.loads(proc.stdout)
    assert envelope.get("ok") is True
    assert envelope.get("skill_name") == "thesis_generation"
    assert envelope.get("status") in ("OK", "PARTIAL")


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_thesis_draft_artifact_exists(fixture_path: str):
    proc = _run_bridge(["--skill", "thesis_generation", "--input", fixture_path, "--pretty"])
    envelope = json.loads(proc.stdout)
    artifacts = envelope.get("artifacts", {})
    assert "thesis_draft" in artifacts, f"Missing thesis_draft in artifacts for {fixture_path}"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_thesis_draft_required_fields(fixture_path: str):
    proc = _run_bridge(["--skill", "thesis_generation", "--input", fixture_path, "--pretty"])
    envelope = json.loads(proc.stdout)
    draft = envelope.get("artifacts", {}).get("thesis_draft", {})
    for field in REQUIRED_THESIS_DRAFT_FIELDS:
        assert field in draft, f"Missing field '{field}' in thesis_draft for {fixture_path}"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_no_formal_decision_artifacts(fixture_path: str):
    proc = _run_bridge(["--skill", "thesis_generation", "--input", fixture_path, "--pretty"])
    envelope = json.loads(proc.stdout)
    artifacts = envelope.get("artifacts", {})
    for key in FORMAL_DECISION_ARTIFACTS:
        assert key not in artifacts, f"Forbidden artifact '{key}' found for {fixture_path}"


def test_confidence_assessment_structure():
    proc = _run_bridge([
        "--skill", "thesis_generation",
        "--input", "examples/thesis_generation/thesis_with_mixed_evidence.json",
        "--pretty",
    ])
    envelope = json.loads(proc.stdout)
    draft = envelope["artifacts"]["thesis_draft"]
    ca = draft["confidence_assessment"]
    assert "level" in ca
    assert ca["level"] in ("LOW", "MEDIUM", "HIGH")
    assert "score" in ca
    assert isinstance(ca["score"], (int, float))
    assert "reason" in ca


def test_decision_boundary_note_present():
    proc = _run_bridge([
        "--skill", "thesis_generation",
        "--input", "examples/thesis_generation/thesis_with_mixed_evidence.json",
        "--pretty",
    ])
    envelope = json.loads(proc.stdout)
    draft = envelope["artifacts"]["thesis_draft"]
    assert "decision_support" in draft["decision_boundary_note"]
