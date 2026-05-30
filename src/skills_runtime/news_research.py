"""News research skill runtime.

This handler is adapter-only: it calls host-injected MCP capabilities and
converts structured results into SoftEvidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.skill import SkillInput, SkillOutput
from src.tools.evidence.builders import build_soft_evidence_from_mcp_result


class NewsResearchSkill:
    """Adapter-only news research skill."""

    def __init__(self, mcp_adapter: Any = None) -> None:
        self.mcp_adapter = mcp_adapter

    def run(self, skill_input: SkillInput) -> SkillOutput:
        capability = self._select_capability(
            skill_input.required_mcp_capabilities,
            preferred=("financial_news", "web_search"),
        )
        if capability is None:
            return self._failed(
                skill_input,
                "MissingMCPCapability",
                "NewsResearch requires financial_news or web_search",
            )

        response = self.mcp_adapter.call(capability, skill_input.payload)
        if not response.get("ok"):
            return self._failed(
                skill_input,
                response.get("error", {}).get("type", "MCPError"),
                response.get("error", {}).get("message", "MCP call failed"),
            )

        evidence_items = []
        errors = []
        entities = _entities_from_input(skill_input)
        for item in _items_from_response(response.get("data", {})):
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
                    {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "skill_name": skill_input.skill_name,
                    }
                )

        status = "OK" if evidence_items and not errors else "PARTIAL"
        if not evidence_items:
            status = "FAILED"
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            evidence_items=evidence_items,
            artifacts={"mcp_response": response.get("data", {})},
            errors=errors,
            used_mcp_capabilities=[capability],
            status=status,
        )

    def _select_capability(
        self,
        required: list[str],
        preferred: tuple[str, ...],
    ) -> str | None:
        if self.mcp_adapter is None:
            return None
        candidates = list(dict.fromkeys(list(preferred) + list(required)))
        for name in candidates:
            if self.mcp_adapter.has_capability(name):
                return name
        return None

    def _failed(
        self,
        skill_input: SkillInput,
        error_type: str,
        message: str,
    ) -> SkillOutput:
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            warnings=[message],
            errors=[
                {
                    "type": error_type,
                    "message": message,
                    "skill_name": skill_input.skill_name,
                }
            ],
            status="FAILED",
        )


def _items_from_response(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    for key in ("items", "results", "articles", "news"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [data] if data else []


def _entities_from_input(skill_input: SkillInput) -> list[str]:
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
