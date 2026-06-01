"""Decision support skill runtime.

This is the only runtime skill that may produce formal Decision and
ExecutionLedger artifacts. It consumes an already compiled EvidenceGraph from
the host agent and applies local, deterministic contract rules.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
import uuid

from src.schemas.decision import Decision, ExecutionLedger
from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillError, SkillInput, SkillOutput

ACTIVE_ACTIONS: frozenset[str] = frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})
PASSIVE_ACTIONS: frozenset[str] = frozenset({"WAIT", "HOLD", "PAUSE_DCA"})
ALL_ACTIONS: frozenset[str] = ACTIVE_ACTIONS | PASSIVE_ACTIONS


class DecisionSupportSkill:
    """Host-callable decision support skill."""

    mcp_adapter = None
    tool_registry = None

    def __init__(
        self,
        decision_engine: Any | None = None,
        ledger_builder: Any | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.ledger_builder = ledger_builder

    def run(self, skill_input: SkillInput) -> SkillOutput:
        try:
            if "evidence_graph" not in skill_input.payload:
                raise _SkillContractError(
                    code="INVALID_INPUT",
                    message="DecisionSupportSkill requires payload.evidence_graph",
                )

            graph = _graph_from_payload(skill_input.payload.get("evidence_graph"))
            requested_action = _normalized_action(
                skill_input.payload.get("requested_action")
            )
            if requested_action in ACTIVE_ACTIONS and not graph.items:
                raise _SkillContractError(
                    code="CONTRACT_VIOLATION",
                    message="Active decision requires at least one real evidence anchor",
                )

            task = _task_from_payload(skill_input.payload)
            critique = _critique_from_payload(skill_input.payload, graph)
            decision = _build_decision(
                payload=skill_input.payload,
                task=task,
                graph=graph,
                critique=critique,
                requested_action=requested_action,
            )
            ledger = ExecutionLedger(decisions=[decision])
            decision_payload = decision.to_dict()
            ledger_payload = ledger.to_dict()
            return SkillOutput(
                step_id=skill_input.step_id,
                skill_name=skill_input.skill_name,
                artifacts={
                    "decision": decision_payload,
                    "execution_ledger": ledger_payload,
                    "decision_status": decision.action,
                    "audit_trail": list(decision.audit_trail),
                },
                status="OK",
            )
        except Exception as exc:
            code = getattr(exc, "code", "INTERNAL_ERROR")
            return SkillOutput(
                step_id=skill_input.step_id,
                skill_name=skill_input.skill_name,
                errors=[
                    SkillError(
                        code=code,
                        message=str(exc),
                        details={
                            "error_type": type(exc).__name__,
                            "skill_name": skill_input.skill_name,
                        },
                        recoverable=code != "CONTRACT_VIOLATION",
                    ).to_dict()
                ],
                warnings=[str(exc)],
                status="FAILED",
            )


def _build_decision(
    *,
    payload: dict[str, Any],
    task: SimpleNamespace,
    graph: EvidenceGraph,
    critique: SimpleNamespace,
    requested_action: str | None,
) -> Decision:
    action = _determine_action(payload, graph, critique, requested_action)
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
    )
    invalidating_conditions = _build_invalidating_conditions(action)
    risk_budget = _calculate_risk_budget(payload, action)
    audit_trail = _build_audit_trail(
        graph=graph,
        critique=critique,
        amount_reason=amount_reason,
        downgraded_reason=downgraded_reason,
        insufficient_evidence=insufficient_evidence,
    )

    return Decision(
        decision_id=str(uuid.uuid4()),
        action=action,
        execution_amount=amount,
        rationale_anchor=anchors,
        trigger_conditions=trigger_conditions,
        invalidating_conditions=invalidating_conditions,
        time_horizon=task.time_horizon,
        risk_budget=risk_budget,
        audit_trail=audit_trail,
        created_at=datetime.now(),
    )


def _determine_action(
    payload: dict[str, Any],
    graph: EvidenceGraph,
    critique: SimpleNamespace,
    requested_action: str | None,
) -> str:
    if not graph.items:
        return "WAIT"

    if getattr(critique, "status", None) != "PASS":
        return "WAIT"

    if requested_action in ALL_ACTIONS:
        return requested_action

    positive = 0.0
    negative = 0.0
    for item in graph.items.values():
        direction = getattr(item, "direction", "neutral")
        weight = getattr(item, "confidence_weight", 1.0)
        if direction == "positive":
            positive += weight
        elif direction == "negative":
            negative += weight

    risk_level = _risk_level(payload.get("risk_profile"))
    if positive > negative * 1.5:
        return "INCREASE" if risk_level == "conservative" else "BUY"
    if negative > positive * 1.5:
        return "REDUCE" if risk_level == "aggressive" else "SELL"
    return "HOLD"


def _derive_execution_amount(
    action: str,
    payload: dict[str, Any],
) -> tuple[float, str]:
    if action in PASSIVE_ACTIONS:
        return 0.0, "passive action does not require execution amount"

    constraints = _dict(payload.get("constraints"))
    forbidden = {str(item).upper() for item in constraints.get("forbidden_actions", [])}
    if action in forbidden:
        return 0.0, f"{action} is forbidden by constraints"

    portfolio_context = _dict(payload.get("portfolio_context"))
    risk_profile = _dict(payload.get("risk_profile"))
    risk_budget = _dict(payload.get("risk_budget"))
    target_amount = _optional_float(payload.get("target_trade_amount"))
    has_budget_context = any(
        (
            portfolio_context,
            risk_profile,
            risk_budget,
            constraints,
            target_amount is not None,
        )
    )

    if not has_budget_context:
        return 10000.0, "default amount used because no portfolio budget context was provided"

    caps: list[float] = []
    total_value = _optional_float(portfolio_context.get("total_value"))
    max_trade_pct = _optional_float(
        risk_profile.get("max_trade_pct", risk_budget.get("max_trade_pct"))
    )
    if total_value is not None and max_trade_pct is not None:
        caps.append(total_value * max_trade_pct)

    if action in {"BUY", "INCREASE"}:
        cash_available = _optional_float(portfolio_context.get("cash_available"))
        if cash_available is not None:
            caps.append(cash_available)
        max_buy_amount = _optional_float(constraints.get("max_buy_amount"))
        if max_buy_amount is not None:
            caps.append(max_buy_amount)
    else:
        max_sell_amount = _optional_float(constraints.get("max_sell_amount"))
        if max_sell_amount is not None:
            caps.append(max_sell_amount)

    positive_caps = [cap for cap in caps if cap > 0]
    if target_amount is not None and target_amount > 0:
        amount = min([target_amount] + positive_caps) if positive_caps else target_amount
    elif positive_caps:
        amount = min(positive_caps)
    else:
        return 0.0, "missing usable trade budget cap"

    min_trade_amount = _optional_float(constraints.get("min_trade_amount")) or 0.0
    if amount < min_trade_amount:
        return 0.0, "derived execution amount is below min_trade_amount"

    return round(amount, 2), "execution amount derived from portfolio risk constraints"


def _graph_from_payload(payload: Any) -> EvidenceGraph:
    if isinstance(payload, EvidenceGraph):
        return payload

    graph = EvidenceGraph()
    if not isinstance(payload, dict):
        return graph

    raw_items = payload.get("items", {})
    if isinstance(raw_items, list):
        iterable = raw_items
    elif isinstance(raw_items, dict):
        iterable = raw_items.values()
    else:
        iterable = []

    for item_payload in iterable:
        if isinstance(item_payload, EvidenceItem):
            graph.add(item_payload)
        elif isinstance(item_payload, dict):
            graph.add(_evidence_item_from_dict(item_payload))

    for edge in payload.get("edges", []):
        if isinstance(edge, (list, tuple)) and len(edge) >= 3:
            graph.add_edge(str(edge[0]), str(edge[1]), str(edge[2]))
    return graph


def _evidence_item_from_dict(data: dict[str, Any]) -> EvidenceItem:
    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    elif timestamp is None:
        timestamp = datetime.now()
    return EvidenceItem(
        evidence_id=str(data.get("evidence_id", "")),
        evidence_type=data.get("evidence_type", "SoftEvidence"),
        source_type=str(data.get("source_type", "")),
        timestamp=timestamp,
        related_entities=list(data.get("related_entities", [])),
        claim=str(data.get("claim", "")),
        value=data.get("value"),
        confidence_weight=float(data.get("confidence_weight", 0.5)),
        direction=data.get("direction", "neutral"),
        provenance=dict(data.get("provenance", {})),
    )


def _task_from_payload(payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        objective=payload.get("objective", ""),
        portfolio_context=_dict(payload.get("portfolio_context")),
        risk_profile=payload.get("risk_profile", "moderate"),
        risk_budget=_dict(payload.get("risk_budget")),
        constraints=_dict(payload.get("constraints")),
        time_horizon=payload.get("time_horizon", "1 year"),
    )


def _critique_from_payload(payload: dict[str, Any], graph: EvidenceGraph) -> SimpleNamespace:
    status = payload.get("critique_status")
    if not status:
        status = "PASS" if graph.items else "EXHAUSTED"
    issues = payload.get("critique_issues")
    if issues is None and not graph.items:
        issues = ["insufficient evidence"]
    return SimpleNamespace(status=status, issues=list(issues or []))


def _extract_rationale_anchor(evidence_graph: EvidenceGraph) -> list[str]:
    if not evidence_graph.items:
        return []
    return list(evidence_graph.items.keys())[:10]


def _validate_anchor_membership(
    action: str,
    rationale_anchor: list[str],
    evidence_graph: EvidenceGraph,
) -> None:
    if action not in ACTIVE_ACTIONS:
        return
    missing = [
        anchor
        for anchor in rationale_anchor
        if anchor not in evidence_graph.items
    ]
    if missing or not rationale_anchor:
        raise ValueError(
            "Active decision rationale_anchor must reference real "
            f"EvidenceGraph evidence_id values, missing={missing}"
        )


def _build_trigger_conditions(
    *,
    action: str,
    amount_reason: str,
    insufficient_evidence: bool,
    downgraded_reason: str,
) -> list[str]:
    if insufficient_evidence:
        return ["Insufficient evidence to support an active decision"]

    conditions = [f"Critique status must be PASS for {action}"]
    if action in ACTIVE_ACTIONS:
        conditions.append("Evidence direction consensus confirmed")
        conditions.append(amount_reason)
    if downgraded_reason:
        conditions.append(downgraded_reason)
    return conditions


def _build_invalidating_conditions(action: str) -> list[str]:
    conditions = [
        "Evidence contradiction detected",
        "Risk budget exceeded",
    ]
    if action in ACTIVE_ACTIONS:
        conditions.append("Execution budget or liquidity constraint changes")
    return conditions


def _calculate_risk_budget(payload: dict[str, Any], action: str) -> float:
    risk_budget = _dict(payload.get("risk_budget"))
    explicit = _optional_float(risk_budget.get("risk_budget"))
    if explicit is not None and explicit > 0:
        return explicit

    risk_map = {
        "conservative": 0.02,
        "moderate": 0.05,
        "aggressive": 0.10,
    }
    base = risk_map.get(_risk_level(payload.get("risk_profile")), 0.05)
    return 0.01 if action in PASSIVE_ACTIONS else base


def _build_audit_trail(
    *,
    graph: EvidenceGraph,
    critique: SimpleNamespace,
    amount_reason: str,
    downgraded_reason: str,
    insufficient_evidence: bool,
) -> list[str]:
    trail: list[str] = []
    if graph.items:
        trail.append(f"Evidence items: {len(graph.items)}")
    elif insufficient_evidence:
        trail.append("Insufficient evidence: no evidence items available")

    status = getattr(critique, "status", "unknown")
    trail.append(f"Critique status: {status}")
    if status and status != "PASS":
        trail.append(f"Blocked by critic: {status}")
    issues = getattr(critique, "issues", [])
    trail.append(f"Issues: {len(issues)}")
    if amount_reason:
        trail.append(f"Execution amount: {amount_reason}")
    if downgraded_reason:
        trail.append(downgraded_reason)
    trail.append(f"Generated at: {datetime.now().isoformat()}")
    return trail


def _normalized_action(value: Any) -> str | None:
    if value is None:
        return None
    action = str(value).upper()
    return action if action in ALL_ACTIONS else None


def _risk_level(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("risk_level", "moderate"))
    if isinstance(value, str):
        return value
    return "moderate"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class _SkillContractError(ValueError):
    """Internal exception carrying a standard SkillError code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
