"""Status and failure-output helpers for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillError, SkillInput, SkillOutput


def failed_output(
    skill_input: SkillInput,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> SkillOutput:
    return SkillOutput(
        step_id=skill_input.step_id,
        skill_name=skill_input.skill_name,
        errors=[
            SkillError(
                code=code,
                message=message,
                details={
                    "skill_name": skill_input.skill_name,
                    **(details or {}),
                },
                recoverable=code not in {"INVALID_INPUT"},
            ).to_dict()
        ],
        warnings=[message],
        status="FAILED",
    )


def empty_evidence_output(
    skill_input: SkillInput,
    *,
    artifacts: dict[str, Any],
    warnings: list[str],
    errors: list[dict[str, Any]],
) -> SkillOutput:
    return SkillOutput(
        step_id=skill_input.step_id,
        skill_name=skill_input.skill_name,
        artifacts=artifacts,
        warnings=warnings,
        errors=errors
        or [
            SkillError(
                code="EMPTY_RESULT",
                message="FundAnalysisSkill produced no evidence",
                details={"skill_name": skill_input.skill_name},
            ).to_dict()
        ],
        status="FAILED",
    )


def status_from_analysis(
    *,
    errors: list[dict[str, Any]],
    data_completeness: dict[str, Any],
    warnings: list[str],
) -> str:
    # Enhanced status semantics:
    # OK    — enough data for a coherent portfolio report, no errors
    # PARTIAL — derived ledger unresolved, optional data requested but missing,
    #           stale data, or non-critical warnings exist
    # FAILED — no usable positions (caught earlier), no evidence produced
    if errors:
        status = "PARTIAL"
    elif data_completeness["grade"] in ("C", "D"):
        status = "PARTIAL"
        if "Report data completeness grade is" not in " ".join(warnings):
            warnings.append(
                f"Report data completeness grade is {data_completeness['grade']} "
                f"(score {data_completeness['score']:.2f})"
            )
    elif warnings:
        status = "PARTIAL"
    else:
        status = "OK"
    return status
