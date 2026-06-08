"""Stage-level unit tests for the decision_support pipeline package."""

from __future__ import annotations

from datetime import datetime

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillInput

from src.skills_runtime.decision_support.action_policy import (
    ACTIVE_ACTIONS,
    PASSIVE_ACTIONS,
    _normalized_action,
)
from src.skills_runtime.decision_support.graph_stage import (
    _graph_from_payload,
    _resolve_trade_evidence_anchors,
)
from src.skills_runtime.decision_support.amount_policy import (
    _validate_trade_amount,
)
from src.skills_runtime.decision_support.trade_plan_stage import (
    validate_and_filter_trades,
)
from src.skills_runtime.decision_support.decision_stage import (
    _build_decision,
)
from src.skills_runtime.decision_support.status_stage import (
    _SkillContractError,
    build_failed_output,
)
from src.skills_runtime.decision_support import DecisionSupportSkill


def _pos_graph(ev_id: str = "ev-1") -> EvidenceGraph:
    graph = EvidenceGraph()
    graph.add(
        EvidenceItem(
            evidence_id=ev_id,
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=datetime.now(),
            related_entities=["fund:TEST"],
            claim="positive signal",
            value={"score": 1.0},
            confidence_weight=1.0,
            direction="positive",
            provenance={"tool": "quant_tool"},
        )
    )
    return graph


class TestActionPolicy:
    def test_active_actions_set(self):
        assert ACTIVE_ACTIONS == frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})

    def test_passive_actions_set(self):
        assert PASSIVE_ACTIONS == frozenset({"WAIT", "HOLD", "PAUSE_DCA"})

    def test_norm_action_lowercase(self):
        assert _normalized_action("buy") == "BUY"

    def test_norm_action_invalid(self):
        assert _normalized_action("invalid_action") is None

    def test_norm_action_none(self):
        assert _normalized_action(None) is None


class TestGraphStage:
    def test_parse_minimal_evidence_graph(self):
        payload = {
            "items": {
                "ev-1": {
                    "evidence_id": "ev-1",
                    "evidence_type": "HardEvidence",
                    "source_type": "quant_tool",
                    "timestamp": "2026-01-01T00:00:00",
                    "related_entities": ["fund:TEST"],
                    "claim": "test claim",
                    "value": {"score": 1.0},
                    "confidence_weight": 1.0,
                    "direction": "positive",
                    "version": "evidence-contract.v2",
                    "provenance": {"tool": "quant_tool"},
                }
            },
            "edges": [],
        }
        graph = _graph_from_payload(payload)
        assert bool(graph.items)
        assert "ev-1" in graph.items

    def test_parse_empty_evidence_graph(self):
        payload = {"items": {}, "edges": []}
        graph = _graph_from_payload(payload)
        assert not bool(graph.items)

    def test_parse_list_items(self):
        payload = {
            "items": [
                {
                    "evidence_id": "ev-list",
                    "evidence_type": "HardEvidence",
                    "source_type": "quant_tool",
                    "timestamp": "2026-01-01T00:00:00",
                    "related_entities": ["fund:TEST"],
                    "claim": "list item claim",
                    "value": {"score": 1.0},
                    "confidence_weight": 1.0,
                    "direction": "positive",
                    "version": "evidence-contract.v2",
                }
            ],
            "edges": [],
        }
        graph = _graph_from_payload(payload)
        assert "ev-list" in graph.items

    def test_resolve_anchors_with_valid_evidence_refs(self):
        graph = _pos_graph("ev-1")
        trade = {"action": "BUY", "evidence_refs": ["ev-1"], "risk_flags_refs": []}
        anchors = _resolve_trade_evidence_anchors(trade, graph, "BUY")
        assert anchors == ["ev-1"]

    def test_resolve_anchors_with_fake_refs_returns_empty(self):
        graph = _pos_graph("ev-1")
        trade = {"action": "BUY", "evidence_refs": ["fake-id"], "risk_flags_refs": []}
        anchors = _resolve_trade_evidence_anchors(trade, graph, "BUY")
        assert anchors == []

    def test_resolve_anchors_for_passive_action(self):
        graph = _pos_graph("ev-1")
        trade = {"action": "HOLD", "evidence_refs": ["fake-id"]}
        anchors = _resolve_trade_evidence_anchors(trade, graph, "HOLD")
        assert "ev-1" in anchors


class TestAmountPolicy:
    def test_caps_buy_by_max_buy_amount(self):
        trade = {"action": "BUY", "amount": 10000.0, "fund_code": "F001"}
        pc = {"total_value": 100000.0, "cash_available": 50000.0}
        rp = {"max_trade_pct": 0.1, "liquidity_reserve_pct": 0.1}
        constraints = {"max_buy_amount": 5000.0, "min_trade_amount": 100.0}
        capped, reasons, valid = _validate_trade_amount(
            trade=trade, portfolio_context=pc, risk_profile=rp, constraints=constraints,
        )
        assert valid
        assert capped <= 5000.0
        assert any("max_buy_amount" in r for r in reasons)

    def test_rejects_trade_below_min_trade_amount(self):
        trade = {"action": "BUY", "amount": 50.0, "fund_code": "F001"}
        pc = {"total_value": 100000.0, "cash_available": 50000.0}
        rp = {"max_trade_pct": 0.1}
        constraints = {"min_trade_amount": 100.0}
        _, reasons, valid = _validate_trade_amount(
            trade=trade, portfolio_context=pc, risk_profile=rp, constraints=constraints,
        )
        assert not valid
        assert any("below min_trade_amount" in r for r in reasons)

    def test_rejects_zero_amount_trade(self):
        trade = {"action": "BUY", "amount": 0.0, "fund_code": "F001"}
        pc = {"total_value": 100000.0}
        rp = {}
        constraints = {}
        _, reasons, valid = _validate_trade_amount(
            trade=trade, portfolio_context=pc, risk_profile=rp, constraints=constraints,
        )
        assert not valid


class TestTradePlanStage:
    def test_skips_forbidden_action(self):
        graph = _pos_graph("ev-1")
        trades = [{"trade_id": "t1", "fund_code": "F001", "action": "SELL", "amount": 5000.0, "evidence_refs": ["ev-1"]}]
        validated, warnings = validate_and_filter_trades(
            trades=trades, selected_trade_ids=["t1"], graph=graph,
            portfolio_context={}, risk_profile={}, constraints={"forbidden_actions": ["SELL"]},
            is_short_term=False, has_real_evidence=True,
        )
        assert len(validated) == 0
        assert any("Forbidden" in w for w in warnings)

    def test_downgrades_active_trade_without_evidence(self):
        graph = EvidenceGraph()
        trades = [{"trade_id": "t1", "fund_code": "F001", "action": "BUY", "amount": 5000.0}]
        validated, warnings = validate_and_filter_trades(
            trades=trades, selected_trade_ids=["t1"], graph=graph,
            portfolio_context={}, risk_profile={}, constraints={},
            is_short_term=False, has_real_evidence=False,
        )
        assert len(validated) == 1
        assert validated[0]["action"] == "HOLD"


class TestStatusStage:
    def test_skill_contract_error(self):
        exc = _SkillContractError("TEST_CODE", "test message")
        assert exc.code == "TEST_CODE"
        assert str(exc) == "test message"

    def test_build_failed_output(self):
        from src.schemas.skill import SkillInput

        exc = _SkillContractError("CONTRACT_VIOLATION", "test failure")
        si = SkillInput(task_id="t", step_id="s", skill_name="test", payload={})
        output = build_failed_output(si, exc)
        assert output.status == "FAILED"
        assert output.errors[0]["code"] == "CONTRACT_VIOLATION"


class TestDecisionStage:
    def test_builds_decision_with_rationale_anchor(self):
        graph = _pos_graph("ev-1")
        payload = {"evidence_graph": graph.to_dict(), "objective": "test", "time_horizon": "1 year"}
        decision = _build_decision(
            payload=payload, task=type("T", (), {"time_horizon": "1 year"})(),
            graph=graph, critique_status="PASS", critique_issues=[],
            requested_action=None, skill_input=None,
        )
        assert decision.action in {"BUY", "INCREASE"}
        assert "ev-1" in decision.rationale_anchor
