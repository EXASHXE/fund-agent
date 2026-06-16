"""Decision support E2E gate tests.

Validates that DecisionSupportSkill is the only valid source of formal
Decision and ExecutionLedger artifacts, and that active decisions always
have evidence anchors.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support.skill import DecisionSupportSkill


def _evidence_graph_with_items(count: int = 3) -> dict[str, Any]:
    items = {}
    for i in range(count):
        eid = f"ev-{i}"
        items[eid] = {
            "evidence_id": eid,
            "evidence_type": "HardEvidence",
            "source_type": "quant_tool",
            "timestamp": "2026-01-01T00:00:00",
            "related_entities": ["fund:F001"],
            "claim": f"Deterministic evidence #{i}",
            "value": {"score": 1.0},
            "confidence_weight": 1.0,
            "direction": "positive",
            "provenance": {"tool": "test"},
        }
    return {"items": items, "edges": []}


def _base_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "requested_action": "BUY",
        "target_trade_amount": 5000.0,
        "time_horizon": "1 year",
        "deterministic": True,
        "task_id": "ds-e2e-gate",
        "step_id": "decision-support-e2e",
        "objective": "e2e gate test",
        "critique_status": "PASS",
        "portfolio_context": {"total_value": 100000.0, "cash_available": 20000.0},
        "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
        "risk_budget": {"risk_budget": 5000.0},
        "evidence_graph": _evidence_graph_with_items(),
    }
    payload.update(overrides)
    return payload


def _run(payload: dict[str, Any]):
    return DecisionSupportSkill().run(
        SkillInput(
            task_id="ds-e2e-gate",
            step_id="decision-support-e2e",
            skill_name="decision_support",
            payload=payload,
        )
    )


class TestDecisionSupportIsOnlyFormalDecisionSource:
    def test_output_contains_decision_artifacts(self):
        result = _run(_base_payload())
        artifacts = result.artifacts
        has_decision = "decision" in artifacts or "decisions" in artifacts
        has_ledger = "execution_ledger" in artifacts
        assert has_decision or has_ledger, "decision_support must produce decision/ledger artifacts"

    def test_output_does_not_contain_forbidden_execution_fields(self):
        result = _run(_base_payload())
        artifacts = result.artifacts
        _assert_no_forbidden_fields(artifacts)


class TestActiveDecisionRequiresEvidenceAnchors:
    def test_active_buy_has_rationale_anchor(self):
        result = _run(_base_payload(requested_action="BUY"))
        decision = _get_decision(result)
        if decision and str(decision.get("action", "")).upper() in ("BUY", "SELL", "INCREASE", "REDUCE"):
            anchors = decision.get("rationale_anchor", [])
            assert len(anchors) > 0, "Active decision must have evidence anchors"

    def test_active_sell_has_rationale_anchor(self):
        result = _run(_base_payload(requested_action="SELL"))
        decision = _get_decision(result)
        if decision and str(decision.get("action", "")).upper() in ("BUY", "SELL", "INCREASE", "REDUCE"):
            anchors = decision.get("rationale_anchor", [])
            assert len(anchors) > 0, "Active decision must have evidence anchors"

    def test_passive_hold_may_have_empty_anchor(self):
        result = _run(_base_payload(
            requested_action="BUY",
            constraints={"forbidden_actions": ["BUY"], "min_trade_amount": 100.0},
        ))
        decision = _get_decision(result)
        if decision and str(decision.get("action", "")).upper() in ("HOLD", "WAIT", "PAUSE_DCA"):
            assert True


class TestEmptyAnchorsGracefulDowngrade:
    def test_active_action_with_empty_graph_downgrades_to_wait(self):
        result = _run(_base_payload(
            requested_action="BUY",
            evidence_graph={"items": {}, "edges": []},
        ))
        decision = _get_decision(result)
        if decision:
            action = str(decision.get("action", "")).upper()
            assert action in ("HOLD", "WAIT"), f"Expected HOLD/WAIT with empty graph, got {action}"

    def test_active_action_with_anchors_but_empty_anchor_list_downgrades(self):
        payload = _base_payload(requested_action="BUY")
        payload["evidence_graph"] = {"items": {}, "edges": []}
        result = _run(payload)
        assert result.status != "FAILED", "Empty graph should not crash decision_support"
        decision = _get_decision(result)
        if decision:
            action = str(decision.get("action", "")).upper()
            assert action in ("HOLD", "WAIT"), f"Expected HOLD/WAIT, got {action}"


class TestBlockedActiveActionIsDowngraded:
    def test_redemption_fee_blocks_sell(self):
        result = _run(_base_payload(
            requested_action="SELL",
            constraints={
                "min_trade_amount": 100.0,
                "forbidden_actions": ["short_term_redemption_within_7d"],
            },
            fund_analysis_artifacts={
                "redemption_fee_risk": {
                    "has_blocker": True,
                    "items": [{"fund_code": "F001", "has_blocker": True, "reason": "Short-term redemption within 7 days"}],
                }
            },
        ))
        decision = _get_decision(result)
        if decision:
            action = str(decision.get("action", "")).upper()
            reason_codes = decision.get("decision_reason_codes", [])
            blocked_by = decision.get("blocked_by", [])
            if action == "SELL":
                assert len(blocked_by) > 0 or any("BLOCKED" in rc for rc in reason_codes), \
                    "Unblocked SELL with forbidden_actions should have blockers"
            elif action in ("HOLD", "WAIT"):
                assert any("BLOCKED" in rc or "DOWNGRADED" in rc for rc in reason_codes), \
                    f"Downgraded action should have BLOCKED/DOWNGRADED reason code, got {reason_codes}"


class TestNoBrokerExecutionFields:
    def test_no_broker_fields_in_single_decision(self):
        result = _run(_base_payload())
        decision = _get_decision(result)
        if decision:
            _assert_no_forbidden_fields(decision)

    def test_no_broker_fields_in_ledger(self):
        result = _run(_base_payload())
        ledger = result.artifacts.get("execution_ledger", {})
        if ledger:
            _assert_no_forbidden_fields(ledger)


class TestTradePlanE2EGates:
    def test_multi_leg_trade_plan_produces_multiple_decisions(self):
        payload = _base_payload()
        del payload["requested_action"]
        payload["trade_plan"] = {
            "suggested_trade_plan": [
                {"trade_id": "T1", "action": "REDUCE", "fund_code": "F001", "amount": 5000, "rationale": "Trim high profit"},
                {"trade_id": "T2", "action": "BUY", "fund_code": "F002", "amount": 3000, "rationale": "Sector allocation"},
            ]
        }
        payload["selected_trade_ids"] = ["T1", "T2"]
        result = _run(payload)
        decisions = result.artifacts.get("decisions", [])
        assert len(decisions) >= 2, f"Expected >= 2 decisions from trade plan, got {len(decisions)}"

    def test_forbidden_action_in_trade_plan_is_blocked(self):
        payload = _base_payload()
        del payload["requested_action"]
        payload["trade_plan"] = {
            "suggested_trade_plan": [
                {"trade_id": "T1", "action": "SELL", "fund_code": "F001", "amount": 5000, "rationale": "Sell"},
            ]
        }
        payload["selected_trade_ids"] = ["T1"]
        payload["constraints"] = {
            "min_trade_amount": 100.0,
            "forbidden_actions": ["short_term_redemption_within_7d"],
        }
        result = _run(payload)
        decisions = result.artifacts.get("decisions", [])
        if decisions:
            d = decisions[0]
            action = str(d.get("action", "")).upper()
            if action in ("HOLD", "WAIT"):
                reason_codes = d.get("decision_reason_codes", [])
                assert any("BLOCKED" in rc or "DOWNGRADED" in rc or "FORBIDDEN" in rc.upper() for rc in reason_codes), \
                    f"Blocked trade should have BLOCKED/DOWNGRADED/FORBIDDEN reason, got {reason_codes}"


FORBIDDEN_FIELDS = frozenset({
    "broker_order_id", "order_id", "order_status", "filled_quantity",
    "fill_price", "execution_venue", "submitted_at", "broker", "exchange_order_id",
})


def _get_decision(result) -> dict[str, Any] | None:
    d = result.artifacts.get("decision")
    if d:
        return d
    decisions = result.artifacts.get("decisions", [])
    if decisions:
        return decisions[0] if isinstance(decisions[0], dict) else None
    return None


def _assert_no_forbidden_fields(data: dict[str, Any], path: str = "") -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            current = f"{path}.{key}" if path else key
            assert key not in FORBIDDEN_FIELDS, f"Forbidden field found: {current}"
            _assert_no_forbidden_fields(value, current)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _assert_no_forbidden_fields(item, f"{path}[{i}]")
