"""Decision-contract.v2 typed dataclass and ExecutionLedger wrapper.

Decision represents an actionable investment decision with full traceability
to evidence. ExecutionLedger collects multiple decisions for audit trails.

Constraints:
- BUY/SELL/INCREASE/REDUCE MUST have execution_amount > 0
- BUY/SELL/INCREASE/REDUCE MUST reference at least one real evidence_id
- WAIT/HOLD/PAUSE_DCA may use an empty rationale_anchor only when
  structured justification fields explain insufficient evidence or blockage
- trigger_conditions and invalidating_conditions are required
- risk_budget MUST be > 0
- audit_trail references evidence_ids for full traceability
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal
import uuid

ActionType = Literal["BUY", "SELL", "HOLD", "PAUSE_DCA", "REDUCE", "INCREASE", "WAIT"]
EvidenceState = Literal[
    "ANCHORED",
    "INSUFFICIENT_EVIDENCE",
    "CRITIC_BLOCKED",
    "CONSTRAINT_BLOCKED",
    "BUDGET_BLOCKED",
    "DOWNGRADED",
]

DECISION_REASON_CODES: tuple[str, ...] = (
    "EVIDENCE_AVAILABLE",
    "EVIDENCE_MISSING",
    "EVIDENCE_STALE",
    "EVIDENCE_WEAK",
    "EVIDENCE_SUFFICIENT",
    "EVIDENCE_CONTRADICTORY",
    "INSUFFICIENT_EVIDENCE",
    "CRITIC_BLOCKED",
    "REDEMPTION_FEE_RISK",
    "FEE_LOCKUP",
    "THEME_OVERWEIGHT",
    "RIGHT_SIDE_UNCONFIRMED",
    "MOMENTUM_UNCONFIRMED",
    "NEWS_NEGATIVE",
    "NEWS_POSITIVE_BUT_PRICE_WEAK",
    "BENCHMARK_DIVERGENCE",
    "PROFIT_PROTECTION",
    "LOSS_CONTROL",
    "EVENT_HYPE_FAILED",
    "CASH_BUFFER_LOW",
    "CASH_DEPLOYMENT_NOT_READY",
    "SHORT_TERM_BUDGET_EXCEEDED",
    "TRANSACTION_HISTORY_MISSING",
    "USER_CONSTRAINT_MISSING",
    "VALUATION_UNKNOWN",
    "CONSTRAINT_BLOCKED",
    "BUDGET_BLOCKED",
    "RISK_PROFILE_MISSING",
    "LIQUIDITY_NEED_UNKNOWN",
    "DOWNGRADED_ACTIVE_TO_HOLD",
    "PASSIVE_ACTION",
    "ACTIVE_ACTION_ALLOWED",
)
EVIDENCE_STATES: tuple[str, ...] = (
    "ANCHORED",
    "INSUFFICIENT_EVIDENCE",
    "CRITIC_BLOCKED",
    "CONSTRAINT_BLOCKED",
    "BUDGET_BLOCKED",
    "DOWNGRADED",
)

_ACTIONS_NEED_AMOUNT: frozenset[str] = frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})
_ACTIONS_NEED_ANCHOR: frozenset[str] = frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})
_PASSIVE_EMPTY_ANCHOR_ALLOWED: frozenset[str] = frozenset({"WAIT", "HOLD", "PAUSE_DCA"})
_PASSIVE_EMPTY_ANCHOR_EVIDENCE_STATES: frozenset[str] = frozenset({
    "INSUFFICIENT_EVIDENCE",
    "CRITIC_BLOCKED",
    "CONSTRAINT_BLOCKED",
    "BUDGET_BLOCKED",
    "DOWNGRADED",
})
_PASSIVE_EMPTY_ANCHOR_REASON_CODES: frozenset[str] = frozenset({
    "INSUFFICIENT_EVIDENCE",
    "CRITIC_BLOCKED",
    "CONSTRAINT_BLOCKED",
    "BUDGET_BLOCKED",
    "DOWNGRADED_ACTIVE_TO_HOLD",
})
_FAKE_ANCHORS: frozenset[str] = frozenset({
    "no_evidence_available",
    "fake_anchor",
    "fake-anchor",
    "placeholder",
    "missing_evidence",
    "missing-evidence",
})


@dataclass
class Decision:
    """Typed decision contract (decision-contract.v2).

    Attributes:
        decision_id: Unique identifier for this decision.
        action: The investment action to take.
        execution_amount: Amount for execution (required for BUY/SELL/INCREASE/REDUCE).
        rationale_anchor: Evidence IDs that directly support this decision.
            Active actions must contain at least one real evidence_id.
            WAIT/HOLD/PAUSE_DCA may leave this empty only when structured
            justification fields explain insufficient evidence or blockage.
        trigger_conditions: Conditions that triggered this decision.
            Must not be empty.
        invalidating_conditions: Conditions that would invalidate this decision.
            Must not be empty.
        time_horizon: Expected time horizon for this decision.
        risk_budget: Risk budget allocated for this decision. Must be > 0.
        audit_trail: Chain of evidence_ids leading to this decision.
        decision_reason_codes: Machine-readable justification codes.
        evidence_state: Structured summary of evidence availability/blockage.
        blocked_by: Structured blocking causes such as evidence, critic,
            constraint, or budget.
        version: Schema version string. Defaults to "decision-contract.v2".
        created_at: When this decision was created.
    """

    decision_id: str
    action: ActionType
    execution_amount: float
    rationale_anchor: list[str]
    trigger_conditions: list[str]
    invalidating_conditions: list[str]
    time_horizon: str
    risk_budget: float
    audit_trail: list[str] = field(default_factory=list)
    decision_reason_codes: list[str] = field(default_factory=list)
    evidence_state: EvidenceState = "ANCHORED"
    blocked_by: list[str] = field(default_factory=list)
    version: str = "decision-contract.v2"
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate constraints after initialization."""
        # Actions that require execution must have positive amount
        if self.action in _ACTIONS_NEED_AMOUNT and self.execution_amount <= 0:
            raise ValueError(
                f"Action '{self.action}' requires execution_amount > 0, "
                f"got {self.execution_amount}"
            )

        # Must have trigger conditions
        if not self.trigger_conditions:
            raise ValueError("Decision must specify trigger_conditions")

        # Must have invalidating conditions
        if not self.invalidating_conditions:
            raise ValueError("Decision must specify invalidating_conditions")

        if self.evidence_state not in EVIDENCE_STATES:
            raise ValueError(
                f"evidence_state must be one of {', '.join(EVIDENCE_STATES)}, "
                f"got {self.evidence_state!r}"
            )

        if any(str(anchor).strip().lower() in _FAKE_ANCHORS for anchor in self.rationale_anchor):
            raise ValueError(
                "rationale_anchor must reference real evidence_id values, "
                "not fake placeholders"
            )

        # Active decisions must reference at least one real evidence_id.
        if self.action in _ACTIONS_NEED_ANCHOR and not self.rationale_anchor:
            raise ValueError(
                "Active decision must reference at least one evidence_id in rationale_anchor"
            )

        if (
            not self.rationale_anchor
            and self.action in _PASSIVE_EMPTY_ANCHOR_ALLOWED
            and not self._has_empty_anchor_justification()
        ):
            raise ValueError(
                "WAIT/HOLD/PAUSE_DCA with empty rationale_anchor must carry "
                "structured decision_reason_codes or evidence_state explaining "
                "insufficient evidence or blockage"
            )

        if not self.rationale_anchor and self.action not in _PASSIVE_EMPTY_ANCHOR_ALLOWED:
            raise ValueError(
                "Decision must reference at least one evidence_id in rationale_anchor"
            )

        # Risk budget must be positive
        if self.risk_budget <= 0:
            raise ValueError(
                f"risk_budget must be > 0, got {self.risk_budget}"
            )

    def _has_empty_anchor_justification(self) -> bool:
        if self.evidence_state in _PASSIVE_EMPTY_ANCHOR_EVIDENCE_STATES:
            return True

        reason_codes = {str(code) for code in self.decision_reason_codes}
        if reason_codes & _PASSIVE_EMPTY_ANCHOR_REASON_CODES:
            return True

        return self._legacy_explains_insufficient_evidence()

    def _legacy_explains_insufficient_evidence(self) -> bool:
        # Backward compatibility for older fixtures/hosts that explained
        # passive empty-anchor decisions only in free text. New runtime outputs
        # must populate structured justification fields instead.
        text = " ".join(
            list(self.trigger_conditions)
            + list(self.invalidating_conditions)
            + list(self.audit_trail)
        ).lower()
        return "insufficient evidence" in text or "blocked by critic" in text

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict.

        Compatible with the existing agent_decisions JSON format.
        """
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        return result


@dataclass
class ExecutionLedger:
    """Collection of decisions with full audit trail.

    Wraps multiple Decision instances for batch output, providing
    aggregate views of risk budget and action distribution.

    Attributes:
        decisions: List of Decision instances.
        generated_at: When this ledger was generated.
        version: Schema version string. Defaults to "execution-ledger.v1".
    """

    decisions: list[Decision]
    ledger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = field(default_factory=datetime.now)
    version: str = "execution-ledger.v1"

    def ledger_summary(self) -> dict[str, Any]:
        """Compute aggregate summary across all decisions in the ledger."""
        _ACTIVE = _ACTIONS_NEED_AMOUNT

        action_counts: dict[str, int] = {}
        for action in ("BUY", "SELL", "INCREASE", "REDUCE", "HOLD", "WAIT", "PAUSE_DCA"):
            action_counts[action] = 0

        active_count = 0
        passive_count = 0
        downgraded_count = 0
        blocked_count = 0
        total_execution_amount = 0.0
        total_risk_budget = 0.0
        blocked_by_counts: dict[str, int] = {}
        reason_code_counts: dict[str, int] = {}

        for d in self.decisions:
            action_counts[d.action] = action_counts.get(d.action, 0) + 1
            if d.action in _ACTIVE:
                active_count += 1
            else:
                passive_count += 1

            if "DOWNGRADED_ACTIVE_TO_HOLD" in d.decision_reason_codes:
                downgraded_count += 1
            if d.blocked_by:
                blocked_count += 1
                for b in d.blocked_by:
                    blocked_by_counts[b] = blocked_by_counts.get(b, 0) + 1
            for rc in d.decision_reason_codes:
                reason_code_counts[rc] = reason_code_counts.get(rc, 0) + 1

            total_execution_amount += d.execution_amount
            total_risk_budget += d.risk_budget

        return {
            "action_counts": action_counts,
            "decision_count": len(self.decisions),
            "active_decision_count": active_count,
            "passive_decision_count": passive_count,
            "downgraded_decision_count": downgraded_count,
            "blocked_decision_count": blocked_count,
            "total_execution_amount": round(total_execution_amount, 2),
            "total_risk_budget": round(total_risk_budget, 4),
            "blocked_by_counts": blocked_by_counts,
            "reason_code_counts": reason_code_counts,
        }

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        decisions = []
        for decision in self.decisions:
            payload = decision.to_dict()
            payload["evidence_ids"] = list(decision.rationale_anchor)
            decisions.append(payload)
        return {
            "ledger_id": self.ledger_id,
            "version": self.version,
            "generated_at": self.generated_at.isoformat(),
            "decisions": decisions,
            "ledger_summary": self.ledger_summary(),
        }

    def total_risk_budget(self) -> float:
        """Sum of risk budgets across all decisions."""
        return sum(d.risk_budget for d in self.decisions)

    def actions_summary(self) -> dict[str, int]:
        """Count of each action type across all decisions."""
        return dict(Counter(d.action for d in self.decisions))
