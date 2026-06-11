"""Tests for decision_support runtime bridge sample (v1.2).

Verifies the runtime_bridge_decision_support_input_v2.json sample
produces the expected artifacts when run through DecisionSupportSkill.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "runtime_bridge_decision_support_input_v2.json"
)


@pytest.fixture()
def sample_input() -> dict:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return raw


def test_fixture_file_exists() -> None:
    assert FIXTURE_PATH.is_file(), f"Fixture not found: {FIXTURE_PATH}"


def test_decision_support_produces_decision(sample_input: dict) -> None:
    skill_input = SkillInput(
        task_id=sample_input["task_id"],
        step_id=sample_input["step_id"],
        skill_name=sample_input["skill_name"],
        payload=sample_input["payload"],
    )
    output = DecisionSupportSkill().run(skill_input)
    artifacts = output.artifacts

    assert "decision" in artifacts, "Missing decision artifact"
    decision = artifacts["decision"]
    assert isinstance(decision, dict)
    assert "action" in decision
    assert "decision_reason_codes" in decision
    assert isinstance(decision["decision_reason_codes"], list)


def test_decision_support_produces_execution_ledger(sample_input: dict) -> None:
    skill_input = SkillInput(
        task_id=sample_input["task_id"],
        step_id=sample_input["step_id"],
        skill_name=sample_input["skill_name"],
        payload=sample_input["payload"],
    )
    output = DecisionSupportSkill().run(skill_input)
    artifacts = output.artifacts

    assert "execution_ledger" in artifacts, "Missing execution_ledger"
    ledger = artifacts["execution_ledger"]
    assert isinstance(ledger, dict)
    assert "ledger_summary" in ledger, "Missing ledger_summary in execution_ledger"
    summary = ledger["ledger_summary"]
    assert isinstance(summary, dict)
    assert "decision_count" in summary


def test_decision_support_produces_anchor_diagnostics(sample_input: dict) -> None:
    skill_input = SkillInput(
        task_id=sample_input["task_id"],
        step_id=sample_input["step_id"],
        skill_name=sample_input["skill_name"],
        payload=sample_input["payload"],
    )
    output = DecisionSupportSkill().run(skill_input)
    artifacts = output.artifacts

    assert "evidence_anchor_diagnostics" in artifacts, (
        "Missing evidence_anchor_diagnostics"
    )


def test_decision_support_produces_risk_constraint_conflicts(sample_input: dict) -> None:
    skill_input = SkillInput(
        task_id=sample_input["task_id"],
        step_id=sample_input["step_id"],
        skill_name=sample_input["skill_name"],
        payload=sample_input["payload"],
    )
    output = DecisionSupportSkill().run(skill_input)
    artifacts = output.artifacts

    assert "risk_constraint_conflicts" in artifacts, (
        "Missing risk_constraint_conflicts"
    )


def test_decision_support_no_broker_fields(sample_input: dict) -> None:
    skill_input = SkillInput(
        task_id=sample_input["task_id"],
        step_id=sample_input["step_id"],
        skill_name=sample_input["skill_name"],
        payload=sample_input["payload"],
    )
    output = DecisionSupportSkill().run(skill_input)
    artifacts = output.artifacts

    broker_fields = {"broker_order", "order_execution", "trade_execution"}
    found = broker_fields & set(artifacts.keys())
    assert not found, f"Found broker/order execution fields: {found}"


def test_decision_support_sell_scenario(sample_input: dict) -> None:
    skill_input = SkillInput(
        task_id=sample_input["task_id"],
        step_id=sample_input["step_id"],
        skill_name=sample_input["skill_name"],
        payload=sample_input["payload"],
    )
    output = DecisionSupportSkill().run(skill_input)
    decision = output.artifacts.get("decision", {})

    assert decision.get("action") in ("SELL", "HOLD", "WAIT", "REDUCE"), (
        f"Unexpected action: {decision.get('action')}"
    )
