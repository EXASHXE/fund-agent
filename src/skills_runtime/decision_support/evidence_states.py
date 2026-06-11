"""Evidence state constants for decision_support.

These constants document the semantics of the evidence_state field on
formal Decision objects. No schema migration is involved — this module
provides named constants and helper functions for the same string values
that have always been serialized in decision artifacts.

Evidence state semantics:
- ANCHORED: Sufficient anchored evidence supports the decision direction.
- INSUFFICIENT_EVIDENCE: Evidence is missing, weak, or stale; cannot
  support an active action.
- CRITIC_BLOCKED: Critique pipeline rejected the proposed action.
- CONSTRAINT_BLOCKED: Evidence may exist but action is blocked by
  constraints or analysis artifacts (redemption fee, position
  contribution, benchmark divergence, etc.).
- BUDGET_BLOCKED: Action is blocked by cash/budget/liquidity conditions
  (cash deployment not ready, cash buffer low, etc.).
- DOWNGRADED: Gatekeeper downgraded an active action to HOLD/WAIT due
  to one or more blockers.
"""

from __future__ import annotations

EVIDENCE_STATE_ANCHORED = "ANCHORED"
EVIDENCE_STATE_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
EVIDENCE_STATE_CRITIC_BLOCKED = "CRITIC_BLOCKED"
EVIDENCE_STATE_CONSTRAINT_BLOCKED = "CONSTRAINT_BLOCKED"
EVIDENCE_STATE_BUDGET_BLOCKED = "BUDGET_BLOCKED"
EVIDENCE_STATE_DOWNGRADED = "DOWNGRADED"

ALL_EVIDENCE_STATES: tuple[str, ...] = (
    EVIDENCE_STATE_ANCHORED,
    EVIDENCE_STATE_INSUFFICIENT_EVIDENCE,
    EVIDENCE_STATE_CRITIC_BLOCKED,
    EVIDENCE_STATE_CONSTRAINT_BLOCKED,
    EVIDENCE_STATE_BUDGET_BLOCKED,
    EVIDENCE_STATE_DOWNGRADED,
)


def is_active_evidence_state(state: str) -> bool:
    """Return True only when evidence is fully anchored and unblocked."""
    return state == EVIDENCE_STATE_ANCHORED


def is_blocked_evidence_state(state: str) -> bool:
    """Return True when evidence state indicates some form of blockage."""
    return state in (
        EVIDENCE_STATE_INSUFFICIENT_EVIDENCE,
        EVIDENCE_STATE_CRITIC_BLOCKED,
        EVIDENCE_STATE_CONSTRAINT_BLOCKED,
        EVIDENCE_STATE_BUDGET_BLOCKED,
        EVIDENCE_STATE_DOWNGRADED,
    )


def describe_evidence_state(state: str) -> str:
    """Return a human-readable description of an evidence state."""
    descriptions = {
        EVIDENCE_STATE_ANCHORED: "Sufficient anchored evidence supports the decision direction.",
        EVIDENCE_STATE_INSUFFICIENT_EVIDENCE: "Evidence is missing, weak, or stale; cannot support an active action.",
        EVIDENCE_STATE_CRITIC_BLOCKED: "Critique pipeline rejected the proposed action.",
        EVIDENCE_STATE_CONSTRAINT_BLOCKED: "Evidence may exist but action is blocked by constraints or analysis artifacts.",
        EVIDENCE_STATE_BUDGET_BLOCKED: "Action is blocked by cash/budget/liquidity conditions.",
        EVIDENCE_STATE_DOWNGRADED: "Gatekeeper downgraded an active action to HOLD/WAIT due to one or more blockers.",
    }
    return descriptions.get(state, f"Unknown evidence state: {state}")
