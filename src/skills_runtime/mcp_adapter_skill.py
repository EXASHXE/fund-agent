"""MCP adapter skill base class for skills that call host-injected MCP capabilities.

Provides MCPAdapterSkill(BaseSkillRuntime) with standardized capability selection,
MCP calling, response item extraction, SoftEvidence construction, and failure
handling for MCP-backed skills like news_research and sentiment_analysis.

Rules:
- It must call only host-injected mcp_adapter.
- It must not import provider SDKs.
- It must not call network.
- It must not know about specific providers.
- It should preserve current status behavior:
  - OK if evidence items exist and no evidence-build errors
  - PARTIAL if evidence items exist with build errors
  - FAILED if no evidence items
  - FAILED if required MCP capability is missing
  - FAILED if MCP call fails
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.evidence import EvidenceItem
from src.schemas.skill import SkillError, SkillInput, SkillOutput
from src.skills_runtime.base import BaseSkillRuntime
from src.tools.evidence.builders import build_soft_evidence_from_mcp_result


class MCPAdapterSkill(BaseSkillRuntime):
    """Base class for MCP adapter skills that produce SoftEvidence."""

    preferred_capabilities: tuple[str, ...] = ()
    response_item_keys: tuple[str, ...] = ("items", "results")
    default_entity: str = "research_task"

    def __init__(self, mcp_adapter: Any = None) -> None:
        self.mcp_adapter = mcp_adapter

    def select_capability(
        self,
        required: list[str],
        preferred: tuple[str, ...] | None = None,
    ) -> str | None:
        if self.mcp_adapter is None:
            return None
        prefs = preferred if preferred is not None else self.preferred_capabilities
        candidates = list(dict.fromkeys(list(prefs) + list(required)))
        for name in candidates:
            if self.mcp_adapter.has_capability(name):
                return name
        return None

    def call_mcp(self, capability: str, payload: dict) -> dict:
        return self.mcp_adapter.call(capability, payload)

    @staticmethod
    def items_from_response(
        data: dict,
        item_keys: tuple[str, ...] | None = None,
    ) -> list[dict]:
        keys = item_keys or ("items", "results")
        if not isinstance(data, dict):
            return []
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data] if data else []

    def build_soft_evidence_items(
        self,
        items: list[dict],
        capability: str,
        entities: list[str],
        skill_input: SkillInput,
    ) -> tuple[list[EvidenceItem], list[dict[str, Any]]]:
        evidence_items: list[EvidenceItem] = []
        errors: list[dict[str, Any]] = []
        for item in items:
            try:
                evidence_items.append(
                    self._build_single_evidence(
                        item=item,
                        capability=capability,
                        entities=entities,
                        skill_input=skill_input,
                    )
                )
            except Exception as exc:
                errors.append(
                    SkillError(
                        code="EVIDENCE_BUILD_FAILED",
                        message=str(exc),
                        details={
                            "error_type": type(exc).__name__,
                            "skill_name": skill_input.skill_name,
                        },
                    ).to_dict()
                )
        return evidence_items, errors

    def _build_single_evidence(
        self,
        item: dict,
        capability: str,
        entities: list[str],
        skill_input: SkillInput,
    ) -> EvidenceItem:
        return build_soft_evidence_from_mcp_result(
            source_type=item.get("source_type") or capability,
            timestamp=item.get("timestamp") or datetime.now(),
            related_entities=item.get("related_entities") or entities,
            claim=item.get("claim") or item.get("title") or "MCP result item",
            value=item,
            confidence_weight=item.get("confidence_weight", item.get("confidence", 0.5)),
            direction=item.get("direction", "neutral"),
            provenance={
                "mcp_capability": capability,
                "skill_name": skill_input.skill_name,
            },
        )

    def failed_missing_capability(
        self,
        skill_input: SkillInput,
        message: str,
    ) -> SkillOutput:
        return self.failed_output(
            skill_input,
            "MISSING_MCP_CAPABILITY",
            message,
        )

    def failed_mcp_call(
        self,
        skill_input: SkillInput,
        capability: str,
        response: dict,
    ) -> SkillOutput:
        error_info = response.get("error", {})
        return self.failed_output(
            skill_input,
            "MCP_CALL_FAILED",
            error_info.get("message", "MCP call failed"),
            details={"capability": capability, "error": error_info},
        )

    def empty_result_output(
        self,
        skill_input: SkillInput,
        capability: str,
        response_data: dict,
        errors: list[dict[str, Any]],
    ) -> SkillOutput:
        if not errors:
            errors.append(
                SkillError(
                    code="EMPTY_RESULT",
                    message=f"{skill_input.skill_name} returned no evidence items",
                    details={"skill_name": skill_input.skill_name},
                ).to_dict()
            )
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            evidence_items=[],
            artifacts={"mcp_response": response_data},
            errors=errors,
            used_mcp_capabilities=[capability],
            status="FAILED",
        )

    def run_mcp_evidence_skill(
        self,
        skill_input: SkillInput,
        *,
        missing_capability_message: str,
        preferred: tuple[str, ...] | None = None,
        item_keys: tuple[str, ...] | None = None,
    ) -> SkillOutput:
        capability = self.select_capability(
            skill_input.required_mcp_capabilities,
            preferred=preferred or self.preferred_capabilities,
        )
        if capability is None:
            return self.failed_missing_capability(
                skill_input,
                missing_capability_message,
            )

        response = self.call_mcp(capability, skill_input.payload)
        if not response.get("ok"):
            return self.failed_mcp_call(skill_input, capability, response)

        entities = self.normalize_entities_from_input(skill_input)
        items = self.items_from_response(
            response.get("data", {}),
            item_keys=item_keys or self.response_item_keys,
        )

        evidence_items, errors = self.build_soft_evidence_items(
            items, capability, entities, skill_input,
        )

        response_data = response.get("data", {})
        status = self._status_from_evidence(evidence_items, errors)

        if status == "FAILED":
            return self.empty_result_output(
                skill_input, capability, response_data, errors,
            )

        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            evidence_items=evidence_items,
            artifacts={"mcp_response": response_data},
            errors=errors,
            used_mcp_capabilities=[capability],
            status=status,
        )

    @staticmethod
    def _status_from_evidence(
        evidence_items: list[EvidenceItem],
        errors: list[dict[str, Any]],
    ) -> str:
        if not evidence_items:
            return "FAILED"
        if errors:
            return "PARTIAL"
        return "OK"
