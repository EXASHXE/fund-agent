"""Formal Decision construction from payload evidence, task, and critique."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
import uuid

from src.schemas.decision import Decision
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillInput

from .action_policy import (
    ACTIVE_ACTIONS,
    ALL_ACTIONS,
    PASSIVE_ACTIONS,
    _determine_action,
    _normalized_action,
    _risk_level,
)
from .amount_policy import _calculate_risk_budget, _derive_execution_amount
from .audit_stage import (
    _build_audit_trail,
    _deterministic_decision_id,
    _deterministic_timestamp,
)
from .context import _dict
from .graph_stage import _extract_rationale_anchor, _validate_anchor_membership


def _task_from_payload(payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        objective=payload.get("objective", ""),
        portfolio_context=_dict(payload.get("portfolio_context")),
        risk_profile=payload.get("risk_profile", "moderate"),
        risk_budget=_dict(payload.get("risk_budget")),
        constraints=_dict(payload.get("constraints")),
        time_horizon=payload.get("time_horizon", "1 year"),
    )


def _critique_from_payload(payload: dict[str, Any], graph: EvidenceGraph) -> tuple[str, list[str]]:
    status = payload.get("critique_status")
    if not status:
        status = "PASS" if graph.items else "EXHAUSTED"
    issues = payload.get("critique_issues")
    if issues is None and not graph.items:
        issues = ["insufficient evidence"]
    return str(status or ""), list(issues or [])


def _build_trigger_conditions(
    *,
    action: str,
    amount_reason: str,
    insufficient_evidence: bool,
    downgraded_reason: str,
    payload: dict[str, Any] | None = None,
) -> list[str]:
    if insufficient_evidence:
        return ["Insufficient evidence to support an active decision"]

    conditions = [f"Critique status must be PASS for {action}"]
    if action in ACTIVE_ACTIONS:
        conditions.append("Evidence direction consensus confirmed")
        conditions.append(amount_reason)
    else:
        payload = payload or {}
        why_not_buy = payload.get("why_not_buy", "")
        if why_not_buy:
            conditions.append(f"Why not buy: {why_not_buy}")
        why_not_sell = payload.get("why_not_sell", "")
        if why_not_sell:
            conditions.append(f"Why not sell: {why_not_sell}")
        trigger_to_change = payload.get("trigger_to_change", "")
        if trigger_to_change:
            conditions.append(f"Trigger to change: {trigger_to_change}")
    if downgraded_reason:
        conditions.append(downgraded_reason)
    return conditions


def _build_invalidating_conditions(
    action: str,
    payload: dict[str, Any] | None = None,
) -> list[str]:
    conditions = [
        "Evidence contradiction detected",
        "Risk budget exceeded",
    ]
    if action in ACTIVE_ACTIONS:
        conditions.append("Execution budget or liquidity constraint changes")
    else:
        payload = payload or {}
        what_invalidates = payload.get("what_invalidates", "")
        if what_invalidates:
            conditions.append(f"What invalidates: {what_invalidates}")
        conditions.append("Market regime change")
    return conditions


def _build_decision(
    *,
    payload: dict[str, Any],
    task: SimpleNamespace,
    graph: EvidenceGraph,
    critique_status: str,
    critique_issues: list[str],
    requested_action: str | None,
    skill_input: SkillInput | None = None,
) -> Decision:
    action = _determine_action(payload, graph, critique_status, requested_action)
    anchors = _extract_rationale_anchor(graph)
    _validate_anchor_membership(action, anchors, graph)

    amount, amount_reason = _derive_execution_amount(action, payload)
    downgraded_reason = ""
    if action in ACTIVE_ACTIONS and amount <= 0:
        action = "HOLD" if anchors else "WAIT"
        downgraded_reason = (
            "Insufficient evidence or budget context to derive a safe "
            "execution amount"
        )
        amount = 0.0

    insufficient_evidence = not anchors
    trigger_conditions = _build_trigger_conditions(
        action=action,
        amount_reason=amount_reason,
        insufficient_evidence=insufficient_evidence,
        downgraded_reason=downgraded_reason,
        payload=payload,
    )
    invalidating_conditions = _build_invalidating_conditions(
        action, payload=payload
    )
    risk_budget = _calculate_risk_budget(payload, action)
    missing_evidence = payload.get("missing_evidence", "") if action in PASSIVE_ACTIONS else ""

    deterministic = bool(payload.get("deterministic"))
    deterministic_ts = _deterministic_timestamp(payload) if deterministic else None
    decision_id = (
        _deterministic_decision_id(payload, skill_input, action)
        if deterministic
        else str(uuid.uuid4())
    )
    created_at = (
        datetime.fromisoformat(deterministic_ts)
        if deterministic and deterministic_ts
        else datetime.now()
    )

    audit_trail = _build_audit_trail(
        graph=graph,
        critique_status=critique_status,
        critique_issues=critique_issues,
        amount_reason=amount_reason,
        downgraded_reason=downgraded_reason,
        insufficient_evidence=insufficient_evidence,
        missing_evidence=missing_evidence,
        deterministic_ts=deterministic_ts,
    )

    return Decision(
        decision_id=decision_id,
        action=action,
        execution_amount=amount,
        rationale_anchor=anchors,
        trigger_conditions=trigger_conditions,
        invalidating_conditions=invalidating_conditions,
        time_horizon=task.time_horizon,
        risk_budget=risk_budget,
        audit_trail=audit_trail,
        created_at=created_at,
    )
