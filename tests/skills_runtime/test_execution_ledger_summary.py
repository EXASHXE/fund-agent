"""Tests for ExecutionLedger ledger_summary."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas.decision import Decision, ExecutionLedger


def _make_decision(
    action: str = "BUY",
    execution_amount: float = 10000.0,
    rationale_anchor: list[str] | None = None,
    evidence_state: str = "ANCHORED",
    reason_codes: list[str] | None = None,
    blocked_by: list[str] | None = None,
    risk_budget: float = 0.05,
) -> Decision:
    return Decision(
        decision_id="test_decision",
        action=action,
        execution_amount=execution_amount,
        rationale_anchor=rationale_anchor or ["ev1"],
        trigger_conditions=["Test trigger"],
        invalidating_conditions=["Test invalidation"],
        time_horizon="1 year",
        risk_budget=risk_budget,
        audit_trail=["Test audit"],
        decision_reason_codes=reason_codes or ["EVIDENCE_AVAILABLE"],
        evidence_state=evidence_state,
        blocked_by=blocked_by or [],
        created_at=datetime(2026, 1, 1),
    )


class TestExecutionLedgerSummary:
    def test_summary_counts_active_passive(self):
        d1 = _make_decision(action="BUY")
        d2 = _make_decision(action="HOLD", execution_amount=0.0, rationale_anchor=[], evidence_state="INSUFFICIENT_EVIDENCE", reason_codes=["INSUFFICIENT_EVIDENCE", "PASSIVE_ACTION"])
        ledger = ExecutionLedger(decisions=[d1, d2])
        summary = ledger.ledger_summary()
        assert summary["active_decision_count"] == 1
        assert summary["passive_decision_count"] == 1
        assert summary["decision_count"] == 2

    def test_summary_counts_blocked(self):
        d1 = _make_decision(action="HOLD", execution_amount=0.0, rationale_anchor=[], evidence_state="BUDGET_BLOCKED", reason_codes=["BUDGET_BLOCKED", "PASSIVE_ACTION"], blocked_by=["budget"])
        ledger = ExecutionLedger(decisions=[d1])
        summary = ledger.ledger_summary()
        assert summary["blocked_decision_count"] == 1
        assert summary["blocked_by_counts"]["budget"] == 1

    def test_summary_sums_execution_amount_and_risk_budget(self):
        d1 = _make_decision(action="BUY", execution_amount=5000.0, risk_budget=0.05)
        d2 = _make_decision(action="SELL", execution_amount=3000.0, risk_budget=0.03)
        ledger = ExecutionLedger(decisions=[d1, d2])
        summary = ledger.ledger_summary()
        assert summary["total_execution_amount"] == 8000.0
        assert summary["total_risk_budget"] == pytest.approx(0.08)

    def test_summary_counts_reason_codes(self):
        d1 = _make_decision(reason_codes=["EVIDENCE_AVAILABLE", "ACTIVE_ACTION_ALLOWED"])
        d2 = _make_decision(reason_codes=["EVIDENCE_AVAILABLE"])
        ledger = ExecutionLedger(decisions=[d1, d2])
        summary = ledger.ledger_summary()
        assert summary["reason_code_counts"]["EVIDENCE_AVAILABLE"] == 2
        assert summary["reason_code_counts"]["ACTIVE_ACTION_ALLOWED"] == 1

    def test_summary_in_to_dict(self):
        d1 = _make_decision()
        ledger = ExecutionLedger(decisions=[d1])
        serialized = ledger.to_dict()
        assert "ledger_summary" in serialized
        assert serialized["ledger_summary"]["decision_count"] == 1
        assert serialized["ledger_summary"]["active_decision_count"] == 1

    def test_summary_downgraded_count(self):
        d1 = _make_decision(action="HOLD", execution_amount=0.0, rationale_anchor=[], evidence_state="DOWNGRADED", reason_codes=["DOWNGRADED_ACTIVE_TO_HOLD", "PASSIVE_ACTION"])
        ledger = ExecutionLedger(decisions=[d1])
        summary = ledger.ledger_summary()
        assert summary["downgraded_decision_count"] == 1

    def test_action_counts_all_keys_present(self):
        d1 = _make_decision()
        ledger = ExecutionLedger(decisions=[d1])
        summary = ledger.ledger_summary()
        for action in ("BUY", "SELL", "INCREASE", "REDUCE", "HOLD", "WAIT", "PAUSE_DCA"):
            assert action in summary["action_counts"]
