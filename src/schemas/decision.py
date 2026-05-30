"""Decision-contract.v2 typed dataclass and ExecutionLedger wrapper.

Decision represents an actionable investment decision with full traceability
to evidence. ExecutionLedger collects multiple decisions for audit trails.

Constraints:
- BUY/SELL/INCREASE/REDUCE MUST have execution_amount > 0
- BUY/SELL/INCREASE/REDUCE MUST reference at least one real evidence_id
- WAIT/HOLD may use an empty rationale_anchor when insufficient evidence is
  explicitly explained
- trigger_conditions and invalidating_conditions are required
- risk_budget MUST be > 0
- audit_trail references evidence_ids for full traceability
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

ActionType = Literal["BUY", "SELL", "HOLD", "PAUSE_DCA", "REDUCE", "INCREASE", "WAIT"]

_ACTIONS_NEED_AMOUNT: frozenset[str] = frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})
_ACTIONS_NEED_ANCHOR: frozenset[str] = frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})
_PASSIVE_EMPTY_ANCHOR_ALLOWED: frozenset[str] = frozenset({"WAIT", "HOLD"})


@dataclass
class Decision:
    """Typed decision contract (decision-contract.v2).

    Attributes:
        decision_id: Unique identifier for this decision.
        action: The investment action to take.
        execution_amount: Amount for execution (required for BUY/SELL/INCREASE/REDUCE).
        rationale_anchor: Evidence IDs that directly support this decision.
            Active actions must contain at least one real evidence_id. WAIT/HOLD
            may leave this empty when insufficient evidence is explicitly noted.
        trigger_conditions: Conditions that triggered this decision.
            Must not be empty.
        invalidating_conditions: Conditions that would invalidate this decision.
            Must not be empty.
        time_horizon: Expected time horizon for this decision.
        risk_budget: Risk budget allocated for this decision. Must be > 0.
        audit_trail: Chain of evidence_ids leading to this decision.
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

        if any(anchor == "no_evidence_available" for anchor in self.rationale_anchor):
            raise ValueError(
                "rationale_anchor must reference real evidence_id values, "
                "not no_evidence_available"
            )

        # Active decisions must reference at least one real evidence_id.
        if self.action in _ACTIONS_NEED_ANCHOR and not self.rationale_anchor:
            raise ValueError(
                "Active decision must reference at least one evidence_id in rationale_anchor"
            )

        if (
            not self.rationale_anchor
            and self.action in _PASSIVE_EMPTY_ANCHOR_ALLOWED
            and not self._explains_insufficient_evidence()
        ):
            raise ValueError(
                "WAIT/HOLD with empty rationale_anchor must explain insufficient evidence"
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

    def _explains_insufficient_evidence(self) -> bool:
        text = " ".join(
            list(self.trigger_conditions)
            + list(self.invalidating_conditions)
            + list(self.audit_trail)
        ).lower()
        return "insufficient evidence" in text

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
    generated_at: datetime = field(default_factory=datetime.now)
    version: str = "execution-ledger.v1"

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "version": self.version,
            "generated_at": self.generated_at.isoformat(),
            "decisions": [d.to_dict() for d in self.decisions],
        }

    def total_risk_budget(self) -> float:
        """Sum of risk budgets across all decisions."""
        return sum(d.risk_budget for d in self.decisions)

    def actions_summary(self) -> dict[str, int]:
        """Count of each action type across all decisions."""
        return dict(Counter(d.action for d in self.decisions))
