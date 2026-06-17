"""Doctor script tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCTOR_SCRIPT = REPO_ROOT / "install" / "fund-agent-agent-doctor.py"


class TestDoctor:
    @pytest.mark.parametrize("target", ["claude-code", "codex", "opencode", "all"])
    def test_doctor_runs(self, target):
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--target", target],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"doctor --target {target} failed: {result.stderr}"

    def test_doctor_output_valid_json(self):
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--target", "all"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        data = json.loads(result.stdout)
        assert "ok" in data
        assert "checks" in data
        assert "invocation_examples" in data
        assert len(data["checks"]) > 0

    def test_doctor_checks_python(self):
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--target", "claude-code"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        data = json.loads(result.stdout)
        check_ids = [c["id"] for c in data["checks"]]
        assert "python.available" in check_ids

    def test_doctor_checks_bin_runners(self):
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--target", "all"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        data = json.loads(result.stdout)
        check_ids = [c["id"] for c in data["checks"]]
        assert "bin.fund-agent-e2e" in check_ids
        assert "bin.fund-agent-privacy-check" in check_ids

    def test_doctor_checks_privacy(self):
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--target", "all"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        data = json.loads(result.stdout)
        check_ids = [c["id"] for c in data["checks"]]
        assert "privacy.no_tracked_private" in check_ids

    def test_doctor_reports_invocation_examples(self):
        result = subprocess.run(
            [sys.executable, str(DOCTOR_SCRIPT), "--target", "all"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        data = json.loads(result.stdout)
        examples = data.get("invocation_examples", [])
        assert any("claude" in ex.lower() for ex in examples)
        assert any("install" in ex.lower() for ex in examples)
