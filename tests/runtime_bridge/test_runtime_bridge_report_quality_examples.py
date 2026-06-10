"""Runtime bridge tests for report quality examples."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.tools.portfolio.report_composer import SECTION_ORDER
from tests.support.bridge_runner import run_bridge_inprocess_json


EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"

REQUIRED_REPORT_SECTION_IDS = [section_id for section_id, _ in SECTION_ORDER]


def _run_skill_inprocess(skill: str, example_path: Path) -> dict:
    input_text = example_path.read_text(encoding="utf-8")
    output = run_bridge_inprocess_json(skill=skill, input_text=input_text)
    assert output.get("ok") is True
    return output


class TestPersonalReportQualityExample:
    example_path = EXAMPLES_DIR / "runtime_bridge_personal_report_quality_input.json"

    def test_example_file_exists_and_valid_json(self):
        assert self.example_path.exists()
        data = json.loads(self.example_path.read_text(encoding="utf-8"))
        assert data["skill_name"] == "fund_analysis"

    def test_fund_analysis_runs_with_report_quality_input(self):
        output = _run_skill_inprocess("fund_analysis", self.example_path)
        assert output["status"] in ("OK", "PARTIAL")
        artifacts = output["artifacts"]
        assert "data_completeness" in artifacts
        assert "analysis_coverage" in artifacts
        assert "report_limitations" in artifacts
        assert "report_sections" in artifacts
        assert "report_quality_gate" in artifacts
        report = artifacts["fund_analysis_report"]
        assert "data_completeness" in report
        assert "report_sections" in report
        assert "report_quality_gate" in report
        section_ids = [section["id"] for section in artifacts["report_sections"]]
        assert section_ids == REQUIRED_REPORT_SECTION_IDS
        assert artifacts["report_quality_gate"]["grade"] in ("A", "B", "C", "D")
        assert "decision" not in artifacts
        assert "execution_ledger" not in artifacts

    def test_ledger_quality_summary_present_when_derived(self):
        ledger_path = EXAMPLES_DIR / "runtime_bridge_ledger_snapshot_input.json"
        if not ledger_path.exists():
            pytest.skip("ledger snapshot example not found")
        output = _run_skill_inprocess("fund_analysis", ledger_path)
        artifacts = output["artifacts"]
        if artifacts.get("source_of_truth") == "derived_from_transactions":
            assert "ledger_quality_summary" in artifacts

    def test_research_query_plan_example_includes_completeness(self):
        query_path = EXAMPLES_DIR / "runtime_bridge_research_query_plan_input.json"
        if not query_path.exists():
            pytest.skip("research query plan example not found")
        output = _run_skill_inprocess("fund_analysis", query_path)
        artifacts = output["artifacts"]
        assert "data_completeness" in artifacts
        assert "analysis_coverage" in artifacts
        assert "report_sections" in artifacts
        assert "report_quality_gate" in artifacts
        report = artifacts.get("fund_analysis_report", {})
        assert "data_completeness" in report

    def test_no_network_access_in_report_quality(self):
        import importlib

        for module_name in (
            "src.tools.portfolio.report_quality",
            "src.tools.portfolio.report_composer",
        ):
            mod = importlib.import_module(module_name)
            source = __import__("inspect").getsource(mod)
            for banned in ("import urllib", "import requests", "import httpx",
                           "import socket", "import aiohttp", "import ssl",
                           "from urllib", "from requests", "from httpx"):
                assert banned not in source, f"network import found in {module_name}: {banned}"
