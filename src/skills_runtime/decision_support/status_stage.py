"""Status and error output helpers for decision support."""

from __future__ import annotations

from src.schemas.skill import SkillError, SkillOutput


class _SkillContractError(ValueError):
    """Internal exception carrying a standard SkillError code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def build_failed_output(skill_input, exc: Exception) -> SkillOutput:
    code = getattr(exc, "code", "INTERNAL_ERROR")
    return SkillOutput(
        step_id=skill_input.step_id,
        skill_name=skill_input.skill_name,
        errors=[
            SkillError(
                code=code,
                message=str(exc),
                details={
                    "error_type": type(exc).__name__,
                    "skill_name": skill_input.skill_name,
                },
                recoverable=code != "CONTRACT_VIOLATION",
            ).to_dict()
        ],
        warnings=[str(exc)],
        status="FAILED",
    )
