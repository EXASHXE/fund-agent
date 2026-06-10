"""Structured justification regression tests for decision_support."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from tests.support.formal_boundary import (
    assert_active_decisions_have_anchors,
    assert_no_fake_rationale_anchors,
    extract_formal_decisions,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "examples" / "decision_support"


def _input_from_fixture(name: str) -> SkillInput:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))["payload"]
    return SkillInput(
        task_id=str(payload.get("task_id", "test")),
        step_id=str(payload.get("step_id", "decision-support")),
        skill_name="decision_support",
        payload=payload,
    )


def _run_fixture(name: str):
    return DecisionSupportSkill().run(_input_from_fixture(name))


def test_single_active_buy_with_evidence_has_anchored_structured_fields() -> None:
    output = _run_fixture("single_active_buy_with_evidence.json")

    assert output.status == "OK"
    decision = output.artifacts["decision"]
    assert decision["action"] in {"BUY", "INCREASE"}
    assert decision["evidence_state"] == "ANCHORED"
    assert "EVIDENCE_AVAILABLE" in decision["decision_reason_codes"]
    assert decision["blocked_by"] == []


def test_single_active_buy_without_evidence_downgrades_with_structured_reason() -> None:
    output = _run_fixture("single_active_buy_without_evidence_invalid.json")

    assert output.status == "OK"
    decision = output.artifacts["decision"]
    assert decision["action"] in {"WAIT", "HOLD"}
    assert decision["rationale_anchor"] == []
    assert "EVIDENCE_MISSING" in decision["decision_reason_codes"]
    assert "DOWNGRADED_ACTIVE_TO_HOLD" in decision["decision_reason_codes"]
    assert decision["blocked_by"]


def test_single_passive_without_evidence_has_structured_passive_reason() -> None:
    output = _run_fixture("single_passive_hold_without_evidence.json")

    assert output.status == "OK"
    decision = output.artifacts["decision"]
    assert decision["action"] in {"WAIT", "HOLD", "PAUSE_DCA"}
    assert decision["rationale_anchor"] == []
    assert decision["evidence_state"] in {"INSUFFICIENT_EVIDENCE", "CRITIC_BLOCKED"}
    assert "PASSIVE_ACTION" in decision["decision_reason_codes"]
    assert (
        {"INSUFFICIENT_EVIDENCE", "CRITIC_BLOCKED"}
        & set(decision["decision_reason_codes"])
    )
    assert decision["blocked_by"]


def test_trade_plan_no_evidence_downgrade_has_structured_reason() -> None:
    output = _run_fixture("trade_plan_no_evidence_downgraded.json")

    assert output.status == "OK"
    decisions = output.artifacts.get("decisions") or []
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["action"] == "HOLD"
    assert "DOWNGRADED_ACTIVE_TO_HOLD" in decision["decision_reason_codes"]
    assert decision["evidence_state"] in {"DOWNGRADED", "INSUFFICIENT_EVIDENCE"}
    assert "evidence" in decision["blocked_by"]


def test_forbidden_action_fixture_emits_no_forbidden_formal_decision() -> None:
    output = _run_fixture("trade_plan_forbidden_action_skipped.json")

    assert output.status == "PARTIAL"
    assert extract_formal_decisions(output.artifacts) == []
    warnings = output.warnings or output.artifacts.get("warnings") or []
    assert any("Forbidden action SELL" in warning for warning in warnings)


def test_formal_decisions_do_not_contain_fake_rationale_anchors() -> None:
    fixture_names = [
        "single_active_buy_with_evidence.json",
        "single_passive_hold_without_evidence.json",
        "trade_plan_selected_trade_with_caps.json",
        "trade_plan_no_evidence_downgraded.json",
    ]

    for name in fixture_names:
        output = _run_fixture(name)
        assert output.status == "OK"
        decisions = extract_formal_decisions(output.artifacts)
        assert_no_fake_rationale_anchors(decisions)
        assert_active_decisions_have_anchors(decisions)
