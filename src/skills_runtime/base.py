"""Shared runtime base helpers for skill runtime handlers.

Provides BaseSkillRuntime with standardized skill name handling, error
creation, FAILED output, entity extraction, and deterministic status helpers.

Rules:
- Keep it lightweight.
- Do not change SkillInput or SkillOutput schemas.
- Do not introduce new dependencies.
- Prefer adopting it in news_research, sentiment_analysis, and thesis_generation.
"""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillError, SkillInput, SkillOutput, make_skill_error_dict, normalize_skill_error, normalize_skill_errors


class BaseSkillRuntime:
    """Base class for skill runtime handlers with shared helpers."""

    mcp_adapter: Any = None
    tool_registry: Any = None

    @staticmethod
    def make_skill_error(
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
    ) -> dict[str, Any]:
        return make_skill_error_dict(code, message, details, recoverable)

    @staticmethod
    def failed_output(
        skill_input: SkillInput,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
    ) -> SkillOutput:
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            warnings=[message],
            errors=[
                SkillError(
                    code=code,
                    message=message,
                    details=details or {"skill_name": skill_input.skill_name},
                    recoverable=recoverable,
                ).to_dict()
            ],
            status="FAILED",
        )

    @staticmethod
    def ok_output(
        skill_input: SkillInput,
        *,
        artifacts: dict[str, Any] | None = None,
        evidence_items: list | None = None,
        warnings: list[str] | None = None,
        errors: list | None = None,
        used_mcp_capabilities: list[str] | None = None,
    ) -> SkillOutput:
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            artifacts=artifacts or {},
            evidence_items=evidence_items or [],
            warnings=warnings or [],
            errors=errors or [],
            used_mcp_capabilities=used_mcp_capabilities or [],
            status="OK",
        )

    @staticmethod
    def partial_output(
        skill_input: SkillInput,
        *,
        artifacts: dict[str, Any] | None = None,
        evidence_items: list | None = None,
        warnings: list[str] | None = None,
        errors: list | None = None,
        used_mcp_capabilities: list[str] | None = None,
    ) -> SkillOutput:
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            artifacts=artifacts or {},
            evidence_items=evidence_items or [],
            warnings=warnings or [],
            errors=errors or [],
            used_mcp_capabilities=used_mcp_capabilities or [],
            status="PARTIAL",
        )

    @staticmethod
    def normalize_entities_from_input(skill_input: SkillInput) -> list[str]:
        payload_entities = skill_input.payload.get("related_entities")
        if isinstance(payload_entities, list) and payload_entities:
            return payload_entities
        fund_codes = skill_input.kg_context.get("fund_codes", [])
        if isinstance(fund_codes, list) and fund_codes:
            return [
                code if str(code).startswith("fund:") else f"fund:{code}"
                for code in fund_codes
            ]
        return ["research_task"]

    @staticmethod
    def normalize_error(
        error: SkillError | dict[str, Any] | str | Exception,
        *,
        code: str = "RUNTIME_ERROR",
        recoverable: bool = True,
    ) -> dict[str, Any]:
        return normalize_skill_error(error, default_code=code, recoverable=recoverable)

    @staticmethod
    def normalize_errors(
        errors: list[Any] | None,
    ) -> list[dict[str, Any]]:
        return normalize_skill_errors(errors)

    @staticmethod
    def _unique_strings(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
