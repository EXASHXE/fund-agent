"""Evidence anchor diagnostics for decision_support.

Produces a deterministic artifact explaining why evidence anchors are
missing, invalid, weak, or insufficient. Does not weaken anchor enforcement.
Active BUY/SELL/INCREASE/REDUCE still require real EvidenceGraph anchors.
"""
from __future__ import annotations

from typing import Any

from src.schemas.evidence_graph import EvidenceGraph

from .action_policy import ACTIVE_ACTIONS, PASSIVE_ACTIONS
from .graph_stage import _resolve_trade_evidence_anchors


def build_evidence_anchor_diagnostics(
    *,
    action: str,
    evidence_graph: EvidenceGraph,
    rationale_anchor: list[str],
    trade_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_action_requires_anchor = action in ACTIVE_ACTIONS

    anchor_count = len(rationale_anchor)
    missing_anchor_refs: list[str] = []
    invalid_anchor_refs: list[str] = []
    valid_anchor_refs: list[str] = []

    for ref in rationale_anchor:
        if ref not in evidence_graph.items:
            invalid_anchor_refs.append(ref)
        else:
            valid_anchor_refs.append(ref)

    if active_action_requires_anchor and not rationale_anchor:
        missing_anchor_refs.append("_no_anchors_provided")

    trade_anchor_coverage = _build_trade_anchor_coverage(
        trade_plan=trade_plan,
        evidence_graph=evidence_graph,
    )

    anchor_entity_mismatch = _find_entity_mismatches(
        rationale_anchor=rationale_anchor,
        evidence_graph=evidence_graph,
    )

    limitations: list[str] = []
    if active_action_requires_anchor and not valid_anchor_refs:
        limitations.append("Active action has no valid evidence anchors")
    if invalid_anchor_refs:
        limitations.append(f"{len(invalid_anchor_refs)} anchor ref(s) not found in evidence graph")
    if not active_action_requires_anchor and not rationale_anchor:
        limitations.append("Passive action with no anchors; evidence_state explains blockage")

    trade_plan_has_active_actions = False
    trade_plan_requires_anchor = False
    if trade_plan:
        for trade in trade_plan:
            if not isinstance(trade, dict):
                continue
            trade_action = str(trade.get("action", "")).upper()
            if trade_action in ACTIVE_ACTIONS:
                trade_plan_has_active_actions = True
                trade_plan_requires_anchor = True
                break

    return {
        "active_action_requires_anchor": active_action_requires_anchor,
        "anchor_count": anchor_count,
        "missing_anchor_refs": missing_anchor_refs,
        "invalid_anchor_refs": invalid_anchor_refs,
        "valid_anchor_refs": valid_anchor_refs,
        "trade_anchor_coverage": trade_anchor_coverage,
        "anchor_entity_mismatch": anchor_entity_mismatch,
        "limitations": limitations,
        "trade_plan_has_active_actions": trade_plan_has_active_actions,
        "trade_plan_requires_anchor": trade_plan_requires_anchor,
    }


def _build_trade_anchor_coverage(
    *,
    trade_plan: list[dict[str, Any]] | None,
    evidence_graph: EvidenceGraph,
) -> list[dict[str, Any]]:
    if not trade_plan:
        return []

    coverage_list = []
    for trade in trade_plan:
        if not isinstance(trade, dict):
            continue
        trade_id = str(trade.get("trade_id", trade.get("fund_code", "")))
        action = str(trade.get("action", "")).upper()
        required = action in ACTIVE_ACTIONS

        provided_refs = list(trade.get("evidence_refs", []))
        risk_refs = list(trade.get("risk_flags_refs", []))
        all_requested = provided_refs + risk_refs

        valid_refs = [r for r in all_requested if r in evidence_graph.items]
        invalid_refs = [r for r in all_requested if r not in evidence_graph.items]

        if not all_requested:
            coverage = "none"
        elif len(valid_refs) == len(all_requested):
            coverage = "full"
        elif valid_refs:
            coverage = "partial"
        else:
            coverage = "none"

        coverage_list.append({
            "trade_id": trade_id,
            "action": action,
            "required": required,
            "provided_refs": provided_refs,
            "valid_refs": valid_refs,
            "invalid_refs": invalid_refs,
            "coverage": coverage,
        })

    return coverage_list


def _find_entity_mismatches(
    *,
    rationale_anchor: list[str],
    evidence_graph: EvidenceGraph,
) -> list[dict[str, Any]]:
    mismatches = []
    for ref in rationale_anchor:
        item = evidence_graph.items.get(ref)
        if item and not item.related_entities:
            mismatches.append({
                "anchor_ref": ref,
                "issue": "evidence item has no related_entities",
            })
    return mismatches
