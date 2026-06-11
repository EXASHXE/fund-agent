"""decision_support gatekeeper regression tests."""

from __future__ import annotations

import json
from typing import Any

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill

from datetime import datetime


def _evidence_graph() -> dict[str, Any]:
    return {
        "items": {
            "ev-positive": {
                "evidence_id": "ev-positive",
                "evidence_type": "HardEvidence",
                "source_type": "quant_tool",
                "timestamp": "2026-01-01T00:00:00",
                "related_entities": ["fund:F001"],
                "claim": "Host-provided deterministic evidence supports review",
                "value": {"score": 1.0},
                "confidence_weight": 1.0,
                "direction": "positive",
                "provenance": {"tool": "test"},
            }
        },
        "edges": [],
    }


def _base_payload(requested_action: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "requested_action": requested_action,
        "target_trade_amount": 1000.0,
        "time_horizon": "1 year",
        "deterministic": True,
        "task_id": "gatekeeper-test",
        "step_id": "decision-support-gatekeeper",
        "objective": "test gatekeeper",
        "critique_status": "PASS",
        "portfolio_context": {"total_value": 100000.0, "cash_available": 20000.0},
        "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
        "risk_budget": {"risk_budget": 5000.0},
        "evidence_graph": _evidence_graph(),
    }
    payload.update(overrides)
    return payload


def _run(payload: dict[str, Any]):
    return DecisionSupportSkill().run(
        SkillInput(
            task_id="gatekeeper-test",
            step_id="decision-support",
            skill_name="decision_support",
            payload=payload,
        )
    )


def _decision(payload: dict[str, Any]) -> dict[str, Any]:
    output = _run(payload)
    assert output.status == "OK", output.errors
    return output.artifacts["decision"]


def test_missing_evidence_blocks_active_buy() -> None:
    payload = _base_payload("BUY", evidence_graph={"items": {}, "edges": []})

    decision = _decision(payload)

    assert decision["action"] in {"WAIT", "HOLD"}
    assert {"EVIDENCE_MISSING", "INSUFFICIENT_EVIDENCE"} & set(decision["decision_reason_codes"])
    assert "DOWNGRADED_ACTIVE_TO_HOLD" in decision["decision_reason_codes"]
    assert decision["blocked_by"]
    assert decision["rationale_anchor"] == []


def test_stale_evidence_blocks_active_buy_when_as_of_metadata_is_present() -> None:
    payload = _base_payload(
        "BUY",
        as_of_date="2026-12-31",
        max_evidence_age_days=30,
    )

    decision = _decision(payload)

    assert decision["action"] in {"WAIT", "HOLD"}
    assert "EVIDENCE_STALE" in decision["decision_reason_codes"]
    assert "evidence_freshness" in decision["blocked_by"]


def test_redemption_fee_blocker_downgrades_sell_reduce_trim() -> None:
    for requested_action in ("SELL", "REDUCE", "TRIM"):
        payload = _base_payload(
            requested_action,
            redemption_fee_risk={
                "has_blocker": True,
                "fee_items": [{"fund_code": "F001", "level": "blocker"}],
            },
        )

        decision = _decision(payload)

        assert decision["action"] in {"HOLD", "WAIT"}
        assert {"REDEMPTION_FEE_RISK", "FEE_LOCKUP"} & set(decision["decision_reason_codes"])
        assert "redemption_fee_blocker" in decision["blocked_by"]


def test_right_side_unconfirmed_blocks_add_buy() -> None:
    payload = _base_payload(
        "ADD",
        right_side_confirmation_diagnostics={
            "items": [
                {
                    "fund_code": "F001",
                    "applicability": "applicable",
                    "right_side_confirmed": False,
                    "evidence_state": "weak",
                }
            ],
            "summary": {"needs_more_evidence": True},
        },
    )

    decision = _decision(payload)

    assert decision["action"] in {"HOLD", "WAIT"}
    assert "RIGHT_SIDE_UNCONFIRMED" in decision["decision_reason_codes"]
    assert "right_side_unconfirmed" in decision["blocked_by"]


def test_event_hype_failed_blocks_event_driven_add_buy() -> None:
    payload = _base_payload(
        "BUY",
        event_hype_failure_diagnostics={
            "items": [{"fund_code": "F001", "hype_failed": True}],
            "summary": {"has_event_hype_failure": True, "high_risk_events": ["ASCO:F001"]},
        },
    )

    decision = _decision(payload)

    assert decision["action"] in {"HOLD", "WAIT"}
    assert "EVENT_HYPE_FAILED" in decision["decision_reason_codes"]
    assert "event_hype_failed" in decision["blocked_by"]


def test_cash_deployment_not_ready_blocks_add_buy() -> None:
    payload = _base_payload(
        "BUY",
        cash_deployment_diagnostics={
            "summary": {
                "deployment_readiness": "not_ready",
                "cash_buffer_status": "low",
            }
        },
    )

    decision = _decision(payload)

    assert decision["action"] in {"HOLD", "WAIT"}
    assert {"CASH_DEPLOYMENT_NOT_READY", "CASH_BUFFER_LOW"} <= set(decision["decision_reason_codes"])
    assert "cash_deployment_not_ready" in decision["blocked_by"]


def test_position_and_profit_artifacts_are_consumed_by_gatekeeper() -> None:
    payload = _base_payload(
        "BUY",
        position_contribution={
            "summary": {
                "high_weight_low_contribution_positions": ["F001"],
            },
            "positions": [{"fund_code": "F001"}],
        },
        profit_protection_diagnostics={
            "items": [
                {
                    "fund_code": "F001",
                    "profit_level": "high",
                    "suggested_analysis_action": "trim_review",
                }
            ],
            "summary": {},
        },
    )

    decision = _decision(payload)

    assert decision["action"] in {"HOLD", "WAIT"}
    assert "LOSS_CONTROL" in decision["decision_reason_codes"]
    assert "PROFIT_PROTECTION" in decision["decision_reason_codes"]
    assert "position_contribution_watchlist" in decision["blocked_by"]
    assert "profit_protection_review" in decision["blocked_by"]


def test_passive_watch_alias_remains_passive_with_structured_reason() -> None:
    payload = _base_payload("WATCH")

    decision = _decision(payload)

    assert decision["action"] == "HOLD"
    assert decision["execution_amount"] == 0.0
    assert "PASSIVE_ACTION" in decision["decision_reason_codes"]


def test_decision_support_output_has_no_order_execution_fields() -> None:
    decision = _decision(_base_payload("BUY"))
    rendered = json.dumps(decision).lower()

    for forbidden in ("place_order", "submit_order", "trade_execution_api"):
        assert forbidden not in rendered


def _graph_with_evidence(evidence_id: str = "ev-positive") -> EvidenceGraph:
    graph = EvidenceGraph()
    graph.add(
        EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=datetime.now(),
            related_entities=["fund:F001"],
            claim="Positive risk-adjusted return signal",
            value={"score": 1.0},
            confidence_weight=1.0,
            direction="positive",
            provenance={"tool": "test"},
        )
    )
    return graph


def _trade_plan_payload(trades: list[dict], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "objective": "trade plan gatekeeper test",
        "time_horizon": "medium_term",
        "deterministic": True,
        "task_id": "trade-plan-gatekeeper-test",
        "step_id": "decision-support-trade-plan-gatekeeper",
        "portfolio_context": {"total_value": 100000.0, "cash_available": 20000.0},
        "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
        "risk_budget": {"risk_budget": 5000.0},
        "evidence_graph": _graph_with_evidence().to_dict(),
        "trade_plan": {"suggested_trade_plan": trades},
        "selected_trade_ids": [t.get("trade_id", "") for t in trades],
    }
    payload.update(overrides)
    return payload


def _run_trade_plan(payload: dict[str, Any]):
    return DecisionSupportSkill().run(
        SkillInput(
            task_id="trade-plan-gatekeeper-test",
            step_id="decision-support",
            skill_name="decision_support",
            payload=payload,
        )
    )


def test_trade_plan_buy_blocked_by_right_side_unconfirmed_is_downgraded() -> None:
    graph = _graph_with_evidence()
    trade = {
        "trade_id": "trade-buy-rs",
        "fund_code": "F001",
        "action": "BUY",
        "amount": 5000.0,
        "evidence_refs": ["ev-positive"],
    }
    payload = _trade_plan_payload(
        [trade],
        evidence_graph=graph.to_dict(),
        right_side_confirmation_diagnostics={
            "items": [
                {
                    "fund_code": "F001",
                    "applicability": "applicable",
                    "right_side_confirmed": False,
                }
            ],
            "summary": {"needs_more_evidence": True},
        },
    )

    output = _run_trade_plan(payload)
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) >= 1
    decision = decisions[0]
    assert decision["action"] in {"HOLD", "WAIT"}
    assert "RIGHT_SIDE_UNCONFIRMED" in decision["decision_reason_codes"]
    assert "right_side_unconfirmed" in decision["blocked_by"]


def test_trade_plan_sell_blocked_by_redemption_fee_risk_is_downgraded() -> None:
    graph = _graph_with_evidence()
    trade = {
        "trade_id": "trade-sell-fee",
        "fund_code": "F001",
        "action": "SELL",
        "amount": 3000.0,
        "current_value": 30000.0,
        "evidence_refs": ["ev-positive"],
    }
    payload = _trade_plan_payload(
        [trade],
        evidence_graph=graph.to_dict(),
        redemption_fee_risk={
            "has_blocker": True,
            "fee_items": [{"fund_code": "F001", "level": "blocker"}],
        },
    )

    output = _run_trade_plan(payload)
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) >= 1
    decision = decisions[0]
    assert decision["action"] in {"HOLD", "WAIT"}
    assert "REDEMPTION_FEE_RISK" in decision["decision_reason_codes"]
    assert "redemption_fee_blocker" in decision["blocked_by"]


def test_trade_plan_decisions_include_reason_codes_and_blocked_by() -> None:
    graph = _graph_with_evidence()
    trade = {
        "trade_id": "trade-buy-1",
        "fund_code": "F001",
        "action": "BUY",
        "amount": 5000.0,
        "evidence_refs": ["ev-positive"],
    }
    payload = _trade_plan_payload(
        [trade],
        evidence_graph=graph.to_dict(),
        cash_deployment_diagnostics={
            "summary": {
                "deployment_readiness": "not_ready",
                "cash_buffer_status": "low",
            }
        },
    )

    output = _run_trade_plan(payload)
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) >= 1
    decision = decisions[0]
    assert isinstance(decision["decision_reason_codes"], list)
    assert len(decision["decision_reason_codes"]) > 0
    assert isinstance(decision["blocked_by"], list)
    assert len(decision["blocked_by"]) > 0
    assert "CASH_DEPLOYMENT_NOT_READY" in decision["decision_reason_codes"]
    assert "cash_deployment_not_ready" in decision["blocked_by"]
