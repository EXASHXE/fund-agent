"""Runtime bridge tests for thesis_generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json, run_bridge_inprocess_metadata, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]
THESIS_FIXTURE = ROOT / "examples" / "thesis_generation" / "thesis_with_mixed_evidence.json"


def _thesis_output_schema() -> dict:
    return run_bridge_inprocess_metadata(skill="thesis_generation", output_schema=True, pretty=True)


def _thesis_fixture_input_text() -> str:
    return THESIS_FIXTURE.read_text(encoding="utf-8")


def _run_thesis_fixture() -> dict:
    return run_bridge_inprocess_json(
        skill="thesis_generation",
        input_text=_thesis_fixture_input_text(),
    )


class TestRuntimeBridgeThesisGeneration:
    def test_output_schema_returns_thesis_draft(self):
        envelope = _thesis_output_schema()
        schema = envelope.get("output_schema", {})
        artifacts = schema.get("artifacts", {})
        known_keys = [k.get("key") for k in artifacts.get("known_keys", [])]
        assert "thesis_draft" in known_keys

    def test_fixture_run_succeeds(self):
        envelope = _run_thesis_fixture()
        assert envelope.get("ok") is True

    def test_artifacts_thesis_draft_exists(self):
        envelope = _run_thesis_fixture()
        assert "thesis_draft" in envelope.get("artifacts", {})

    def test_no_formal_decision_artifacts(self):
        envelope = _run_thesis_fixture()
        artifacts = envelope.get("artifacts", {})
        for key in ("decision", "decisions", "execution_ledger", "execution_ledgers"):
            assert key not in artifacts

    @pytest.mark.subprocess
    def test_hyphenated_skill_name_works(self):
        proc = run_bridge_subprocess([
            "--skill", "thesis-generation",
            "--input", "examples/thesis_generation/thesis_with_mixed_evidence.json",
            "--pretty",
        ])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        assert envelope.get("ok") is True

    def test_output_schema_has_thesis_draft_fields(self):
        envelope = _thesis_output_schema()
        schema = envelope.get("output_schema", {})
        fields = schema.get("thesis_draft_fields", [])
        expected = {
            "task_id", "topic", "related_entities", "thesis_statement",
            "supporting_evidence", "counter_evidence", "neutral_evidence",
            "missing_evidence", "confidence_assessment", "watch_conditions",
            "invalidating_conditions", "next_research_questions",
            "source_summary", "limitations", "decision_boundary_note",
        }
        assert set(fields) == expected

    def test_output_schema_formal_outputs_forbidden(self):
        envelope = _thesis_output_schema()
        schema = envelope.get("output_schema", {})
        artifacts = schema.get("artifacts", {})
        forbidden = artifacts.get("formal_outputs_forbidden", [])
        assert "Decision" in forbidden
        assert "ExecutionLedger" in forbidden

    def test_output_schema_status_values_match_yaml(self):
        envelope = _thesis_output_schema()
        schema = envelope.get("output_schema", {})
        status_values = set(schema.get("status_values", []))
        assert status_values == {"OK", "PARTIAL", "FAILED"}

    @pytest.mark.subprocess
    def test_hyphenated_output_schema_works(self):
        proc = run_bridge_subprocess(["--skill", "thesis-generation", "--output-schema", "--pretty"])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        assert envelope.get("ok") is True
        known_keys = [
            k.get("key")
            for k in envelope.get("output_schema", {}).get("artifacts", {}).get("known_keys", [])
        ]
        assert "thesis_draft" in known_keys
