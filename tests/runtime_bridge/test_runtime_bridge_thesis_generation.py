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
