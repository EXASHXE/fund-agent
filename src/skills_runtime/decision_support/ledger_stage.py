"""ExecutionLedger construction helpers."""

from __future__ import annotations

from src.schemas.decision import Decision, ExecutionLedger


def build_ledger(decisions: list[Decision]) -> ExecutionLedger:
    """Build an ExecutionLedger from a list of Decisions."""
    return ExecutionLedger(decisions=decisions)
