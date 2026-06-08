"""Structured justification validation for formal Decisions."""

from __future__ import annotations

import pytest

from src.schemas.decision import Decision


def _decision(**overrides: object) -> Decision:
    payload: dict[str, object] = {
        "decision_id": "dec-structured",
        "action": "HOLD",
        "execution_amount": 0.0,
        "rationale_anchor": ["ev-real"],
        "trigger_conditions": ["review condition"],
        "invalidating_conditions": ["new contradictory evidence"],
        "time_horizon": "1 year",
        "risk_budget": 0.05,
    }
    payload.update(overrides)
    return Decision(**payload)  # type: ignore[arg-type]


def test_active_buy_with_real_anchor_and_positive_amount_succeeds() -> None:
    decision = _decision(
        action="BUY",
        execution_amount=1000.0,
        rationale_anchor=["ev-real"],
        decision_reason_codes=["EVIDENCE_AVAILABLE"],
        evidence_state="ANCHORED",
    )

    assert decision.action == "BUY"
    assert decision.rationale_anchor == ["ev-real"]


def test_active_buy_without_anchor_fails_even_with_reason_codes() -> None:
    with pytest.raises(ValueError, match="Active decision"):
        _decision(
            action="BUY",
            execution_amount=1000.0,
            rationale_anchor=[],
            decision_reason_codes=["INSUFFICIENT_EVIDENCE"],
            evidence_state="INSUFFICIENT_EVIDENCE",
        )


def test_passive_wait_empty_anchor_uses_structured_evidence_state() -> None:
    decision = _decision(
        action="WAIT",
        rationale_anchor=[],
        evidence_state="INSUFFICIENT_EVIDENCE",
        blocked_by=["evidence"],
    )

    assert decision.evidence_state == "INSUFFICIENT_EVIDENCE"


def test_passive_hold_empty_anchor_uses_structured_reason_code() -> None:
    decision = _decision(
        action="HOLD",
        rationale_anchor=[],
        decision_reason_codes=["CRITIC_BLOCKED"],
        blocked_by=["critic"],
    )

    assert "CRITIC_BLOCKED" in decision.decision_reason_codes


def test_passive_pause_dca_empty_anchor_without_structured_justification_fails() -> None:
    with pytest.raises(ValueError, match="structured decision_reason_codes"):
        _decision(action="PAUSE_DCA", rationale_anchor=[])


def test_legacy_text_only_passive_empty_anchor_still_succeeds_temporarily() -> None:
    decision = _decision(
        action="WAIT",
        rationale_anchor=[],
        trigger_conditions=["Insufficient evidence to support an active decision"],
        invalidating_conditions=["new evidence becomes available"],
    )

    assert decision.action == "WAIT"
    assert decision.decision_reason_codes == []
    assert decision.evidence_state == "ANCHORED"


def test_fake_anchors_still_fail() -> None:
    with pytest.raises(ValueError, match="fake placeholders"):
        _decision(rationale_anchor=["fake_anchor"])


def test_non_positive_risk_budget_still_fails() -> None:
    with pytest.raises(ValueError, match="risk_budget must be > 0"):
        _decision(risk_budget=0.0)


def test_empty_trigger_conditions_still_fail() -> None:
    with pytest.raises(ValueError, match="trigger_conditions"):
        _decision(trigger_conditions=[])


def test_empty_invalidating_conditions_still_fail() -> None:
    with pytest.raises(ValueError, match="invalidating_conditions"):
        _decision(invalidating_conditions=[])
