"""Example-level tests for personal fund report flow scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FLOW_SCRIPT = PROJECT_ROOT / "examples" / "minimal_personal_fund_report_flow.py"
DECISION_SCRIPT = PROJECT_ROOT / "examples" / "minimal_personal_fund_report_with_decision_handoff.py"


def _run(script: Path, args: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *(args or [])],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(PROJECT_ROOT), **os.environ},
        timeout=30,
    )


class TestMinimalReportFlow:
    def test_runs_without_network(self):
        result = _run(FLOW_SCRIPT)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

    def test_output_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outpath = Path(tmpdir) / "report.md"
            result = _run(FLOW_SCRIPT, ["--output", str(outpath)])
            assert result.returncode == 0
            assert outpath.exists()
            content = outpath.read_text(encoding="utf-8")
            assert "Executive summary" in content
            assert "Evidence appendix" in content

    def test_output_metadata_when_file_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outpath = Path(tmpdir) / "report.md"
            result = _run(FLOW_SCRIPT, ["--output", str(outpath)])
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data["ok"] is True
            assert data["output_file"] == str(outpath)
            assert "markdown_report" not in data

    def test_exits_nonzero_on_invalid_input(self):
        result = _run(FLOW_SCRIPT, ["--input", "/nonexistent/path.json"])
        assert result.returncode != 0


class TestDecisionHandoff:
    def test_report_only_produces_no_decisions(self):
        result = _run(DECISION_SCRIPT)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "decisions" not in data
        assert "execution_ledger" not in data
        assert "analysis artifact" in data.get("note", "")

    def test_with_decision_runs_decision_support(self):
        result = _run(DECISION_SCRIPT, ["--with-decision"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "decisions" in data
        assert "execution_ledger" in data
        assert "decision_status" in data
