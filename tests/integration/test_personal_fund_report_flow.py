"""Integration tests for minimal_personal_fund_report_flow.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FLOW_SCRIPT = PROJECT_ROOT / "examples" / "minimal_personal_fund_report_flow.py"


def _run_flow(args: list[str] | None = None) -> dict:
    result = subprocess.run(
        [sys.executable, str(FLOW_SCRIPT), *(args or [])],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(PROJECT_ROOT), **__import__("os").environ},
        timeout=30,
    )
    assert result.returncode == 0, f"flow failed: {result.stderr}"
    return json.loads(result.stdout)


class TestPersonalFundReportFlow:
    def test_runs_without_arguments(self):
        output = _run_flow()
        assert output["ok"] is True

    def test_output_contains_required_section_titles_in_markdown(self):
        output = _run_flow()
        md = output["markdown_report"]
        assert "Executive summary" in md
        assert "Portfolio snapshot" in md
        assert "Risk flags" in md
        assert "Data completeness and limitations" in md
        assert "Evidence appendix" in md

    def test_output_contains_limitations_when_sections_partial(self):
        output = _run_flow()
        md = output["markdown_report"]
        if "[PARTIAL]" in md:
            assert "Limitations" in md or "limitations" in md.lower()

    def test_output_contains_no_decision_or_execution_ledger(self):
        output = _run_flow()
        md = output["markdown_report"]
        assert "Decision" not in md
        assert "ExecutionLedger" not in md

    def test_output_is_deterministic(self):
        out1 = _run_flow()
        out2 = _run_flow()
        assert out1["markdown_report"] == out2["markdown_report"]

    def test_has_data_completeness(self):
        output = _run_flow()
        assert "data_completeness" in output
        assert "grade" in output["data_completeness"]

    def test_has_analysis_coverage(self):
        output = _run_flow()
        assert "analysis_coverage" in output
        assert "portfolio" in output["analysis_coverage"]

    def test_has_report_quality_gate(self):
        output = _run_flow()
        assert "report_quality_gate" in output
        assert "can_publish_professional_report" in output["report_quality_gate"]
