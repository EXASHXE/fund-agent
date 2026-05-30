"""Skill runtime contracts for Research OS.

Skills are evidence producers. They receive a structured ``SkillInput`` and
return a structured ``SkillOutput``. Formal decisions are produced only by the
DecisionEngine, never by skills.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from src.schemas.evidence import EvidenceItem

SkillStatus = Literal["OK", "PARTIAL", "FAILED"]


@dataclass
class SkillInput:
    """Structured input passed from ResearchOS to a skill."""

    task_id: str
    step_id: str
    skill_name: str
    payload: dict[str, Any]
    kg_context: dict[str, Any] = field(default_factory=dict)
    required_mcp_capabilities: list[str] = field(default_factory=list)
    evidence_context: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkillOutput:
    """Structured output returned by a skill."""

    step_id: str = ""
    skill_name: str = ""
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    used_mcp_capabilities: list[str] = field(default_factory=list)
    status: SkillStatus = "OK"

    def __post_init__(self) -> None:
        allowed = {"OK", "PARTIAL", "FAILED"}
        if self.status not in allowed:
            raise ValueError(f"SkillOutput.status must be one of {sorted(allowed)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "skill_name": self.skill_name,
            "evidence_items": [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in self.evidence_items
            ],
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "errors": self.errors,
            "used_mcp_capabilities": self.used_mcp_capabilities,
            "status": self.status,
        }
