"""Integration test for minimal host demo."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_minimal_host_demo_runs():
    """The minimal host demo must run and produce JSON output."""
    result = subprocess.run(
        [sys.executable, "examples/minimal_host_news_to_decision.py"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "."},
        cwd=Path(__file__).parent.parent.parent,
    )
    assert result.returncode == 0, f"Demo failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["status"] == "OK"
    assert "decision" in data
    assert "execution_ledger" in data


def test_minimal_host_demo_does_not_import_research_os():
    demo_path = Path(__file__).parent.parent.parent / "examples" / "minimal_host_news_to_decision.py"
    content = demo_path.read_text()

    assert "src.core.research_os" not in content, "Demo imports ResearchOS"
    assert "import legacy" not in content, "Demo imports legacy"
    assert "from legacy" not in content, "Demo imports legacy"


def test_minimal_host_demo_outputs_json_decision():
    result = subprocess.run(
        [sys.executable, "examples/minimal_host_news_to_decision.py"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "."},
        cwd=Path(__file__).parent.parent.parent,
    )
    data = json.loads(result.stdout)

    decision = data["decision"]
    assert isinstance(decision, dict)
    assert "action" in decision
    assert "decision_id" in decision
    assert "rationale_anchor" in decision

    ledger = data["execution_ledger"]
    assert isinstance(ledger, dict)
    assert len(ledger.get("decisions", [])) >= 1

    json.dumps(data)  # Must be JSON serializable
