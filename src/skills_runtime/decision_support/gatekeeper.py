"""Fund-scenario-aware decision gatekeeping.

This module reads only JSON-like payload dictionaries and EvidenceGraph state.
It does not import fund_analysis runtime types, fetch data, or execute actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.schemas.evidence_graph import EvidenceGraph

from .action_policy import ACTIVE_ACTIONS, PASSIVE_ACTIONS
from .context import _dict
from .reason_codes import (
    ACTIVE_ACTION_ALLOWED,
    BENCHMARK_DIVERGENCE,
    BUDGET_BLOCKED,
    CASH_BUFFER_LOW,
    CASH_DEPLOYMENT_NOT_READY,
    CONSTRAINT_BLOCKED,
    DOWNGRADED_ACTIVE_TO_HOLD,
    EVENT_HYPE_FAILED,
    EVIDENCE_AVAILABLE,
    EVIDENCE_CONTRADICTORY,
    EVIDENCE_MISSING,
    EVIDENCE_SUFFICIENT,
    EVIDENCE_WEAK,
    FEE_LOCKUP,
    INSUFFICIENT_EVIDENCE,
    LOSS_CONTROL,
    PASSIVE_ACTION,
    PROFIT_PROTECTION,
    REDEMPTION_FEE_RISK,
    RIGHT_SIDE_UNCONFIRMED,
    RISK_PROFILE_MISSING,
    TRANSACTION_HISTORY_MISSING,
    USER_CONSTRAINT_MISSING,
)

BUY_SIDE_ACTIONS = frozenset({"BUY", "INCREASE"})
SELL_SIDE_ACTIONS = frozenset({"SELL", "REDUCE"})


@dataclass
class GatekeeperResult:
    """Structured gatekeeper result merged into formal Decisions."""

    action: str
    downgraded: bool = False
    reason_codes: list[str] = field(default_factory=list)
    evidence_state: str = "ANCHORED"
    blocked_by: list[str] = field(default_factory=list)
    trigger_conditions: list[str] = field(default_factory=list)
    invalidating_conditions: list[str] = field(default_factory=list)
    audit_trail: list[str] = field(default_factory=list)


def evaluate_gatekeeper(
    *,
    payload: dict[str, Any],
    graph: EvidenceGraph,
    action: str,
) -> GatekeeperResult:
    """Evaluate evidence/artifact blockers before a formal action is emitted."""

    result = GatekeeperResult(action=action)
    _apply_evidence_state(result, graph, action)
    _apply_artifact_blockers(result, payload, action)

    if action in PASSIVE_ACTIONS:
        result.reason_codes.append(PASSIVE_ACTION)

    has_blocker = bool(result.blocked_by)
    if action in ACTIVE_ACTIONS and has_blocker:
        result.action = "HOLD" if graph.items else "WAIT"
        result.downgraded = True
        result.reason_codes.extend([DOWNGRADED_ACTIVE_TO_HOLD, PASSIVE_ACTION])
        if result.evidence_state == "ANCHORED":
            result.evidence_state = "DOWNGRADED"
        result.trigger_conditions.append(
            "Active action downgraded until decision_support gatekeeper blockers clear"
        )
        result.audit_trail.append(
            f"Gatekeeper downgraded {action} to {result.action}: "
            f"{', '.join(result.blocked_by)}"
        )
    elif action in ACTIVE_ACTIONS and not has_blocker and graph.items:
        result.reason_codes.append(ACTIVE_ACTION_ALLOWED)

    result.reason_codes = _dedupe(result.reason_codes)
    result.blocked_by = _dedupe(result.blocked_by)
    result.trigger_conditions = _dedupe(result.trigger_conditions)
    result.invalidating_conditions = _dedupe(result.invalidating_conditions)
    result.audit_trail = _dedupe(result.audit_trail)
    return result


def _apply_evidence_state(
    result: GatekeeperResult,
    graph: EvidenceGraph,
    action: str,
) -> None:
    if not graph.items:
        result.evidence_state = "INSUFFICIENT_EVIDENCE"
        result.reason_codes.extend([EVIDENCE_MISSING, INSUFFICIENT_EVIDENCE])
        result.blocked_by.append("evidence")
        result.trigger_conditions.append("No EvidenceGraph items are available")
        result.invalidating_conditions.append("Fresh relevant evidence becomes available")
        result.audit_trail.append("Gatekeeper recorded missing evidence: evidence graph is empty")
        return

    conflicts = graph.find_conflicts()
    if conflicts:
        result.evidence_state = "CONSTRAINT_BLOCKED"
        result.reason_codes.extend([EVIDENCE_CONTRADICTORY, CONSTRAINT_BLOCKED])
        result.blocked_by.append("evidence_conflict")
        result.trigger_conditions.append("Resolve contradictory evidence before active action")
        result.invalidating_conditions.append("Contradictory evidence remains unresolved")
        result.audit_trail.append(f"Gatekeeper detected contradictory evidence pairs: {len(conflicts)}")
        return

    weights = [
        float(getattr(item, "confidence_weight", 0.0) or 0.0)
        for item in graph.items.values()
    ]
    if weights and max(weights) < 0.4:
        result.evidence_state = "INSUFFICIENT_EVIDENCE"
        result.reason_codes.extend([EVIDENCE_WEAK, INSUFFICIENT_EVIDENCE])
        result.blocked_by.append("evidence_quality")
        result.trigger_conditions.append("Evidence confidence must improve before active action")
        result.invalidating_conditions.append("Evidence confidence remains weak")
    else:
        result.evidence_state = "ANCHORED"
        result.reason_codes.extend([EVIDENCE_AVAILABLE, EVIDENCE_SUFFICIENT])

    if action in PASSIVE_ACTIONS and result.evidence_state == "ANCHORED":
        result.trigger_conditions.append("Passive action requested despite available evidence")


def _apply_artifact_blockers(
    result: GatekeeperResult,
    payload: dict[str, Any],
    action: str,
) -> None:
    analysis_plan = _artifact(payload, "analysis_plan")
    evidence_gap = _artifact(payload, "evidence_gap_diagnostics")

    blockers = _strings(analysis_plan.get("blockers"))
    for blocker in blockers:
        _apply_named_blocker(result, blocker, action)

    if evidence_gap.get("missing_recent_news"):
        _add_blocker(
            result,
            codes=[EVIDENCE_MISSING, INSUFFICIENT_EVIDENCE],
            blocked_by="missing_recent_news",
            trigger="Recent fund or theme news evidence is required before active action",
            invalidating="Recent news evidence remains missing",
            evidence_state="INSUFFICIENT_EVIDENCE",
        )
    if evidence_gap.get("missing_user_constraints"):
        _add_blocker(
            result,
            codes=[USER_CONSTRAINT_MISSING, CONSTRAINT_BLOCKED],
            blocked_by="user_constraints",
            trigger="User constraints must be supplied before active action",
            invalidating="Liquidity or forbidden-action constraints remain missing",
            evidence_state="CONSTRAINT_BLOCKED",
        )
    if evidence_gap.get("missing_risk_preference"):
        _add_blocker(
            result,
            codes=[RISK_PROFILE_MISSING, CONSTRAINT_BLOCKED],
            blocked_by="risk_profile",
            trigger="Risk preference must be supplied before active action",
            invalidating="Risk preference remains missing",
            evidence_state="CONSTRAINT_BLOCKED",
        )
    if action in SELL_SIDE_ACTIONS and evidence_gap.get("missing_transaction_history"):
        _add_blocker(
            result,
            codes=[TRANSACTION_HISTORY_MISSING, INSUFFICIENT_EVIDENCE],
            blocked_by="transaction_history",
            trigger="Transaction history is needed before fee-sensitive sell/reduce",
            invalidating="Transaction history remains missing",
            evidence_state="INSUFFICIENT_EVIDENCE",
        )

    _apply_redemption_fee(result, _artifact(payload, "redemption_fee_risk"), action)
    _apply_position_contribution(result, _artifact(payload, "position_contribution"), action)
    _apply_profit_protection(result, _artifact(payload, "profit_protection_diagnostics"), action)
    _apply_right_side(result, _artifact(payload, "right_side_confirmation_diagnostics"), action)
    _apply_event_hype(result, _artifact(payload, "event_hype_failure_diagnostics"), action)
    _apply_cash_deployment(result, _artifact(payload, "cash_deployment_diagnostics"), action)
    _apply_benchmark(result, _artifact(payload, "benchmark_divergence_diagnostics"), action)


def _apply_named_blocker(result: GatekeeperResult, blocker: str, action: str) -> None:
    blocker = str(blocker)
    if blocker == "redemption_fee_blocker" and action in SELL_SIDE_ACTIONS:
        _add_blocker(
            result,
            codes=[REDEMPTION_FEE_RISK, FEE_LOCKUP, CONSTRAINT_BLOCKED],
            blocked_by="redemption_fee_blocker",
            trigger="Review after minimum holding period or fee window",
            invalidating="Short-holding redemption fee blocker remains active",
            evidence_state="CONSTRAINT_BLOCKED",
        )
    elif blocker == "right_side_unconfirmed" and action in BUY_SIDE_ACTIONS:
        _add_blocker(
            result,
            codes=[RIGHT_SIDE_UNCONFIRMED, INSUFFICIENT_EVIDENCE],
            blocked_by="right_side_unconfirmed",
            trigger="Fresh NAV, benchmark, news, and sentiment confirmation is required",
            invalidating="Right-side confirmation remains unconfirmed",
            evidence_state="INSUFFICIENT_EVIDENCE",
        )
    elif blocker == "event_hype_failed" and action in BUY_SIDE_ACTIONS:
        _add_blocker(
            result,
            codes=[EVENT_HYPE_FAILED, CONSTRAINT_BLOCKED],
            blocked_by="event_hype_failed",
            trigger="Event-driven add/buy requires post-event price action to recover",
            invalidating="Post-event price action remains weak despite positive catalyst",
            evidence_state="CONSTRAINT_BLOCKED",
        )
    elif blocker == "cash_deployment_not_ready" and action in BUY_SIDE_ACTIONS:
        _add_blocker(
            result,
            codes=[CASH_DEPLOYMENT_NOT_READY, BUDGET_BLOCKED],
            blocked_by="cash_deployment_not_ready",
            trigger="Confirm liquidity need and target cash buffer before deploying cash",
            invalidating="Cash deployment readiness remains not ready",
            evidence_state="BUDGET_BLOCKED",
        )


def _apply_redemption_fee(
    result: GatekeeperResult,
    redemption: dict[str, Any],
    action: str,
) -> None:
    if action not in SELL_SIDE_ACTIONS or not redemption.get("has_blocker"):
        return
    _add_blocker(
        result,
        codes=[REDEMPTION_FEE_RISK, FEE_LOCKUP, CONSTRAINT_BLOCKED],
        blocked_by="redemption_fee_blocker",
        trigger="Review after minimum holding period or redemption fee window",
        invalidating="Redemption fee blocker remains active",
        evidence_state="CONSTRAINT_BLOCKED",
    )


def _apply_right_side(
    result: GatekeeperResult,
    right_side: dict[str, Any],
    action: str,
) -> None:
    if action not in BUY_SIDE_ACTIONS:
        return
    for item in _list_dicts(right_side.get("items")):
        if item.get("applicability") == "not_applicable":
            continue
        if item.get("right_side_confirmed") is False:
            _add_blocker(
                result,
                codes=[RIGHT_SIDE_UNCONFIRMED, INSUFFICIENT_EVIDENCE],
                blocked_by="right_side_unconfirmed",
                trigger="Fresh NAV, benchmark, news, and sentiment confirmation is required",
                invalidating="Right-side confirmation remains unconfirmed",
                evidence_state="INSUFFICIENT_EVIDENCE",
            )
            return


def _apply_position_contribution(
    result: GatekeeperResult,
    contribution: dict[str, Any],
    action: str,
) -> None:
    if action not in BUY_SIDE_ACTIONS:
        return
    summary = _dict(contribution.get("summary"))
    low_contribution = _strings(summary.get("high_weight_low_contribution_positions"))
    if not low_contribution:
        return
    _add_blocker(
        result,
        codes=[LOSS_CONTROL, CONSTRAINT_BLOCKED],
        blocked_by="position_contribution_watchlist",
        trigger="Resolve high-weight low-contribution positions before add/buy",
        invalidating="High-weight low-contribution watchlist remains active",
        evidence_state="CONSTRAINT_BLOCKED",
    )


def _apply_profit_protection(
    result: GatekeeperResult,
    diagnostics: dict[str, Any],
    action: str,
) -> None:
    items = _list_dicts(diagnostics.get("items"))
    if not items:
        return

    has_profit_review = any(
        str(item.get("profit_level", "")) in {"high", "very_high"}
        or str(item.get("suggested_analysis_action", "")) in {"trim_review", "watch"}
        for item in items
    )
    if not has_profit_review:
        return

    result.reason_codes.append(PROFIT_PROTECTION)
    result.audit_trail.append("Gatekeeper reviewed profit protection diagnostics")
    if action in BUY_SIDE_ACTIONS:
        _add_blocker(
            result,
            codes=[PROFIT_PROTECTION, CONSTRAINT_BLOCKED],
            blocked_by="profit_protection_review",
            trigger="Resolve profit-protection watch/trim review before add/buy",
            invalidating="Profit-protection review remains active",
            evidence_state="CONSTRAINT_BLOCKED",
        )


def _apply_event_hype(
    result: GatekeeperResult,
    event_hype: dict[str, Any],
    action: str,
) -> None:
    if action not in BUY_SIDE_ACTIONS:
        return
    summary = _dict(event_hype.get("summary"))
    has_failure = bool(summary.get("has_event_hype_failure"))
    if not has_failure:
        has_failure = any(item.get("hype_failed") is True for item in _list_dicts(event_hype.get("items")))
    if not has_failure:
        return
    _add_blocker(
        result,
        codes=[EVENT_HYPE_FAILED, CONSTRAINT_BLOCKED],
        blocked_by="event_hype_failed",
        trigger="Event-driven add/buy requires post-event price action to recover",
        invalidating="Post-event price action remains weak despite positive catalyst",
        evidence_state="CONSTRAINT_BLOCKED",
    )


def _apply_cash_deployment(
    result: GatekeeperResult,
    cash_deployment: dict[str, Any],
    action: str,
) -> None:
    if action not in BUY_SIDE_ACTIONS:
        return
    summary = _dict(cash_deployment.get("summary"))
    readiness = str(summary.get("deployment_readiness", "") or "").lower()
    cash_status = str(summary.get("cash_buffer_status", "") or "").lower()
    if readiness in {"not_ready", "unknown"}:
        _add_blocker(
            result,
            codes=[CASH_DEPLOYMENT_NOT_READY, BUDGET_BLOCKED],
            blocked_by="cash_deployment_not_ready",
            trigger="Confirm liquidity need and target cash buffer before deploying cash",
            invalidating="Cash deployment readiness remains not ready",
            evidence_state="BUDGET_BLOCKED",
        )
    if cash_status == "low":
        _add_blocker(
            result,
            codes=[CASH_BUFFER_LOW, BUDGET_BLOCKED],
            blocked_by="cash_buffer_low",
            trigger="Cash buffer should be restored before add/buy",
            invalidating="Cash buffer remains low",
            evidence_state="BUDGET_BLOCKED",
        )


def _apply_benchmark(
    result: GatekeeperResult,
    benchmark: dict[str, Any],
    action: str,
) -> None:
    if action not in BUY_SIDE_ACTIONS:
        return
    summary = _dict(benchmark.get("summary"))
    if summary.get("has_severe_underperformance"):
        _add_blocker(
            result,
            codes=[BENCHMARK_DIVERGENCE, CONSTRAINT_BLOCKED],
            blocked_by="benchmark_divergence",
            trigger="Benchmark-relative underperformance should improve before add/buy",
            invalidating="Severe benchmark underperformance remains",
            evidence_state="CONSTRAINT_BLOCKED",
        )


def _add_blocker(
    result: GatekeeperResult,
    *,
    codes: list[str],
    blocked_by: str,
    trigger: str,
    invalidating: str,
    evidence_state: str,
) -> None:
    result.reason_codes.extend(codes)
    result.blocked_by.append(blocked_by)
    result.trigger_conditions.append(trigger)
    result.invalidating_conditions.append(invalidating)
    result.audit_trail.append(f"Gatekeeper blocker: {blocked_by}")
    if result.evidence_state == "ANCHORED" or evidence_state in {"BUDGET_BLOCKED", "CONSTRAINT_BLOCKED"}:
        result.evidence_state = evidence_state


def _artifact(payload: dict[str, Any], key: str) -> dict[str, Any]:
    sources = [
        payload,
        _dict(payload.get("artifacts")),
        _dict(payload.get("fund_analysis_artifacts")),
        _dict(payload.get("fund_analysis")),
    ]
    for source in sources:
        value = source.get(key)
        if isinstance(value, dict):
            return value
    report = _dict(_dict(payload.get("artifacts")).get("fund_analysis_report"))
    value = report.get(key)
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        return [value]
    return []


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dedupe(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result
