"""Runtime bridge tests for report quality examples."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _run_skill(skill: str, example_path: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent.parent.parent / "scripts" / "run_skill.py"),
            "--skill", skill,
            "--input", str(example_path),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(Path(__file__).resolve().parent.parent.parent), **__import__("os").environ},
        timeout=30,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    output = json.loads(result.stdout)
    assert output.get("ok") is True
    return output


class TestPersonalReportQualityExample:
    example_path = EXAMPLES_DIR / "runtime_bridge_personal_report_quality_input.json"

    def test_example_file_exists_and_valid_json(self):
        assert self.example_path.exists()
        data = json.loads(self.example_path.read_text())
        assert data["skill_name"] == "fund_analysis"

    def test_fund_analysis_runs_with_report_quality_input(self):
        output = _run_skill("fund_analysis", self.example_path)
        assert output["status"] in ("OK", "PARTIAL")
        artifacts = output["artifacts"]
        assert "data_completeness" in artifacts
        assert "analysis_coverage" in artifacts
        assert "report_limitations" in artifacts
        report = artifacts["fund_analysis_report"]
        assert "data_completeness" in report

    def test_ledger_quality_summary_present_when_derived(self):
        """Ledger snapshot example includes ledger_quality_summary."""
        ledger_path = EXAMPLES_DIR / "runtime_bridge_ledger_snapshot_input.json"
        if not ledger_path.exists():
            pytest.skip("ledger snapshot example not found")
        output = _run_skill("fund_analysis", ledger_path)
        artifacts = output["artifacts"]
        # Derived from transactions should have ledger_quality_summary
        if artifacts.get("source_of_truth") == "derived_from_transactions":
            assert "ledger_quality_summary" in artifacts

    def test_research_query_plan_example_includes_completeness(self):
        """Research query plan example includes data_completeness."""
        query_path = EXAMPLES_DIR / "runtime_bridge_research_query_plan_input.json"
        if not query_path.exists():
            pytest.skip("research query plan example not found")
        output = _run_skill("fund_analysis", query_path)
        artifacts = output["artifacts"]
        assert "data_completeness" in artifacts
        assert "analysis_coverage" in artifacts
        report = artifacts.get("fund_analysis_report", {})
        assert "data_completeness" in report

    def test_no_network_access_in_report_quality(self):
        """Verify the report quality helpers do not reach any network."""
        import importlib
        import sys as _sys

        mod = importlib.import_module("src.tools.portfolio.report_quality")
        source = __import__("inspect").getsource(mod)
        # No urllib, requests, httpx, socket, aiohttp
        for banned in ("import urllib", "import requests", "import httpx",
                       "import socket", "import aiohttp", "import ssl",
                       "from urllib", "from requests", "from httpx"):
            assert banned not in source, f"network import found: {banned}"
