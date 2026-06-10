"""Integration tests for thesis_generation fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import (
    run_bridge_inprocess_json,
    run_bridge_subprocess,
)
from tests.support.formal_boundary import (
    assert_no_formal_decision_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]

THESIS_FIXTURES = [
    "examples/thesis_generation/thesis_with_mixed_evidence.json",
    "examples/thesis_generation/thesis_from_fund_analysis_artifacts.json",
    "examples/thesis_generation/thesis_missing_evidence_partial.json",
    "examples/thesis_generation/evidence_graph_balanced_thesis.json",
    "examples/thesis_generation/sparse_context_low_confidence.json",
    "examples/thesis_generation/fund_analysis_report_thesis.json",
]

REQUIRED_THESIS_DRAFT_FIELDS = [
    "task_id",
    "topic",
    "related_entities",
    "thesis_statement",
    "supporting_evidence",
    "counter_evidence",
    "neutral_evidence",
    "missing_evidence",
    "confidence_assessment",
    "watch_conditions",
    "invalidating_conditions",
    "next_research_questions",
    "source_summary",
    "limitations",
    "decision_boundary_note",
]


def _run_thesis(fixture_path: str) -> dict:
    input_text = (ROOT / fixture_path).read_text(encoding="utf-8")
    return run_bridge_inprocess_json(skill="thesis_generation", input_text=input_text)


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
    envelope = _run_thesis(fixture_path)
    assert envelope.get("ok") is True
    assert envelope.get("skill_name") == "thesis_generation"
    assert envelope.get("status") in ("OK", "PARTIAL")


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_thesis_draft_artifact_exists(fixture_path: str):
    envelope = _run_thesis(fixture_path)
    artifacts = envelope.get("artifacts", {})
    assert "thesis_draft" in artifacts, f"Missing thesis_draft in artifacts for {fixture_path}"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_thesis_draft_required_fields(fixture_path: str):
    envelope = _run_thesis(fixture_path)
    draft = envelope.get("artifacts", {}).get("thesis_draft", {})
    for field in REQUIRED_THESIS_DRAFT_FIELDS:
        assert field in draft, f"Missing field '{field}' in thesis_draft for {fixture_path}"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_no_formal_decision_artifacts(fixture_path: str):
    envelope = _run_thesis(fixture_path)
    artifacts = envelope.get("artifacts", {})
    assert_no_formal_decision_artifacts(artifacts)


def test_confidence_assessment_structure():
    envelope = _run_thesis("examples/thesis_generation/thesis_with_mixed_evidence.json")
    draft = envelope["artifacts"]["thesis_draft"]
    ca = draft["confidence_assessment"]
    assert "level" in ca
    assert ca["level"] in ("LOW", "MEDIUM", "HIGH")
    assert "score" in ca
    assert isinstance(ca["score"], (int, float))
    assert "reason" in ca


def test_decision_boundary_note_present():
    envelope = _run_thesis("examples/thesis_generation/thesis_with_mixed_evidence.json")
    draft = envelope["artifacts"]["thesis_draft"]
    assert "decision_support" in draft["decision_boundary_note"]


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
@pytest.mark.subprocess
def test_hyphenated_slug_works(fixture_path: str):
    proc = run_bridge_subprocess(["--skill", "thesis-generation", "--input", fixture_path, "--pretty"])
    assert proc.returncode == 0, f"Hyphenated slug failed for {fixture_path}: {proc.stderr}"
    import json as _json
    envelope = _json.loads(proc.stdout.strip())
    assert envelope.get("ok") is True
    assert envelope.get("skill_name") == "thesis_generation"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_fixture_has_payload_envelope(fixture_path: str):
    data = json.loads((ROOT / fixture_path).read_text(encoding="utf-8"))
    assert "payload" in data, f"{fixture_path} missing payload envelope"


@pytest.mark.parametrize("fixture_path", THESIS_FIXTURES)
def test_no_formal_buy_sell_hold_in_thesis_draft(fixture_path: str):
    envelope = _run_thesis(fixture_path)
    draft = envelope.get("artifacts", {}).get("thesis_draft", {})
    assert "action" not in draft
    assert "recommendation" not in draft
