"""FinalThesis and report schemas for Research OS output.

The FinalThesis is the structured output of a Research OS run.
It packages the decision, ledger, evidence, and metadata into
a serializable dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FinalThesis:
    """Structured output of the Research OS pipeline.

    Contains the final decision, execution ledger, evidence summary,
    and iteration metadata. All fields are serializable via to_dict().
    """

    thesis_id: str
    task_id: str
    decision: dict[str, Any] | None = None
    ledger: dict[str, Any] | None = None
    evidence_count: int = 0
    iterations: int = 0
    critique_status: str = "N/A"
    circuit_broken: bool = False
    kg_context_snapshot: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "task_id": self.task_id,
            "decision": self.decision,
            "ledger": self.ledger,
            "evidence_count": self.evidence_count,
            "iterations": self.iterations,
            "critique_status": self.critique_status,
            "circuit_broken": self.circuit_broken,
            "kg_context_snapshot": self.kg_context_snapshot,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FinalThesis:
        return cls(
            thesis_id=data.get("thesis_id", ""),
            task_id=data.get("task_id", ""),
            decision=data.get("decision"),
            ledger=data.get("ledger"),
            evidence_count=data.get("evidence_count", 0),
            iterations=data.get("iterations", 0),
            critique_status=data.get("critique_status", "N/A"),
            circuit_broken=data.get("circuit_broken", False),
            kg_context_snapshot=data.get("kg_context_snapshot", {}),
            generated_at=data.get("generated_at", ""),
        )
