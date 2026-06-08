"""Runtime bridge tests for thesis_generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = ROOT / "scripts" / "run_skill.py"


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


class TestRuntimeBridgeThesisGeneration:
    def test_output_schema_returns_thesis_draft(self):
        proc = _run_bridge(["--skill", "thesis_generation", "--output-schema", "--pretty"])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        schema = envelope.get("output_schema", {})
        artifacts = schema.get("artifacts", {})
        known_keys = [k.get("key") for k in artifacts.get("known_keys", [])]
        assert "thesis_draft" in known_keys

    def test_fixture_run_succeeds(self):
        proc = _run_bridge([
            "--skill", "thesis_generation",
            "--input", "examples/thesis_generation/thesis_with_mixed_evidence.json",
            "--pretty",
        ])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        assert envelope.get("ok") is True

    def test_artifacts_thesis_draft_exists(self):
        proc = _run_bridge([
            "--skill", "thesis_generation",
            "--input", "examples/thesis_generation/thesis_with_mixed_evidence.json",
            "--pretty",
        ])
        envelope = json.loads(proc.stdout)
        assert "thesis_draft" in envelope.get("artifacts", {})

    def test_no_formal_decision_artifacts(self):
        proc = _run_bridge([
            "--skill", "thesis_generation",
            "--input", "examples/thesis_generation/thesis_with_mixed_evidence.json",
            "--pretty",
        ])
        envelope = json.loads(proc.stdout)
        artifacts = envelope.get("artifacts", {})
        for key in ("decision", "decisions", "execution_ledger", "execution_ledgers"):
            assert key not in artifacts

    def test_hyphenated_skill_name_works(self):
        proc = _run_bridge([
            "--skill", "thesis-generation",
            "--input", "examples/thesis_generation/thesis_with_mixed_evidence.json",
            "--pretty",
        ])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        assert envelope.get("ok") is True

    def test_output_schema_has_thesis_draft_fields(self):
        proc = _run_bridge(["--skill", "thesis_generation", "--output-schema", "--pretty"])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
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
        proc = _run_bridge(["--skill", "thesis_generation", "--output-schema", "--pretty"])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        schema = envelope.get("output_schema", {})
        artifacts = schema.get("artifacts", {})
        forbidden = artifacts.get("formal_outputs_forbidden", [])
        assert "Decision" in forbidden
        assert "ExecutionLedger" in forbidden

    def test_output_schema_status_values_match_yaml(self):
        proc = _run_bridge(["--skill", "thesis_generation", "--output-schema", "--pretty"])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        schema = envelope.get("output_schema", {})
        status_values = set(schema.get("status_values", []))
        assert status_values == {"OK", "PARTIAL", "FAILED"}

    def test_hyphenated_output_schema_works(self):
        proc = _run_bridge(["--skill", "thesis-generation", "--output-schema", "--pretty"])
        assert proc.returncode == 0
        envelope = json.loads(proc.stdout)
        assert envelope.get("ok") is True
        known_keys = [
            k.get("key")
            for k in envelope.get("output_schema", {}).get("artifacts", {}).get("known_keys", [])
        ]
        assert "thesis_draft" in known_keys
