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
FORMAL_DECISION_ARTIFACTS = FORMAL_DECISION_ARTIFACT_KEYS

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


def artifacts_from_envelope(envelope_or_artifacts: dict[str, Any]) -> dict[str, Any]:
    """Return artifacts whether passed a bridge envelope or artifacts dict."""
    artifacts = envelope_or_artifacts.get("artifacts")
    if isinstance(artifacts, dict):
        return artifacts
    return envelope_or_artifacts


def extract_formal_decisions(envelope_or_artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract formal decision dicts from artifacts (single or plural)."""
    artifacts = artifacts_from_envelope(envelope_or_artifacts)
    decisions: list[dict[str, Any]] = []
    single = artifacts.get("decision")
    if isinstance(single, dict) and single.get("decision_id"):
        decisions.append(single)
    for item in artifacts.get("decisions") or []:
        if isinstance(item, dict) and item.get("decision_id"):
            decisions.append(item)
    return decisions


def assert_no_fake_rationale_anchors(decisions: list[dict[str, Any]]) -> None:
    """Assert that formal decisions contain no placeholder anchors."""
    for decision in decisions:
        anchors = {
            str(anchor).strip().lower()
            for anchor in decision.get("rationale_anchor") or []
        }
        assert not (anchors & FAKE_ANCHORS), (
            f"Decision has fake anchors: {anchors & FAKE_ANCHORS}"
        )


def assert_active_decisions_have_anchors(decisions: list[dict[str, Any]]) -> None:
    """Assert that all active decisions have non-empty, non-fake rationale anchors."""
    assert_no_fake_rationale_anchors(decisions)
    for decision in decisions:
        action = decision.get("action")
        anchors = {
            str(anchor).strip().lower()
            for anchor in decision.get("rationale_anchor") or []
        }
        if action in ACTIVE_ACTIONS:
            assert anchors, f"Active action {action} must have rationale anchors"


def _coerce_decisions(decisions_or_decision: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(decisions_or_decision, list):
        return decisions_or_decision
    if decisions_or_decision.get("decision_id") or decisions_or_decision.get("action"):
        return [decisions_or_decision]
    return extract_formal_decisions(decisions_or_decision)


def assert_passive_empty_anchor_has_structured_justification(
    decisions_or_decision: dict[str, Any] | list[dict[str, Any]],
) -> None:
    """Assert passive empty-anchor decisions carry structured justification."""
    for decision in _coerce_decisions(decisions_or_decision):
        anchors = {str(a).strip().lower() for a in decision.get("rationale_anchor") or []}
        action = decision.get("action")
        if action not in PASSIVE_ACTIONS or anchors:
            continue
        reason_codes = set(decision.get("decision_reason_codes") or [])
        assert (
            decision.get("evidence_state") in EMPTY_ANCHOR_STATES
            or reason_codes & EMPTY_ANCHOR_REASON_CODES
        ), (
            f"Passive action {action} with empty anchors must have structured "
            f"justification (evidence_state or reason_codes)"
        )
