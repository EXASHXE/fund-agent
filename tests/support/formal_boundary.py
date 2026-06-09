"""Formal decision boundary assertion helpers for tests.

Provides shared constants and assertion functions for verifying that
formal decision boundaries are respected across test layers.

These helpers must not import provider SDKs or perform network calls.
They should not mask behavior changes; tests should still assert
explicit semantics.
"""

from __future__ import annotations

from typing import Any


FORMAL_DECISION_ARTIFACT_KEYS = {"decision", "decisions", "execution_ledger", "execution_ledgers"}

ACTIVE_ACTIONS = {"BUY", "SELL", "INCREASE", "REDUCE"}

PASSIVE_ACTIONS = {"WAIT", "HOLD", "PAUSE_DCA"}

EMPTY_ANCHOR_STATES = {
    "INSUFFICIENT_EVIDENCE",
    "CRITIC_BLOCKED",
    "CONSTRAINT_BLOCKED",
    "BUDGET_BLOCKED",
    "DOWNGRADED",
}

EMPTY_ANCHOR_REASON_CODES = {
    "INSUFFICIENT_EVIDENCE",
    "CRITIC_BLOCKED",
    "CONSTRAINT_BLOCKED",
    "BUDGET_BLOCKED",
    "DOWNGRADED_ACTIVE_TO_HOLD",
}

FAKE_ANCHORS = {
    "no_evidence_available",
    "fake_anchor",
    "fake-anchor",
    "placeholder",
    "missing_evidence",
    "missing-evidence",
}


def assert_no_formal_decision_artifacts(artifacts: dict[str, Any]) -> None:
    """Assert that artifacts contain no formal decision/ledger keys."""
    found = FORMAL_DECISION_ARTIFACT_KEYS & set(artifacts)
    assert not found, f"Forbidden formal decision artifacts found: {found}"


def extract_formal_decisions(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract formal decision dicts from artifacts (single or plural)."""
    decisions: list[dict[str, Any]] = []
    single = artifacts.get("decision")
    if isinstance(single, dict) and single.get("decision_id"):
        decisions.append(single)
    for item in artifacts.get("decisions") or []:
        if isinstance(item, dict) and item.get("decision_id"):
            decisions.append(item)
    return decisions


def assert_active_decisions_have_anchors(decisions: list[dict[str, Any]]) -> None:
    """Assert that all active decisions have non-empty, non-fake rationale anchors."""
    for decision in decisions:
        action = decision.get("action")
        anchors = {
            str(anchor).strip().lower()
            for anchor in decision.get("rationale_anchor") or []
        }
        assert not (anchors & FAKE_ANCHORS), (
            f"Active decision has fake anchors: {anchors & FAKE_ANCHORS}"
        )
        if action in ACTIVE_ACTIONS:
            assert anchors, f"Active action {action} must have rationale anchors"


def assert_passive_empty_anchor_has_structured_justification(decision: dict[str, Any]) -> None:
    """Assert that a passive decision with empty anchors has structured justification."""
    anchors = {str(a).strip().lower() for a in decision.get("rationale_anchor") or []}
    action = decision.get("action")
    if action in PASSIVE_ACTIONS and not anchors:
        reason_codes = set(decision.get("decision_reason_codes") or [])
        assert (
            decision.get("evidence_state") in EMPTY_ANCHOR_STATES
            or reason_codes & EMPTY_ANCHOR_REASON_CODES
        ), (
            f"Passive action {action} with empty anchors must have structured "
            f"justification (evidence_state or reason_codes)"
        )
