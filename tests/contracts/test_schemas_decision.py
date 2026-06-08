"""Tests for the Decision schema (decision-contract.v2) and ExecutionLedger."""

from __future__ import annotations

import re

import pytest
from datetime import datetime
from src.schemas.decision import Decision, ExecutionLedger


def _make_valid_decision(**overrides: object) -> Decision:
    """Helper to build a minimal valid Decision, overriding any fields."""
    defaults: dict[str, object] = {
        "decision_id": "dec-001",
        "action": "HOLD",
        "execution_amount": 0.0,
        "rationale_anchor": ["ev-001"],
        "trigger_conditions": ["price_below_ma50"],
        "invalidating_conditions": ["price_above_ma200"],
        "time_horizon": "1M",
        "risk_budget": 0.05,
    }
    defaults.update(overrides)
    return Decision(**defaults)  # type: ignore[arg-type]


class TestDecisionActionValidation:
    """Tests for Decision action-based validation."""

    def test_buy_with_positive_amount_passes(self):
        """BUY action with execution_amount > 0 should be valid."""
        decision = _make_valid_decision(
            action="BUY",
            execution_amount=10000.0,
        )
        assert decision.action == "BUY"
        assert decision.execution_amount == 10000.0

    def test_sell_with_positive_amount_passes(self):
        """SELL action with execution_amount > 0 should be valid."""
        decision = _make_valid_decision(
            action="SELL",
            execution_amount=5000.0,
        )
        assert decision.action == "SELL"
        assert decision.execution_amount == 5000.0

    def test_increase_with_positive_amount_passes(self):
        """INCREASE action with execution_amount > 0 should be valid."""
        decision = _make_valid_decision(
            action="INCREASE",
            execution_amount=2000.0,
        )
        assert decision.action == "INCREASE"
        assert decision.execution_amount == 2000.0

    def test_reduce_with_positive_amount_passes(self):
        """REDUCE action with execution_amount > 0 should be valid."""
        decision = _make_valid_decision(
            action="REDUCE",
            execution_amount=3000.0,
        )
        assert decision.action == "REDUCE"
        assert decision.execution_amount == 3000.0

    def test_buy_with_zero_amount_raises(self):
        """BUY action with execution_amount=0 should raise ValueError."""
        with pytest.raises(ValueError, match="requires execution_amount > 0"):
            _make_valid_decision(
                action="BUY",
                execution_amount=0.0,
            )

    def test_sell_with_zero_amount_raises(self):
        """SELL action with execution_amount=0 should raise ValueError."""
        with pytest.raises(ValueError, match="requires execution_amount > 0"):
            _make_valid_decision(
                action="SELL",
                execution_amount=0.0,
            )

    def test_increase_with_zero_amount_raises(self):
        """INCREASE action with execution_amount=0 should raise ValueError."""
        with pytest.raises(ValueError, match="requires execution_amount > 0"):
            _make_valid_decision(
                action="INCREASE",
                execution_amount=0.0,
            )

    def test_reduce_with_zero_amount_raises(self):
        """REDUCE action with execution_amount=0 should raise ValueError."""
        with pytest.raises(ValueError, match="requires execution_amount > 0"):
            _make_valid_decision(
                action="REDUCE",
                execution_amount=0.0,
            )

    def test_buy_with_negative_amount_raises(self):
        """BUY action with negative execution_amount should raise ValueError."""
        with pytest.raises(ValueError, match="requires execution_amount > 0"):
            _make_valid_decision(
                action="BUY",
                execution_amount=-100.0,
            )

    def test_hold_with_zero_amount_passes(self):
        """HOLD action with execution_amount=0 should be valid."""
        decision = _make_valid_decision(
            action="HOLD",
            execution_amount=0.0,
        )
        assert decision.action == "HOLD"
        assert decision.execution_amount == 0.0

    def test_hold_with_positive_amount_passes(self):
        """HOLD action with non-zero amount is allowed (informational)."""
        decision = _make_valid_decision(
            action="HOLD",
            execution_amount=500.0,
        )
        assert decision.action == "HOLD"

    def test_wait_with_zero_amount_passes(self):
        """WAIT action with execution_amount=0 should be valid."""
        decision = _make_valid_decision(
            action="WAIT",
            execution_amount=0.0,
        )
        assert decision.action == "WAIT"

    def test_pause_dca_with_zero_amount_passes(self):
        """PAUSE_DCA action with execution_amount=0 should be valid."""
        decision = _make_valid_decision(
            action="PAUSE_DCA",
            execution_amount=0.0,
        )
        assert decision.action == "PAUSE_DCA"


class TestDecisionConditionValidation:
    """Tests for Decision conditions validation."""

    def test_missing_trigger_conditions_raises(self):
        """Empty trigger_conditions should raise ValueError."""
        with pytest.raises(ValueError, match="trigger_conditions"):
            _make_valid_decision(trigger_conditions=[])

    def test_missing_invalidating_conditions_raises(self):
        """Empty invalidating_conditions should raise ValueError."""
        with pytest.raises(ValueError, match="invalidating_conditions"):
            _make_valid_decision(invalidating_conditions=[])

    def test_empty_rationale_anchor_raises(self):
        """Empty rationale_anchor should raise ValueError."""
        with pytest.raises(ValueError, match="rationale_anchor"):
            _make_valid_decision(rationale_anchor=[])


class TestDecisionRiskBudgetValidation:
    """Tests for Decision risk_budget validation."""

    def test_zero_risk_budget_raises(self):
        """risk_budget=0 should raise ValueError."""
        with pytest.raises(ValueError, match="risk_budget must be > 0"):
            _make_valid_decision(risk_budget=0.0)

    def test_negative_risk_budget_raises(self):
        """Negative risk_budget should raise ValueError."""
        with pytest.raises(ValueError, match="risk_budget must be > 0"):
            _make_valid_decision(risk_budget=-0.01)

    def test_positive_risk_budget_passes(self):
        """Positive risk_budget should be valid."""
        decision = _make_valid_decision(risk_budget=0.1)
        assert decision.risk_budget == 0.1


class TestDecisionDefaults:
    """Tests for Decision default values."""

    def test_version_default(self):
        """Version should default to decision-contract.v2."""
        decision = _make_valid_decision()
        assert decision.version == "decision-contract.v2"

    def test_audit_trail_default_empty(self):
        """audit_trail should default to an empty list."""
        decision = _make_valid_decision()
        assert decision.audit_trail == []

    def test_created_at_auto_generated(self):
        """created_at should be auto-generated."""
        decision = _make_valid_decision()
        assert isinstance(decision.created_at, datetime)

    def test_custom_version(self):
        """Custom version string should be accepted."""
        decision = _make_valid_decision(version="decision-contract.v3")
        assert decision.version == "decision-contract.v3"


class TestDecisionSerialization:
    """Tests for Decision serialization."""

    def test_to_dict_serialization(self):
        """to_dict should produce a JSON-compatible dict."""
        decision = _make_valid_decision(
            decision_id="dec-001",
            action="BUY",
            execution_amount=10000.0,
            rationale_anchor=["ev-001", "ev-002"],
            trigger_conditions=["price_below_ma50", "rsi_below_30"],
            invalidating_conditions=["price_above_ma200"],
            time_horizon="1M",
            risk_budget=0.05,
            audit_trail=["ev-001", "ev-002", "ev-003"],
        )
        d = decision.to_dict()
        assert d["decision_id"] == "dec-001"
        assert d["action"] == "BUY"
        assert d["execution_amount"] == 10000.0
        assert d["rationale_anchor"] == ["ev-001", "ev-002"]
        assert d["trigger_conditions"] == ["price_below_ma50", "rsi_below_30"]
        assert d["invalidating_conditions"] == ["price_above_ma200"]
        assert d["time_horizon"] == "1M"
        assert d["risk_budget"] == 0.05
        assert d["audit_trail"] == ["ev-001", "ev-002", "ev-003"]
        assert d["decision_reason_codes"] == []
        assert d["evidence_state"] == "ANCHORED"
        assert d["blocked_by"] == []
        assert d["version"] == "decision-contract.v2"
        assert isinstance(d["created_at"], str)

    def test_to_dict_includes_all_fields(self):
        """to_dict should include all Decision fields."""
        decision = _make_valid_decision()
        d = decision.to_dict()
        expected_keys = {
            "decision_id", "action", "execution_amount",
            "rationale_anchor", "trigger_conditions",
            "invalidating_conditions", "time_horizon",
            "risk_budget", "audit_trail", "decision_reason_codes",
            "evidence_state", "blocked_by", "version", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_created_at_isoformat(self):
        """created_at should be ISO format string in to_dict output."""
        decision = _make_valid_decision()
        d = decision.to_dict()
        # Verify it's a valid ISO datetime string
        datetime.fromisoformat(d["created_at"])


class TestExecutionLedger:
    """Tests for ExecutionLedger wrapper."""

    def test_empty_ledger(self):
        """Empty ledger should have zero risk budget and empty summary."""
        ledger = ExecutionLedger(decisions=[])
        assert ledger.total_risk_budget() == 0.0
        assert ledger.actions_summary() == {}

    def test_total_risk_budget(self):
        """total_risk_budget should sum all risk budgets."""
        decisions = [
            _make_valid_decision(decision_id="d1", risk_budget=0.05),
            _make_valid_decision(decision_id="d2", risk_budget=0.10),
            _make_valid_decision(decision_id="d3", risk_budget=0.03),
        ]
        ledger = ExecutionLedger(decisions=decisions)
        assert ledger.total_risk_budget() == pytest.approx(0.18)

    def test_actions_summary(self):
        """actions_summary should count each action type."""
        decisions = [
            _make_valid_decision(decision_id="d1", action="BUY", execution_amount=1000.0),
            _make_valid_decision(decision_id="d2", action="BUY", execution_amount=2000.0),
            _make_valid_decision(decision_id="d3", action="HOLD", execution_amount=0.0),
            _make_valid_decision(decision_id="d4", action="SELL", execution_amount=500.0),
        ]
        ledger = ExecutionLedger(decisions=decisions)
        assert ledger.actions_summary() == {"BUY": 2, "HOLD": 1, "SELL": 1}

    def test_to_dict_serialization(self):
        """to_dict should produce complete JSON-compatible dict."""
        decisions = [
            _make_valid_decision(decision_id="d1", action="BUY", execution_amount=1000.0),
            _make_valid_decision(decision_id="d2", action="HOLD", execution_amount=0.0),
        ]
        ledger = ExecutionLedger(decisions=decisions)
        d = ledger.to_dict()
        assert d["version"] == "execution-ledger.v1"
        assert isinstance(d["generated_at"], str)
        assert len(d["decisions"]) == 2
        assert d["decisions"][0]["decision_id"] == "d1"
        assert d["decisions"][1]["decision_id"] == "d2"

    def test_version_default(self):
        """Version should default to execution-ledger.v1."""
        ledger = ExecutionLedger(decisions=[])
        assert ledger.version == "execution-ledger.v1"

    def test_generated_at_auto_generated(self):
        """generated_at should be auto-generated."""
        ledger = ExecutionLedger(decisions=[])
        assert isinstance(ledger.generated_at, datetime)


class TestDecisionEdgeCases:
    """Edge case tests for Decision."""

    def test_all_action_types_are_valid(self):
        """All seven ActionType literals should be accepted."""
        actions = ["BUY", "SELL", "HOLD", "PAUSE_DCA", "REDUCE", "INCREASE", "WAIT"]
        for action in actions:
            kwargs: dict[str, object] = {
                "decision_id": f"dec-{action.lower()}",
                "action": action,
                "execution_amount": 1000.0 if action in ("BUY", "SELL", "INCREASE", "REDUCE") else 0.0,
                "rationale_anchor": ["ev-001"],
                "trigger_conditions": ["cond"],
                "invalidating_conditions": ["inv_cond"],
                "time_horizon": "1M",
                "risk_budget": 0.05,
            }
            decision = Decision(**kwargs)  # type: ignore[arg-type]
            assert decision.action == action

    def test_multiple_rationale_anchors(self):
        """rationale_anchor can contain multiple evidence IDs."""
        anchors = ["ev-001", "ev-002", "ev-003"]
        decision = _make_valid_decision(rationale_anchor=anchors)
        assert decision.rationale_anchor == anchors

    def test_audit_trail_with_multiple_ids(self):
        """audit_trail can contain a chain of evidence IDs."""
        trail = ["ev-001", "ev-002", "ev-003", "ev-004"]
        decision = _make_valid_decision(audit_trail=trail)
        assert decision.audit_trail == trail

    def test_multiple_trigger_conditions(self):
        """Multiple trigger conditions should be accepted."""
        triggers = ["rsi_below_30", "price_below_ma50", "volume_spike"]
        decision = _make_valid_decision(trigger_conditions=triggers)
        assert decision.trigger_conditions == triggers

    def test_multiple_invalidating_conditions(self):
        """Multiple invalidating conditions should be accepted."""
        invalids = ["stop_loss_hit", "fundamental_change", "regulatory_event"]
        decision = _make_valid_decision(invalidating_conditions=invalids)
        assert decision.invalidating_conditions == invalids

    def test_time_horizon_varied_values(self):
        """time_horizon accepts various horizon strings."""
        horizons = ["1D", "1W", "1M", "3M", "6M", "1Y", "2Y", "5Y"]
        for horizon in horizons:
            decision = _make_valid_decision(time_horizon=horizon)
            assert decision.time_horizon == horizon

    def test_roundtrip_to_dict_and_back(self):
        """Decision serialized to dict should contain all original data."""
        original = _make_valid_decision(
            decision_id="roundtrip-1",
            action="BUY",
            execution_amount=5000.0,
            rationale_anchor=["ev-001", "ev-002"],
            trigger_conditions=["signal_1"],
            invalidating_conditions=["signal_2"],
            time_horizon="3M",
            risk_budget=0.08,
            audit_trail=["ev-001", "ev-002"],
        )
        d = original.to_dict()
        # Verify all key fields survive serialization
        assert d["decision_id"] == original.decision_id
        assert d["action"] == original.action
        assert d["execution_amount"] == original.execution_amount
        assert d["rationale_anchor"] == original.rationale_anchor
        assert d["trigger_conditions"] == original.trigger_conditions
        assert d["invalidating_conditions"] == original.invalidating_conditions
        assert d["time_horizon"] == original.time_horizon
        assert d["risk_budget"] == original.risk_budget
        assert d["audit_trail"] == original.audit_trail
        assert d["version"] == original.version
