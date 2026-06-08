"""Trade plan validation and decision generation from trade legs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from src.schemas.decision import Decision
from src.schemas.evidence_graph import EvidenceGraph

from .action_policy import ACTIVE_ACTIONS, PASSIVE_ACTIONS, _normalized_action
from .amount_policy import _calculate_risk_budget, _validate_trade_amount
from .audit_stage import _deterministic_decision_id, _deterministic_timestamp
from .context import _dict, _float_value, _optional_float
from .graph_stage import _resolve_trade_evidence_anchors


def validate_and_filter_trades(
    *,
    trades: list[dict[str, Any]],
    selected_trade_ids: list[str],
    graph: EvidenceGraph,
    portfolio_context: dict[str, Any],
    risk_profile: dict[str, Any],
    constraints: dict[str, Any],
    is_short_term: bool,
    has_real_evidence: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate and filter trades, returning validated trades and warnings."""
    validated_trades: list[dict[str, Any]] = []
    output_warnings: list[str] = []

    for trade in trades:
        if not isinstance(trade, dict):
            continue

        if selected_trade_ids:
            trade_id = trade.get("trade_id", "")
            if trade_id not in selected_trade_ids:
                continue

        action = str(trade.get("action", "")).upper()

        forbidden_actions = [
            str(item).upper()
            for item in constraints.get("forbidden_actions", [])
        ]
        if action in forbidden_actions:
            output_warnings.append(
                f"Forbidden action {action} for {trade.get('fund_code', trade.get('trade_id', 'unknown'))} skipped"
            )
            continue

        if action in ACTIVE_ACTIONS and not has_real_evidence:
            trade = dict(trade)
            trade["action"] = "HOLD"
            trade["why_not_buy"] = "No real evidence anchor available to support active decision"
            trade["why_not_sell"] = "No real evidence anchor available"
            trade["missing_evidence"] = "No evidence items in evidence graph"
            trade["trigger_to_change"] = "New evidence becomes available"
            trade["what_invalidates"] = "Any new evidence contradicts current assessment"
            trade["decision_reason_codes"] = [
                "INSUFFICIENT_EVIDENCE",
                "DOWNGRADED_ACTIVE_TO_HOLD",
                "PASSIVE_ACTION",
            ]
            trade["evidence_state"] = "INSUFFICIENT_EVIDENCE"
            trade["blocked_by"] = ["evidence"]
            action = "HOLD"

        if action in ACTIVE_ACTIONS:
            trade = dict(trade)
            capped_amount, cap_reasons, is_valid = _validate_trade_amount(
                trade=trade,
                portfolio_context=portfolio_context,
                risk_profile=risk_profile,
                constraints=constraints,
                is_short_term=is_short_term,
            )
            if not is_valid:
                output_warnings.append(
                    f"Trade {trade.get('trade_id', trade.get('fund_code', 'unknown'))} invalid after amount validation: {cap_reasons}"
                )
                continue
            trade["amount"] = capped_amount
            trade["capped"] = capped_amount < _float_value(
                trade.get("requested_amount"), 0.0
            )
            trade["cap_reasons"] = cap_reasons

        validated_trades.append(trade)

    return validated_trades, output_warnings


def select_top_trades(
    validated_trades: list[dict[str, Any]],
    selected_trade_ids: list[str],
) -> list[dict[str, Any]]:
    """Select top trades when no explicit selection, sorting by priority/rank."""
    if selected_trade_ids or not validated_trades:
        return validated_trades
    validated_trades.sort(
        key=lambda t: t.get("priority", t.get("rank", 999))
    )
    return validated_trades[:1]


def _dedupe_reason_codes(*groups: Any) -> list[str]:
    reason_codes: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if isinstance(group, str):
            values = [group]
        else:
            values = list(group or [])
        for value in values:
            code = str(value)
            if code and code not in seen:
                reason_codes.append(code)
                seen.add(code)
    return reason_codes


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [str(item) for item in list(value or []) if str(item)]


def _trade_decision_justification(
    *,
    trade: dict[str, Any],
    action: str,
    anchors: list[str],
) -> tuple[list[str], str, list[str]]:
    reason_codes: list[str] = []
    blocked_by: list[str] = []

    if anchors:
        reason_codes.append("EVIDENCE_AVAILABLE")
        evidence_state = "ANCHORED"
    else:
        reason_codes.append("INSUFFICIENT_EVIDENCE")
        evidence_state = "INSUFFICIENT_EVIDENCE"
        blocked_by.append("evidence")

    if action in PASSIVE_ACTIONS:
        reason_codes.append("PASSIVE_ACTION")

    evidence_state = str(trade.get("evidence_state") or evidence_state)
    blocked_by = _list_strings(trade.get("blocked_by")) or blocked_by
    reason_codes = _dedupe_reason_codes(
        reason_codes,
        trade.get("decision_reason_codes"),
    )
    return reason_codes, evidence_state, blocked_by


def _decision_from_trade(
    trade: dict[str, Any],
    evidence_graph: EvidenceGraph,
    payload: dict[str, Any],
) -> Decision:
    """Build a formal Decision from a single trade leg."""
    action = _normalized_action(trade.get("action", "HOLD")) or "HOLD"
    amount = _optional_float(trade.get("amount")) or 0.0

    anchors = _resolve_trade_evidence_anchors(trade, evidence_graph, action)

    if action in ACTIVE_ACTIONS and not anchors:
        action = "HOLD"
        amount = 0.0
        trigger_conditions = [
            "Downgraded to HOLD: no valid trade-specific evidence anchors in evidence graph"
        ]
        invalidating_conditions = [
            "Evidence contradiction detected",
            "Market regime change",
        ]
        audit_trail = [
            "Trade ID: " + (trade.get("trade_id", "")),
            "Insufficient evidence: evidence_refs and risk_flags_refs contained no valid evidence IDs",
        ]

        deterministic = bool(payload.get("deterministic"))
        deterministic_ts = _deterministic_timestamp(payload) if deterministic else None
        if deterministic_ts:
            audit_trail.append(f"Generated at: {deterministic_ts}")
            created_at = datetime.fromisoformat(deterministic_ts)
        else:
            audit_trail.append(f"Generated at: {datetime.now().isoformat()}")
            created_at = datetime.now()

        decision_id = (
            _deterministic_decision_id(payload, None, action, trade.get("fund_code", ""))
            if deterministic
            else str(uuid.uuid4())
        )

        return Decision(
            decision_id=decision_id,
            action=action,
            execution_amount=amount,
            rationale_anchor=[],
            trigger_conditions=trigger_conditions,
            invalidating_conditions=invalidating_conditions,
            time_horizon=trade.get("time_horizon", payload.get("time_horizon", "medium_term")),
            risk_budget=0.01,
            audit_trail=audit_trail,
            decision_reason_codes=[
                "INSUFFICIENT_EVIDENCE",
                "DOWNGRADED_ACTIVE_TO_HOLD",
                "PASSIVE_ACTION",
            ],
            evidence_state="DOWNGRADED",
            blocked_by=["evidence"],
            created_at=created_at,
        )

    trigger_conditions: list[str] = []
    rationale = trade.get("rationale", "")
    if rationale:
        trigger_conditions.append(f"Trade rationale: {rationale}")
    market_scenario = trade.get("market_scenario", "")
    if market_scenario:
        trigger_conditions.append(f"Market scenario: {market_scenario}")
    risk_flags = trade.get("risk_flags", [])
    if isinstance(risk_flags, list):
        for flag in risk_flags:
            trigger_conditions.append(f"Risk flag: {flag}")
    elif risk_flags:
        trigger_conditions.append(f"Risk flags: {risk_flags}")

    if action in PASSIVE_ACTIONS:
        why_not_buy = trade.get("why_not_buy", payload.get("why_not_buy", ""))
        if why_not_buy:
            trigger_conditions.append(f"Why not buy: {why_not_buy}")
        why_not_sell = trade.get("why_not_sell", payload.get("why_not_sell", ""))
        if why_not_sell:
            trigger_conditions.append(f"Why not sell: {why_not_sell}")
        trigger_to_change = trade.get(
            "trigger_to_change", payload.get("trigger_to_change", "")
        )
        if trigger_to_change:
            trigger_conditions.append(f"Trigger to change: {trigger_to_change}")

    if not trigger_conditions:
        trigger_conditions.append(
            f"Trade execution triggered: {action} {trade.get('fund_code', '')}"
        )

    invalidating_conditions = [
        "Evidence contradiction detected",
        "Market regime change",
        "Risk budget exceeded",
    ]
    if action in PASSIVE_ACTIONS:
        what_invalidates = trade.get(
            "what_invalidates", payload.get("what_invalidates", "")
        )
        if what_invalidates:
            invalidating_conditions.append(f"What invalidates: {what_invalidates}")

    time_horizon = trade.get(
        "time_horizon", payload.get("time_horizon", "medium_term")
    )

    portfolio_context = _dict(payload.get("portfolio_context"))
    total_value = _optional_float(portfolio_context.get("total_value"))
    risk_profile = _dict(payload.get("risk_profile"))
    risk_budget_dict = _dict(payload.get("risk_budget"))
    max_trade_pct = _optional_float(
        risk_profile.get("max_trade_pct", risk_budget_dict.get("max_trade_pct"))
    ) or 0.05
    if total_value and total_value > 0 and amount > 0:
        trade_pct = amount / total_value
        risk_budget = round(min(trade_pct, max_trade_pct), 4)
    else:
        risk_budget = _calculate_risk_budget(payload, action)

    audit_trail: list[str] = []
    trade_id = trade.get("trade_id", "")
    if trade_id:
        audit_trail.append(f"Trade ID: {trade_id}")
    if rationale:
        audit_trail.append(f"Rationale: {rationale}")
    if market_scenario:
        audit_trail.append(f"Market scenario: {market_scenario}")
    if action in PASSIVE_ACTIONS:
        missing_evidence = trade.get(
            "missing_evidence", payload.get("missing_evidence", "")
        )
        if missing_evidence:
            audit_trail.append(f"Missing evidence: {missing_evidence}")
        if not evidence_graph.items:
            audit_trail.append("Insufficient evidence: no evidence items in graph")

    deterministic = bool(payload.get("deterministic"))
    deterministic_ts = _deterministic_timestamp(payload) if deterministic else None
    if deterministic_ts:
        audit_trail.append(f"Generated at: {deterministic_ts}")
    else:
        audit_trail.append(f"Generated at: {datetime.now().isoformat()}")

    decision_id = (
        _deterministic_decision_id(payload, None, action, trade.get("fund_code", ""))
        if deterministic
        else str(uuid.uuid4())
    )
    created_at = (
        datetime.fromisoformat(deterministic_ts)
        if deterministic and deterministic_ts
        else datetime.now()
    )
    decision_reason_codes, evidence_state, blocked_by = _trade_decision_justification(
        trade=trade,
        action=action,
        anchors=anchors,
    )

    return Decision(
        decision_id=decision_id,
        action=action,
        execution_amount=amount,
        rationale_anchor=anchors,
        trigger_conditions=trigger_conditions,
        invalidating_conditions=invalidating_conditions,
        time_horizon=time_horizon,
        risk_budget=risk_budget,
        audit_trail=audit_trail,
        decision_reason_codes=decision_reason_codes,
        evidence_state=evidence_state,
        blocked_by=blocked_by,
        created_at=created_at,
    )
