"""Sentiment analysis skill runtime.

This handler is adapter-only and converts host MCP sentiment results into
SoftEvidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.evidence import EvidenceItem
from src.schemas.skill import SkillError, SkillInput, SkillOutput
from src.skills_runtime.mcp_adapter_skill import MCPAdapterSkill
from src.tools.evidence.builders import build_soft_evidence_from_sentiment


class SentimentAnalysisSkill(MCPAdapterSkill):
    """Adapter-only sentiment research skill."""

    preferred_capabilities = ("social_sentiment", "trend_radar", "reddit_search")
    response_item_keys = ("items", "results", "sentiments", "signals")
    default_entity = "research_task"

    def __init__(self, mcp_adapter: Any = None) -> None:
        super().__init__(mcp_adapter=mcp_adapter)

    def run(self, skill_input: SkillInput) -> SkillOutput:
        return self.run_mcp_evidence_skill(
            skill_input,
            missing_capability_message="SentimentResearch requires social_sentiment",
        )

    def _build_single_evidence(
        self,
        item: dict,
        capability: str,
        entities: list[str],
        skill_input: SkillInput,
    ) -> EvidenceItem:
        score = float(item.get("sentiment_score", item.get("score", 0.0)))
        return build_soft_evidence_from_sentiment(
            source_type=item.get("source_type") or capability,
            timestamp=item.get("timestamp") or datetime.now(),
            related_entities=item.get("related_entities") or entities,
            sentiment_score=score,
            claim=item.get("claim") or "Sentiment signal detected",
            direction=item.get("direction"),
            provenance={
                "mcp_capability": capability,
                "skill_name": skill_input.skill_name,
            },
        )
