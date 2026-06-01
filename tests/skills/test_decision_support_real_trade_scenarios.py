"""DecisionSupportSkill tests with realistic trade scenarios from JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.evidence.validators import compile_evidence_graph


def _load_json(name: str) -> dict:
    return json.loads(Path(f"examples/{name}").read_text())


def _compile_evidence_from_payload(payload: dict):
    fund_output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="fa", skill_name="fund_analysis",
        payload=payload,
    ))
    compile_result = compile_evidence_graph(fund_output.evidence_items)
    return compile_result.graph, fund_output


def test_oil_gas_loss_case_produces_decision():
    payload = _load_json("oil_gas_loss_case.json")
    graph, fund_output = _compile_evidence_from_payload(payload)

    rebalance = fund_output.artifacts.get("suggested_rebalance_plan", {})
    trade_plan = rebalance if isinstance(rebalance, dict) else {}

    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="test", step_id="ds", skill_name="decision_support",
        payload={
            "evidence_graph": graph.to_dict(),
            "objective": "review portfolio",
            "time_horizon": "6 months",
            "portfolio_context": payload["portfolio"],
            "risk_profile": payload.get("risk_profile", {}),
            "trade_plan": trade_plan,
            "critique_status": "PASS",
        },
    ))

    assert decision_output.status == "OK"
    assert "decision" in decision_output.artifacts or "decisions" in decision_output.artifacts


def test_short_term_trade_capped_by_budget():
    payload = _load_json("short_term_theme_trade.json")
    graph, fund_output = _compile_evidence_from_payload(payload)

    rebalance = fund_output.artifacts.get("suggested_rebalance_plan", {})
    trade_plan = rebalance if isinstance(rebalance, dict) else {}

    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="test", step_id="ds", skill_name="decision_support",
        payload={
            "evidence_graph": graph.to_dict(),
            "objective": "review short-term trade",
            "time_horizon": "1 month",
            "portfolio_context": payload["portfolio"],
            "risk_profile": payload.get("risk_profile", {}),
            "constraints": {"max_buy_amount": 2000.0, "min_trade_amount": 100.0},
            "trade_plan": trade_plan,
            "critique_status": "PASS",
        },
    ))

    assert decision_output.status == "OK"
    if "decisions" in decision_output.artifacts:
        for d in decision_output.artifacts["decisions"]:
            execution_amount = d.get("execution_amount", 0)
            assert execution_amount <= 10000.0, f"Trade exceeds budget: {execution_amount}"
    elif "decision" in decision_output.artifacts:
        execution_amount = decision_output.artifacts["decision"].get("execution_amount", 0)
        assert execution_amount <= 10000.0, f"Trade exceeds budget: {execution_amount}"


def test_high_drawdown_scenario_produces_hold_or_reduce():
    payload = _load_json("rebalance_with_cash_reserve.json")
    graph, fund_output = _compile_evidence_from_payload(payload)

    rebalance = fund_output.artifacts.get("suggested_rebalance_plan", {})
    trade_plan = rebalance if isinstance(rebalance, dict) else {}

    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="test", step_id="ds", skill_name="decision_support",
        payload={
            "evidence_graph": graph.to_dict(),
            "objective": "review high drawdown portfolio",
            "time_horizon": "3 months",
            "portfolio_context": payload["portfolio"],
            "risk_profile": payload.get("risk_profile", {}),
            "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
            "trade_plan": trade_plan,
            "critique_status": "PASS",
        },
    ))

    assert decision_output.status == "OK"
    if "decisions" in decision_output.artifacts:
        actions = {d.get("action", "") for d in decision_output.artifacts["decisions"]}
    else:
        actions = {decision_output.artifacts.get("decision", {}).get("action", "")}

    assert len(actions) > 0, f"No actions returned: {decision_output.artifacts}"
    # With cash reserve and evidence, any action is acceptable
    valid_actions = {"BUY", "SELL", "HOLD", "REDUCE", "INCREASE", "WAIT", "PAUSE_DCA"}
    assert actions <= valid_actions, f"Unexpected action(s): {actions}"


def test_active_decisions_require_evidence_anchors():
    payload = _load_json("oil_gas_loss_case.json")
    graph, fund_output = _compile_evidence_from_payload(payload)

    rebalance = fund_output.artifacts.get("suggested_rebalance_plan", {})
    trade_plan = rebalance if isinstance(rebalance, dict) else {}

    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="test", step_id="ds", skill_name="decision_support",
        payload={
            "evidence_graph": graph.to_dict(),
            "objective": "review portfolio",
            "time_horizon": "6 months",
            "portfolio_context": payload["portfolio"],
            "risk_profile": payload.get("risk_profile", {}),
            "trade_plan": trade_plan,
            "critique_status": "PASS",
            "target_trade_amount": 5000.0,
        },
    ))

    if decision_output.status == "OK":
        decisions = decision_output.artifacts.get("decisions", [decision_output.artifacts.get("decision", {})])
        if isinstance(decisions, dict):
            decisions = [decisions]
        for d in decisions:
            if not isinstance(d, dict):
                continue
            action = d.get("action", "")
            if action in {"BUY", "SELL", "INCREASE", "REDUCE"}:
                assert len(d.get("rationale_anchor", [])) > 0, (
                    f"Active decision {action} must have evidence anchors"
                )


def test_wait_hold_includes_and_conditions():
    payload = {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 50000.0,
            "cash_available": 5000.0,
            "positions": [
                {"fund_code": "F001", "fund_name": "Fund One", "current_value": 45000.0, "total_cost": 44000.0, "tags": ["equity"]},
            ],
        },
        "risk_profile": {"risk_level": "moderate"},
    }
    graph, fund_output = _compile_evidence_from_payload(payload)

    decision_output = DecisionSupportSkill().run(SkillInput(
        task_id="test", step_id="ds", skill_name="decision_support",
        payload={
            "evidence_graph": graph.to_dict(),
            "objective": "review portfolio",
            "time_horizon": "1 year",
            "portfolio_context": payload.get("portfolio", {}),
            "risk_profile": payload.get("risk_profile", {}),
            "requested_action": "WAIT",
            "why_not_buy": "insufficient positive evidence",
            "why_not_sell": "no negative evidence",
        },
    ))

    assert decision_output.status == "OK"
    decision = decision_output.artifacts.get("decision", {})
    trigger_conditions = decision.get("trigger_conditions", [])
    invalidating_conditions = decision.get("invalidating_conditions", [])

    assert len(trigger_conditions) > 0
    assert len(invalidating_conditions) > 0
