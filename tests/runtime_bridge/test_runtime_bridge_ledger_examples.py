"""Tests for runtime bridge with ledger and query plan examples."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_bridge_inprocess(skill: str, input_file: str) -> dict:
    input_text = (PROJECT_ROOT / input_file).read_text(encoding="utf-8")
    return run_bridge_inprocess_json(skill=skill, input_text=input_text)


class TestRuntimeBridgeLedgerExamples:
    def test_ledger_snapshot_input_runs(self):
        output = _run_bridge_inprocess("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        assert output["ok"] is True
        assert output["status"] in ("OK", "PARTIAL")

    def test_ledger_snapshot_produces_derived_artifacts(self):
        output = _run_bridge_inprocess("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        artifacts = output.get("artifacts", {})
        assert "derived_portfolio_snapshot" in artifacts
        assert "ledger_cashflow_summary" in artifacts
        assert "portfolio_summary" in artifacts

    def test_ledger_snapshot_positions_non_empty(self):
        output = _run_bridge_inprocess("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        snapshot = output["artifacts"]["derived_portfolio_snapshot"]
        assert len(snapshot["positions"]) >= 1

    def test_research_query_plan_input_runs(self):
        output = _run_bridge_inprocess("fund_analysis", "examples/runtime_bridge_research_query_plan_input.json")
        assert output["ok"] is True
        assert output["status"] in ("OK", "PARTIAL")

    def test_research_query_plan_produces_plan(self):
        output = _run_bridge_inprocess("fund_analysis", "examples/runtime_bridge_research_query_plan_input.json")
        artifacts = output.get("artifacts", {})
        assert "research_query_plan" in artifacts
        plan = artifacts["research_query_plan"]
        assert len(plan["news_queries"]) > 0

    def test_json_output_is_valid(self):
        output = _run_bridge_inprocess("fund_analysis", "examples/runtime_bridge_ledger_snapshot_input.json")
        json_str = json.dumps(output)
        reparsed = json.loads(json_str)
        assert reparsed["ok"] is True
        assert "artifacts" in reparsed
