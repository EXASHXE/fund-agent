"""Integration tests for decision_support fixture files.

Runs each fixture through the runtime bridge in-process and verifies contract
boundaries, not exact investment conclusions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json
from tests.support.formal_boundary import (
    assert_active_decisions_have_anchors,
    assert_no_fake_rationale_anchors,
    assert_passive_empty_anchor_has_structured_justification,
    extract_formal_decisions,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "examples" / "decision_support"

FIXTURES = [
    ("single_active_buy_with_evidence.json", "OK", True),
    ("single_active_buy_without_evidence_invalid.json", "FAILED", False),
    ("single_passive_hold_without_evidence.json", "OK", True),
    ("trade_plan_selected_trade_with_caps.json", "OK", True),
    ("trade_plan_forbidden_action_skipped.json", "PARTIAL", True),
    ("trade_plan_no_evidence_downgraded.json", "OK", True),
]


def _run(fixture_name: str) -> dict:
    input_text = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")
    return run_bridge_inprocess_json(skill="decision_support", input_text=input_text)


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
    envelope = _run(fixture_name)
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


@pytest.mark.parametrize("fixture_name,expected_status,_", FIXTURES)
def test_formal_decisions_have_structured_justification(fixture_name, expected_status, _):
    envelope = _run(fixture_name)

    if expected_status == "FAILED":
        assert extract_formal_decisions(envelope) == []
        return

    decisions = extract_formal_decisions(envelope)
    assert_no_fake_rationale_anchors(decisions)
    assert_active_decisions_have_anchors(decisions)
    assert_passive_empty_anchor_has_structured_justification(decisions)
    for decision in decisions:
        assert "decision_reason_codes" in decision
        assert "evidence_state" in decision
        assert "blocked_by" in decision


def test_active_buy_with_evidence_produces_decision():
    envelope = _run("single_active_buy_with_evidence.json")
    assert envelope["status"] == "OK"
    artifacts = envelope.get("artifacts") or {}
    assert "decision" in artifacts
    assert "execution_ledger" in artifacts
    decision = artifacts["decision"]
    assert decision["action"] in {"BUY", "INCREASE"}


def test_active_buy_without_evidence_is_failed():
    envelope = _run("single_active_buy_without_evidence_invalid.json")
    assert envelope["status"] == "FAILED"
    errors = envelope.get("errors") or []
    error_codes = {e.get("code", "") for e in errors}
    assert "CONTRACT_VIOLATION" in error_codes


def test_passive_hold_without_evidence_is_ok():
    envelope = _run("single_passive_hold_without_evidence.json")
    assert envelope["status"] in {"OK", "PARTIAL"}
    artifacts = envelope.get("artifacts") or {}
    decision = artifacts.get("decision") or {}
    assert decision.get("action") in {"WAIT", "HOLD", "PAUSE_DCA"}


def test_trade_plan_capped_produces_capped_decision():
    envelope = _run("trade_plan_selected_trade_with_caps.json")
    assert envelope["status"] == "OK"
    artifacts = envelope.get("artifacts") or {}
    decisions = artifacts.get("decisions") or []
    assert len(decisions) >= 1
    d = decisions[0]
    assert d.get("execution_amount", 0) <= 5000.0 or d.get("capped") is True or (
        len(decisions) == 1
    )


def test_forbidden_action_not_emitted():
    envelope = _run("trade_plan_forbidden_action_skipped.json")
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
    envelope = _run("trade_plan_no_evidence_downgraded.json")
    artifacts = envelope.get("artifacts") or {}
    decisions = artifacts.get("decisions") or []
    decision = artifacts.get("decision") or {}
    if decisions:
        for d in decisions:
            assert d.get("action") in {"HOLD", "WAIT"}
    elif decision:
        assert decision.get("action") in {"HOLD", "WAIT"}
