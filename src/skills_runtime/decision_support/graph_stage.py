"""EvidenceGraph parsing and evidence anchor helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph

from .action_policy import ACTIVE_ACTIONS


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


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


def _resolve_trade_evidence_anchors(
    trade: dict[str, Any],
    evidence_graph: EvidenceGraph,
    current_action: str,
) -> list[str]:
    """Resolve evidence anchors for a trade leg.

    For active actions (BUY/SELL/INCREASE/REDUCE), anchors must come from
    trade-specific evidence_refs or risk_flags_refs that exist in the
    evidence graph. If neither provides valid anchors, the trade is
    downgraded to HOLD and the anchor list is left empty with structured
    downgrade justification.

    For passive actions, any available evidence is accepted.
    """
    if current_action not in ACTIVE_ACTIONS:
        return list(evidence_graph.items.keys())[:3]

    evidence_refs = trade.get("evidence_refs", [])
    risk_flags_refs = trade.get("risk_flags_refs", [])

    valid_evidence = [
        ref for ref in (_safe_list(evidence_refs))
        if ref in evidence_graph.items
    ]
    valid_risk = [
        ref for ref in (_safe_list(risk_flags_refs))
        if ref in evidence_graph.items
    ]

    if valid_evidence:
        return valid_evidence
    if valid_risk:
        return valid_risk

    return []
