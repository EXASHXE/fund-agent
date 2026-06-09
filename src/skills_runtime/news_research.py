"""News research skill runtime.

This handler is adapter-only: it calls host-injected MCP capabilities and
converts structured results into SoftEvidence.
"""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.mcp_adapter_skill import MCPAdapterSkill


class NewsResearchSkill(MCPAdapterSkill):
    """Adapter-only news research skill."""

    preferred_capabilities = ("financial_news", "web_search")
    response_item_keys = ("items", "results", "articles", "news")
    default_entity = "research_task"

    def __init__(self, mcp_adapter: Any = None) -> None:
        super().__init__(mcp_adapter=mcp_adapter)

    def run(self, skill_input: SkillInput) -> SkillOutput:
        return self.run_mcp_evidence_skill(
            skill_input,
            missing_capability_message="NewsResearch requires financial_news or web_search",
        )

    def _build_single_evidence(self, item, capability, entities, skill_input):
        from src.tools.evidence.builders import build_soft_evidence_from_mcp_result
        from datetime import datetime

        return build_soft_evidence_from_mcp_result(
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
