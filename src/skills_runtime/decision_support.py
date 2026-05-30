"""Decision support skill runtime.

This is the only runtime skill that may produce formal Decision and
ExecutionLedger artifacts. It consumes an already compiled EvidenceGraph from
the host agent and delegates contract enforcement to DecisionEngine.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from src.core.decision_engine import ACTIVE_ACTIONS, DecisionEngine
from src.core.ledger import LedgerBuilder
from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillError, SkillInput, SkillOutput


class DecisionSupportSkill:
    """Host-callable decision support skill."""

    mcp_adapter = None
    tool_registry = None

    def __init__(
        self,
        decision_engine: DecisionEngine | None = None,
        ledger_builder: LedgerBuilder | None = None,
    ) -> None:
        self.decision_engine = decision_engine or DecisionEngine()
        self.ledger_builder = ledger_builder or LedgerBuilder()

    def run(self, skill_input: SkillInput) -> SkillOutput:
        try:
            if "evidence_graph" not in skill_input.payload:
                raise _SkillContractError(
                    code="INVALID_INPUT",
                    message="DecisionSupportSkill requires payload.evidence_graph",
                )
            graph = _graph_from_payload(skill_input.payload.get("evidence_graph"))
            requested_action = skill_input.payload.get("requested_action")
            if requested_action in ACTIVE_ACTIONS and not graph.items:
                raise _SkillContractError(
                    code="CONTRACT_VIOLATION",
                    message="Active decision requires at least one real evidence anchor",
                )

            task = _task_from_payload(skill_input.payload)
            critique = _critique_from_payload(skill_input.payload, graph)
            decision = self.decision_engine.decide(task, graph, critique)
            ledger = self.ledger_builder.build(decision, graph)
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
        constraints=payload.get("portfolio_context", {}),
        risk_profile=payload.get("risk_profile", "moderate"),
        risk_budget=payload.get("risk_budget", {}),
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


class _SkillContractError(ValueError):
    """Internal exception carrying a standard SkillError code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
