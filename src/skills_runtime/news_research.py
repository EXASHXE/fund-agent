"""News research skill runtime.

This handler is adapter-only: it calls host-injected MCP capabilities and
converts structured results into SoftEvidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.skill import SkillError, SkillInput, SkillOutput
from src.skills_runtime.mcp_adapter_skill import MCPAdapterSkill
from src.tools.evidence.builders import build_soft_evidence_from_mcp_result


class NewsResearchSkill(MCPAdapterSkill):
    """Adapter-only news research skill."""

    preferred_capabilities = ("financial_news", "web_search")
    response_item_keys = ("items", "results", "articles", "news")
    default_entity = "research_task"

    def __init__(self, mcp_adapter: Any = None) -> None:
        super().__init__(mcp_adapter=mcp_adapter)

    def run(self, skill_input: SkillInput) -> SkillOutput:
        capability = self.select_capability(
            skill_input.required_mcp_capabilities,
            preferred=self.preferred_capabilities,
        )
        if capability is None:
            return self.failed_missing_capability(
                skill_input,
                "NewsResearch requires financial_news or web_search",
            )

        response = self.call_mcp(capability, skill_input.payload)
        if not response.get("ok"):
            return self.failed_mcp_call(skill_input, capability, response)

        entities = self.normalize_entities_from_input(skill_input)
        items = self.items_from_response(
            response.get("data", {}),
            item_keys=self.response_item_keys,
        )

        evidence_items, errors = self._build_news_evidence_items(
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

    def _build_news_evidence_items(
        self,
        items: list[dict],
        capability: str,
        entities: list[str],
        skill_input: SkillInput,
    ) -> tuple[list, list[dict[str, Any]]]:
        evidence_items = []
        errors = []
        for item in items:
            try:
                evidence_items.append(
                    build_soft_evidence_from_mcp_result(
                        source_type=item.get("source_type") or capability,
                        timestamp=item.get("timestamp") or datetime.now(),
                        related_entities=item.get("related_entities") or entities,
                        claim=item.get("claim") or item.get("title") or "News item",
                        value=item,
                        confidence_weight=item.get("confidence_weight", item.get("confidence", 0.5)),
                        direction=item.get("direction", "neutral"),
                        provenance={
                            "mcp_capability": capability,
                            "skill_name": skill_input.skill_name,
                        },
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
