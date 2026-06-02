"""Tests for runtime bridge with ledger and query plan examples."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_SKILL = str(PROJECT_ROOT / "scripts" / "run_skill.py")


def _run_bridge(skill: str, input_file: str) -> dict:
    path = str(PROJECT_ROOT / input_file)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        [sys.executable, RUN_SKILL, "--skill", skill, "--input", path, "--pretty"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    return json.loads(result.stdout)


class TestRuntimeBridgeLedgerExamples:
    def test_ledger_snapshot_input_runs(self):
        """ledger_snapshot_input.json should run with fund_analysis."""
        output = _run_bridge("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        assert output["ok"] is True
        assert output["status"] in ("OK", "PARTIAL")

    def test_ledger_snapshot_produces_derived_artifacts(self):
        """Derived mode should produce expected artifacts."""
        output = _run_bridge("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        artifacts = output.get("artifacts", {})
        assert "derived_portfolio_snapshot" in artifacts
        assert "ledger_cashflow_summary" in artifacts
        assert "portfolio_summary" in artifacts

    def test_ledger_snapshot_positions_non_empty(self):
        """Derived positions should be non-empty."""
        output = _run_bridge("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        snapshot = output["artifacts"]["derived_portfolio_snapshot"]
        assert len(snapshot["positions"]) >= 1

    def test_research_query_plan_input_runs(self):
        """research_query_plan_input.json should run with fund_analysis."""
        output = _run_bridge("fund_analysis", "examples/runtime_bridge_research_query_plan_input.json")
        assert output["ok"] is True
        assert output["status"] in ("OK", "PARTIAL")

    def test_research_query_plan_produces_plan(self):
        """Research planning mode produces query plan."""
        output = _run_bridge("fund_analysis", "examples/runtime_bridge_research_query_plan_input.json")
        artifacts = output.get("artifacts", {})
        assert "research_query_plan" in artifacts
        plan = artifacts["research_query_plan"]
        assert len(plan["news_queries"]) > 0

    def test_json_output_is_valid(self):
        """Output JSON should be serializable/deserializable."""
        output = _run_bridge("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        json_str = json.dumps(output)
        reparsed = json.loads(json_str)
        assert reparsed["ok"] is True
        assert "artifacts" in reparsed
