"""Tests for the personal portfolio regression runner."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_personal_regressions.py"


def test_personal_regression_runner_json_outputs_summary():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["summary"]["scenario_count"] >= 14
    assert payload["summary"]["failed_count"] == 0
    assert payload["summary"]["no_broker_execution"] is True
    assert payload["results"]


def test_personal_regression_runner_can_filter_one_scenario():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--scenario",
            "short_holding_7day_fee_sell_zh",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["summary"]["scenario_count"] == 1
    [scenario] = payload["results"]
    assert scenario["scenario_id"] == "short_holding_7day_fee_sell_zh"
    assert scenario["decision_status"] in {"BLOCKED", "DOWNGRADED"}
    assert scenario["no_broker_execution"] is True


def test_json_output_includes_workflow_trace():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--scenario", "mixed_portfolio_report_only_zh", "--json"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    [scenario] = payload["results"]
    assert "workflow_trace" in scenario
    trace = scenario["workflow_trace"]
    assert trace["event_count"] > 0
    events = trace["events"]
    types = [e["type"] for e in events]
    assert "input_loaded" in types
    assert "workflow_completed" in types


def test_json_output_includes_quality_gate():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--scenario", "mixed_portfolio_report_only_zh", "--json"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    [scenario] = payload["results"]
    assert "quality_gate" in scenario
    qg = scenario["quality_gate"]
    assert "passed" in qg
    assert "checks" in qg
    assert "summary" in qg


def test_show_trace_flag():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--scenario", "mixed_portfolio_report_only_zh", "--show-trace"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    assert "input_loaded" in result.stdout
    assert "workflow_completed" in result.stdout


def test_emit_trace_creates_file():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        trace_path = f.name
    try:
        subprocess.run(
            [sys.executable, str(SCRIPT), "--scenario", "mixed_portfolio_report_only_zh", "--emit-trace", trace_path],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        content = Path(trace_path).read_text(encoding="utf-8")
        lines = [line for line in content.strip().split("\n") if line.strip()]
        assert len(lines) > 0
        first = json.loads(lines[0])
        assert "sequence" in first
        assert "type" in first
    finally:
        Path(trace_path).unlink(missing_ok=True)


def test_gate_only_passes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--scenario", "mixed_portfolio_report_only_zh", "--gate-only"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    assert result.returncode == 0
    assert "passed quality gate" in result.stdout
