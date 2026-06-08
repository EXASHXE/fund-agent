"""Audit trail and deterministic ID/timestamp helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import hashlib

from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillInput

from .context import _dict


def _deterministic_timestamp(payload: dict[str, Any]) -> str:
    """Return a deterministic timestamp from payload, or fallback."""
    portfolio_context = _dict(payload.get("portfolio_context"))
    return (
        payload.get("as_of_date")
        or portfolio_context.get("as_of_date")
        or "2026-01-01T00:00:00"
    )


def _deterministic_decision_id(
    payload: dict[str, Any],
    skill_input: SkillInput | None = None,
    action: str = "",
    fund_code: str = "",
) -> str:
    """Compute a stable decision_id hash from stable fields."""
    task_id = payload.get("task_id", "")
    step_id = payload.get("step_id", "")
    if skill_input is not None:
        task_id = task_id or skill_input.task_id
        step_id = step_id or skill_input.step_id
    fields = [task_id, step_id, fund_code, action]
    hash_input = "|".join(str(f) for f in fields)
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def _build_audit_trail(
    *,
    graph: EvidenceGraph,
    critique_status: str,
    critique_issues: list[str],
    amount_reason: str,
    downgraded_reason: str,
    insufficient_evidence: bool,
    missing_evidence: str = "",
    deterministic_ts: str | None = None,
) -> list[str]:
    trail: list[str] = []
    if graph.items:
        trail.append(f"Evidence items: {len(graph.items)}")
    elif insufficient_evidence:
        trail.append("Insufficient evidence: no evidence items available")
    if missing_evidence:
        trail.append(f"Missing evidence: {missing_evidence}")

    status = critique_status or "unknown"
    trail.append(f"Critique status: {status}")
    if status and status != "PASS":
        trail.append(f"Blocked by critic: {status}")
    trail.append(f"Issues: {len(critique_issues)}")
    if amount_reason:
        trail.append(f"Execution amount: {amount_reason}")
    if downgraded_reason:
        trail.append(downgraded_reason)
    if deterministic_ts:
        trail.append(f"Generated at: {deterministic_ts}")
    else:
        trail.append(f"Generated at: {datetime.now().isoformat()}")
    return trail
