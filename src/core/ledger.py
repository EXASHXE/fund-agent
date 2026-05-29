"""Ledger Builder — produces ExecutionLedger from Decisions + Evidence.

Wraps one or more Decision instances into an ExecutionLedger for
audit trail output. Provides aggregate views (total risk, action
distribution) for downstream consumers.

Design constraints:
    * No LLM / network / IO imports — pure aggregation logic.
    * Uses the typed Decision and ExecutionLedger from src/schemas/decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.decision import Decision, ExecutionLedger


class LedgerBuilder:
    """Builds ExecutionLedger from decisions and evidence.

    The builder validates that all input items are Decision instances
    before constructing the ledger, then provides aggregate views
    (total_risk, actions_summary) for downstream reporting.
    """

    def build(
        self,
        decision: Decision,
        evidence_graph: Any = None,
    ) -> ExecutionLedger:
        """Build a ledger for a single decision.

        Args:
            decision: A single Decision instance.
            evidence_graph: Optional EvidenceGraph (reserved for future use).

        Returns:
            ExecutionLedger wrapping the single decision.

        Raises:
            TypeError: If decision is not a Decision instance.
        """
        if not isinstance(decision, Decision):
            raise TypeError(
                f"Expected Decision, got {type(decision).__name__}"
            )

        return ExecutionLedger(
            decisions=[decision],
            generated_at=datetime.now(),
        )

    def build_multi(
        self,
        decisions: list[Decision],
        evidence_graph: Any = None,
    ) -> ExecutionLedger:
        """Build a ledger for multiple decisions.

        Args:
            decisions: List of Decision instances.
            evidence_graph: Optional EvidenceGraph (reserved for future use).

        Returns:
            ExecutionLedger wrapping all decisions.

        Raises:
            TypeError: If any item is not a Decision instance.
        """
        for d in decisions:
            if not isinstance(d, Decision):
                raise TypeError(
                    f"Expected Decision, got {type(d).__name__}"
                )

        return ExecutionLedger(
            decisions=decisions,
            generated_at=datetime.now(),
        )

    def total_risk(self, ledger: ExecutionLedger) -> float:
        """Compute total risk budget across all decisions.

        Args:
            ledger: The ExecutionLedger to aggregate.

        Returns:
            Sum of all risk_budget values across decisions.
        """
        return sum(d.risk_budget for d in ledger.decisions)

    def actions_summary(self, ledger: ExecutionLedger) -> dict[str, int]:
        """Summarize actions in the ledger.

        Args:
            ledger: The ExecutionLedger to summarize.

        Returns:
            Dict mapping action type to count across all decisions.
        """
        summary: dict[str, int] = {}
        for d in ledger.decisions:
            summary[d.action] = summary.get(d.action, 0) + 1
        return summary
