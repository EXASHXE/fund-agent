"""Integration test for trade plan to decisions demo."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_trade_plan_demo_runs_and_outputs_json():
    result = subprocess.run(
        [sys.executable, "examples/minimal_host_trade_plan_to_decisions.py"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "."},
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"Demo failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert "fund_analysis_status" in data
    assert "portfolio_summary" in data
    assert "evidence_compile_report" in data
    assert "decisions" in data
    assert "execution_ledger" in data


def test_trade_plan_demo_produces_decisions():
    result = subprocess.run(
        [sys.executable, "examples/minimal_host_trade_plan_to_decisions.py"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "."},
        cwd=PROJECT_ROOT,
    )
    data = json.loads(result.stdout)
    decisions = data["decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) >= 1
    assert all(isinstance(d, dict) for d in decisions)
    for d in decisions:
        assert "decision_id" in d
        assert "action" in d


def test_trade_plan_demo_produces_execution_ledger():
    result = subprocess.run(
        [sys.executable, "examples/minimal_host_trade_plan_to_decisions.py"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "."},
        cwd=PROJECT_ROOT,
    )
    data = json.loads(result.stdout)
    ledger = data["execution_ledger"]
    assert isinstance(ledger, dict)
    assert "ledger_id" in ledger
    assert "decisions" in ledger
    assert len(ledger.get("decisions", [])) >= 1


def test_trade_plan_demo_has_no_research_os_or_legacy_import():
    demo_path = PROJECT_ROOT / "examples" / "minimal_host_trade_plan_to_decisions.py"
    tree = ast.parse(demo_path.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = {"src.core.research_os", "legacy", "src.legacy"}
    assert not (imports & forbidden), f"Forbidden imports found: {imports & forbidden}"

    provider_sdks = {"tavily", "finnhub", "exa", "firecrawl", "reddit", "openai", "anthropic", "langchain", "akshare"}
    assert not (imports & provider_sdks), f"Provider SDK imports found: {imports & provider_sdks}"


def test_only_decision_support_produces_decision():
    demo_path = PROJECT_ROOT / "examples" / "minimal_host_trade_plan_to_decisions.py"
    tree = ast.parse(demo_path.read_text())

    from_nodes = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    for node in from_nodes:
        if node.module and "decision" in node.module:
            continue
        for alias in node.names:
            assert alias.name != "Decision", "Decision should not be imported outside decision support context"
