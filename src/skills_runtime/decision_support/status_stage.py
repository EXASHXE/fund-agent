"""Status and error output helpers for decision support."""

from __future__ import annotations

from src.schemas.skill import SkillOutput
from src.skills_runtime.base import BaseSkillRuntime


class _SkillContractError(ValueError):
    """Internal exception carrying a standard SkillError code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def build_failed_output(skill_input, exc: Exception) -> SkillOutput:
    code = getattr(exc, "code", "INTERNAL_ERROR")
    return BaseSkillRuntime.failed_output(
        skill_input, code, str(exc), details={"error_type": type(exc).__name__}
    )
