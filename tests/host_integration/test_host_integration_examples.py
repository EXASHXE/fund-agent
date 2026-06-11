"""Tests for host integration example scripts.

Verifies that the example scripts exist and run successfully.
Does not require env vars or network.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "examples" / "host_integration"

FUND_ANALYSIS_SUBPROCESS = EXAMPLES_DIR / "minimal_fund_analysis_subprocess.py"
DECISION_SUPPORT_SUBPROCESS = EXAMPLES_DIR / "minimal_decision_support_subprocess.py"
FUND_ANALYSIS_RUNTIME = EXAMPLES_DIR / "minimal_fund_analysis_runtime_call.py"
DECISION_SUPPORT_RUNTIME = EXAMPLES_DIR / "minimal_decision_support_call.py"

WORKFLOW_DOC = EXAMPLES_DIR / "minimal_open_agent_workflow.md"
CONTRACT_DOC = EXAMPLES_DIR / "host_integration_contract.md"
MCP_DOC = EXAMPLES_DIR / "mcp_host_injection_example.md"


def test_fund_analysis_subprocess_exists() -> None:
    assert FUND_ANALYSIS_SUBPROCESS.is_file()


def test_decision_support_subprocess_exists() -> None:
    assert DECISION_SUPPORT_SUBPROCESS.is_file()


def test_fund_analysis_runtime_exists() -> None:
    assert FUND_ANALYSIS_RUNTIME.is_file()


def test_decision_support_runtime_exists() -> None:
    assert DECISION_SUPPORT_RUNTIME.is_file()


def test_workflow_doc_exists() -> None:
    assert WORKFLOW_DOC.is_file()


def test_contract_doc_exists() -> None:
    assert CONTRACT_DOC.is_file()


def test_mcp_doc_exists() -> None:
    assert MCP_DOC.is_file()


def test_fund_analysis_runtime_call_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(FUND_ANALYSIS_RUNTIME)],
        capture_output=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )
    assert proc.returncode == 0, (
        f"minimal_fund_analysis_runtime_call.py failed: "
        f"{proc.stderr.decode('utf-8', errors='replace')[:500]}"
    )


def test_decision_support_runtime_call_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(DECISION_SUPPORT_RUNTIME)],
        capture_output=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )
    assert proc.returncode == 0, (
        f"minimal_decision_support_call.py failed: "
        f"{proc.stderr.decode('utf-8', errors='replace')[:500]}"
    )


def test_fund_analysis_subprocess_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(FUND_ANALYSIS_SUBPROCESS)],
        capture_output=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )
    assert proc.returncode == 0, (
        f"minimal_fund_analysis_subprocess.py failed: "
        f"{proc.stderr.decode('utf-8', errors='replace')[:500]}"
    )


def test_decision_support_subprocess_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(DECISION_SUPPORT_SUBPROCESS)],
        capture_output=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )
    assert proc.returncode == 0, (
        f"minimal_decision_support_subprocess.py failed: "
        f"{proc.stderr.decode('utf-8', errors='replace')[:500]}"
    )


def test_workflow_doc_mentions_boundaries() -> None:
    content = WORKFLOW_DOC.read_text(encoding="utf-8")
    assert "fund_analysis" in content
    assert "decision_support" in content
    assert "Decision" in content or "decision" in content
    assert "broker" in content.lower() or "execution" in content.lower()


def test_contract_doc_mentions_host_owned() -> None:
    content = CONTRACT_DOC.read_text(encoding="utf-8")
    assert "host-owned" in content or "host owns" in content.lower()
    assert "broker" in content.lower()
    assert "MCP" in content or "mcp" in content


def test_mcp_doc_mentions_payload_fields() -> None:
    content = MCP_DOC.read_text(encoding="utf-8")
    assert "news_evidence" in content
    assert "sentiment_evidence" in content
    assert "benchmark_history" in content
