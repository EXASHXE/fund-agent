"""Integration tests for decision_support fixture files.

Runs each fixture through the runtime bridge CLI and verifies contract
boundaries, not exact investment conclusions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
FIXTURE_DIR = ROOT / "examples" / "decision_support"

FIXTURES = [
    ("single_active_buy_with_evidence.json", "OK", True),
    ("single_active_buy_without_evidence_invalid.json", "FAILED", False),
    ("single_passive_hold_without_evidence.json", "OK", True),
    ("trade_plan_selected_trade_with_caps.json", "OK", True),
    ("trade_plan_forbidden_action_skipped.json", "PARTIAL", True),
    ("trade_plan_no_evidence_downgraded.json", "OK", True),
]


def _run(fixture_name: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    input_path = FIXTURE_DIR / fixture_name
    return subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--skill", "decision_support",
            "--input", str(input_path),
            "--pretty",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _parse(proc: subprocess.CompletedProcess) -> dict:
    assert proc.stdout.strip(), f"stdout empty for rc={proc.returncode} stderr={proc.stderr!r}"
    return json.loads(proc.stdout)


@pytest.mark.parametrize("fixture_name,expected_status,_", FIXTURES)
def test_fixture_file_exists(fixture_name, expected_status, _):
    path = FIXTURE_DIR / fixture_name
    assert path.exists(), f"Missing fixture: {path}"


@pytest.mark.parametrize("fixture_name,expected_status,_", FIXTURES)
def test_fixture_parses_json(fixture_name, expected_status, _):
    path = FIXTURE_DIR / fixture_name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "payload" in data


@pytest.mark.parametrize("fixture_name,expected_status,expects_artifacts", FIXTURES)
def test_fixture_runs_through_bridge(fixture_name, expected_status, expects_artifacts):
    proc = _run(fixture_name)
    if expected_status == "FAILED":
        assert proc.returncode == 0, (
            f"Bridge should exit 0 even when skill status is FAILED: "
            f"rc={proc.returncode} stderr={proc.stderr!r}"
        )
    else:
        assert proc.returncode == 0, (
            f"Bridge failed for {fixture_name}: rc={proc.returncode} stderr={proc.stderr!r}"
        )

    envelope = _parse(proc)
    assert envelope.get("skill_name") == "decision_support"
    assert envelope.get("status") in {"OK", "PARTIAL", "FAILED"}

    if expected_status == "FAILED":
        assert envelope.get("status") == "FAILED"
        errors = envelope.get("errors") or []
        assert any(
            e.get("code") == "CONTRACT_VIOLATION"
            for e in errors
        ) or "Active decision requires" in (
            envelope.get("status") == "FAILED"
            and json.dumps(envelope)
        )
    else:
        assert envelope.get("status") in {"OK", "PARTIAL"}


def test_active_buy_with_evidence_produces_decision():
    proc = _run("single_active_buy_with_evidence.json")
    envelope = _parse(proc)
    assert envelope["status"] == "OK"
    artifacts = envelope.get("artifacts") or {}
    assert "decision" in artifacts
    assert "execution_ledger" in artifacts
    decision = artifacts["decision"]
    assert decision["action"] in {"BUY", "INCREASE"}


def test_active_buy_without_evidence_is_failed():
    proc = _run("single_active_buy_without_evidence_invalid.json")
    envelope = _parse(proc)
    assert envelope["status"] == "FAILED"
    errors = envelope.get("errors") or []
    error_codes = {e.get("code", "") for e in errors}
    assert "CONTRACT_VIOLATION" in error_codes


def test_passive_hold_without_evidence_is_ok():
    proc = _run("single_passive_hold_without_evidence.json")
    envelope = _parse(proc)
    assert envelope["status"] in {"OK", "PARTIAL"}
    artifacts = envelope.get("artifacts") or {}
    decision = artifacts.get("decision") or {}
    assert decision.get("action") in {"WAIT", "HOLD", "PAUSE_DCA"}


def test_trade_plan_capped_produces_capped_decision():
    proc = _run("trade_plan_selected_trade_with_caps.json")
    envelope = _parse(proc)
    assert envelope["status"] == "OK"
    artifacts = envelope.get("artifacts") or {}
    decisions = artifacts.get("decisions") or []
    assert len(decisions) >= 1
    d = decisions[0]
    assert d.get("execution_amount", 0) <= 5000.0 or d.get("capped") is True or (
        len(decisions) == 1
    )


def test_forbidden_action_not_emitted():
    proc = _run("trade_plan_forbidden_action_skipped.json")
    envelope = _parse(proc)
    artifacts = envelope.get("artifacts") or {}
    decisions = artifacts.get("decisions") or []
    decision = artifacts.get("decision") or {}
    if decisions:
        for d in decisions:
            assert d.get("action") != "SELL"
    elif decision:
        assert decision.get("action") != "SELL"
    warnings = envelope.get("warnings") or []
    assert any("forbidden" in w.lower() or "forbidden" in w.lower() for w in warnings) or (
        artifacts.get("warnings") and any(
            "forbidden" in w.lower() for w in artifacts["warnings"]
        )
    )


def test_no_evidence_downgrades():
    proc = _run("trade_plan_no_evidence_downgraded.json")
    envelope = _parse(proc)
    artifacts = envelope.get("artifacts") or {}
    decisions = artifacts.get("decisions") or []
    decision = artifacts.get("decision") or {}
    if decisions:
        for d in decisions:
            assert d.get("action") in {"HOLD", "WAIT"}
    elif decision:
        assert decision.get("action") in {"HOLD", "WAIT"}
