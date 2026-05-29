"""Decision Engine — produces Decisions from evidence + critique results.

Generates Decision instances with contract enforcement:
    - Non-PASS critique → only WAIT/HOLD allowed
    - BUY/SELL/INCREASE/REDUCE require execution_amount > 0
    - Every Decision references evidence in rationale_anchor
    - Full audit trail for traceability

Design constraints:
    * No LLM / network / IO imports — pure decision logic.
    * References EvidenceGraph and CritiqueResult via duck-typing
      (uses hasattr) for loose coupling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from src.schemas.decision import Decision, ActionType

# Actions that require PASS critique to execute
ACTIVE_ACTIONS: frozenset[str] = frozenset({"BUY", "SELL", "INCREASE", "REDUCE"})
PASSIVE_ACTIONS: frozenset[str] = frozenset({"WAIT", "HOLD", "PAUSE_DCA"})


class DecisionEngine:
    """Generates decisions with contract enforcement.

    Enforcement rules:
        1. Non-PASS critique → only WAIT/HOLD allowed (downgrade active → WAIT)
        2. Every Decision must reference evidence in rationale_anchor
        3. Every Decision must have trigger/invalidating conditions
        4. Risk budget always > 0
        5. Audit trail built from evidence and critique
    """

    def __init__(self, strategy_engine: Any = None) -> None:
        self._strategy_engine = strategy_engine

    def decide(
        self,
        task: Any,
        evidence_graph: Any,
        critique: Any,
    ) -> Decision:
        """Generate a decision from task, evidence, and critique.

        Args:
            task: ResearchTask with objective, constraints, risk_profile.
            evidence_graph: EvidenceGraph containing collected evidence items.
            critique: CritiqueResult with status (PASS/RETRY/FAIL).

        Returns:
            Decision with full contract compliance.
        """

        # Rule 1: Determine action from evidence and critique
        action = self._determine_action(task, evidence_graph, critique)

        # Rule 2: Validate action against critique status
        critique_passed = getattr(critique, "status", None) == "PASS"
        if not critique_passed and action in ACTIVE_ACTIONS:
            # Downgrade active actions to WAIT when critique fails
            action = "WAIT"

        # Rule 3: Extract execution amount
        execution_amount = self._calculate_execution_amount(
            task, action, evidence_graph
        )

        # Rule 4: Build rationale anchor from evidence
        rationale_anchor = self._extract_rationale_anchor(evidence_graph)

        # Rule 5: Build trigger/invalidating conditions
        trigger_conditions = self._build_trigger_conditions(task, action)
        invalidating_conditions = self._build_invalidating_conditions(task, action)

        # Rule 6: Risk budget
        risk_budget = self._calculate_risk_budget(task, action)

        # Rule 7: Audit trail
        audit_trail = self._build_audit_trail(evidence_graph, critique)

        return Decision(
            decision_id=str(uuid.uuid4()),
            action=action,
            execution_amount=execution_amount,
            rationale_anchor=rationale_anchor,
            trigger_conditions=trigger_conditions,
            invalidating_conditions=invalidating_conditions,
            time_horizon=task.time_horizon if getattr(task, "time_horizon", None) else "1 year",
            risk_budget=risk_budget,
            audit_trail=audit_trail,
            created_at=datetime.now(),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _determine_action(
        self, task: Any, evidence_graph: Any, critique: Any
    ) -> str:
        """Determine the action based on task, evidence, and critique status.

        Default: HOLD when evidence is sparse.
        """
        # Check evidence exists
        items = getattr(evidence_graph, "items", None)
        if not items:
            return "WAIT"

        # If critique hasn't passed, return WAIT
        critique_status = getattr(critique, "status", None)
        if critique_status != "PASS":
            return "WAIT"

        # Check evidence direction for signal
        positive = 0.0
        negative = 0.0
        for item in items.values():
            direction = getattr(item, "direction", "neutral")
            weight = getattr(item, "confidence_weight", 1.0)
            if direction == "positive":
                positive += weight
            elif direction == "negative":
                negative += weight

        # Simple signal: more positive → BUY/INCREASE, more negative → SELL/REDUCE
        risk_profile = getattr(task, "risk_profile", "moderate")

        if positive > negative * 1.5:
            return "INCREASE" if risk_profile == "conservative" else "BUY"
        elif negative > positive * 1.5:
            return "REDUCE" if risk_profile == "aggressive" else "SELL"
        else:
            return "HOLD"

    def _calculate_execution_amount(
        self, task: Any, action: str, evidence_graph: Any
    ) -> float:
        """Calculate execution amount. Must be > 0 for active actions."""
        if action in PASSIVE_ACTIONS:
            return 0.0
        default_amount = 10000.0
        constraints = getattr(task, "constraints", None) or {}
        if isinstance(constraints, dict) and "max_position" in constraints:
            default_amount = float(constraints["max_position"])
        return default_amount

    def _extract_rationale_anchor(self, evidence_graph: Any) -> list[str]:
        """Extract evidence IDs as rationale anchor.

        Returns up to 10 evidence IDs from the graph.
        Returns a descriptive placeholder when no evidence exists.
        Callers must handle the no-evidence case (typically WAIT/HOLD).
        """
        items = getattr(evidence_graph, "items", None)
        if not items:
            return ["no_evidence_available"]
        return list(items.keys())[:10]

    def _build_trigger_conditions(
        self, task: Any, action: str
    ) -> list[str]:
        """Build trigger conditions for the decision."""
        conditions = [f"Critique status must be PASS for {action}"]
        if action in ACTIVE_ACTIONS:
            conditions.append("Evidence direction consensus confirmed")
        return conditions

    def _build_invalidating_conditions(
        self, task: Any, action: str
    ) -> list[str]:
        """Build conditions that would invalidate this decision."""
        return [
            "Evidence contradiction detected",
            "Market regime changes to CRISIS",
            "Risk budget exceeded",
        ]

    def _calculate_risk_budget(
        self, task: Any, action: str
    ) -> float:
        """Calculate risk budget. Must be > 0."""
        risk_map = {
            "conservative": 0.02,
            "moderate": 0.05,
            "aggressive": 0.10,
        }
        risk_profile = getattr(task, "risk_profile", "moderate")
        base = risk_map.get(risk_profile, 0.05)
        # Active actions get full budget; passive get minimal
        if action in PASSIVE_ACTIONS:
            return 0.01
        return base

    def _build_audit_trail(
        self, evidence_graph: Any, critique: Any
    ) -> list[str]:
        """Build audit trail from evidence and critique."""
        trail: list[str] = []
        items = getattr(evidence_graph, "items", None)
        if items:
            trail.append(f"Evidence items: {len(items)}")
        if critique is not None:
            trail.append(f"Critique status: {getattr(critique, 'status', 'unknown')}")
            issues = getattr(critique, "issues", [])
            trail.append(f"Issues: {len(issues)}")
        trail.append(f"Generated at: {datetime.now().isoformat()}")
        return trail
