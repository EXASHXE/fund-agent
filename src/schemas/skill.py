"""Skill runtime contracts for host-agent skill packs.

Skills are evidence producers. They receive a structured ``SkillInput`` and
return a structured ``SkillOutput``. Formal decisions are produced only by the
DecisionEngine, never by skills.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from src.schemas.evidence import EvidenceItem

SkillStatus = Literal["OK", "PARTIAL", "FAILED"]
SkillErrorCode = Literal[
    "MISSING_MCP_CAPABILITY",
    "MCP_CALL_FAILED",
    "INVALID_INPUT",
    "EVIDENCE_BUILD_FAILED",
    "EMPTY_RESULT",
    "INTERNAL_ERROR",
    "CONTRACT_VIOLATION",
]


@dataclass
class SkillError:
    """Standard structured skill error."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
        }


def normalize_skill_error(
    error: SkillError | dict[str, Any] | str | Exception,
    *,
    default_code: str = "RUNTIME_ERROR",
    recoverable: bool = True,
) -> dict[str, Any]:
    if isinstance(error, SkillError):
        return error.to_dict()
    if isinstance(error, dict):
        code = error.get("code", default_code)
        message = error.get("message")
        if message is None:
            try:
                message = str(error)
            except Exception:
                message = "unknown error"
        details = error.get("details")
        if not isinstance(details, dict):
            details = {"raw_details": details} if details is not None else {}
        err_recoverable = error.get("recoverable")
        if not isinstance(err_recoverable, bool):
            err_recoverable = recoverable
        return {
            "code": code,
            "message": message,
            "details": details,
            "recoverable": err_recoverable,
        }
    if isinstance(error, str):
        return {
            "code": default_code,
            "message": error,
            "details": {},
            "recoverable": recoverable,
        }
    if isinstance(error, Exception):
        return {
            "code": default_code,
            "message": str(error),
            "details": {"exception_type": type(error).__name__},
            "recoverable": recoverable,
        }
    return {
        "code": default_code,
        "message": str(error),
        "details": {"raw_type": type(error).__name__},
        "recoverable": recoverable,
    }


def normalize_skill_errors(
    errors: list[SkillError | dict[str, Any] | str | Exception] | None,
) -> list[dict[str, Any]]:
    if not errors:
        return []
    return [normalize_skill_error(e) for e in errors]


def make_skill_error_dict(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    recoverable: bool = True,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "recoverable": recoverable,
    }


@dataclass
class SkillInput:
    """Structured input passed from an external host to a skill."""

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
    errors: list[SkillError | dict[str, Any]] = field(default_factory=list)
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
            "errors": [normalize_skill_error(error) for error in self.errors],
            "used_mcp_capabilities": self.used_mcp_capabilities,
            "status": self.status,
        }
