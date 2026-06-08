"""Decision support skill runtime package.

This is the only runtime skill that may produce formal Decision and
ExecutionLedger artifacts. It consumes an already compiled EvidenceGraph from
the host agent and applies local, deterministic contract rules.
"""

from __future__ import annotations

from .skill import DecisionSupportSkill

__all__ = ["DecisionSupportSkill"]
