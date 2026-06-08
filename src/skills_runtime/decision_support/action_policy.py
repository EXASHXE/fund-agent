"""Action policy for decision support.

Defines active/passive action sets and action determination logic.
"""

from __future__ import annotations

from typing import Any

from src.schemas.evidence_graph import EvidenceGraph

from .context import _dict

ACTIVE_ACTIONS: frozenset[str] = frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})
PASSIVE_ACTIONS: frozenset[str] = frozenset({"WAIT", "HOLD", "PAUSE_DCA"})
ALL_ACTIONS: frozenset[str] = ACTIVE_ACTIONS | PASSIVE_ACTIONS


def _risk_level(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("risk_level", "moderate"))
    if isinstance(value, str):
        return value
    return "moderate"


def _normalized_action(value: Any) -> str | None:
    if value is None:
        return None
    action = str(value).upper()
    return action if action in ALL_ACTIONS else None


def _determine_action(
    payload: dict[str, Any],
    graph: EvidenceGraph,
    critique_status: str | None,
    requested_action: str | None,
) -> str:
    if not graph.items:
        return "WAIT"

    if critique_status != "PASS":
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
