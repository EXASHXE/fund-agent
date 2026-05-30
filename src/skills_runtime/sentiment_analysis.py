"""Sentiment analysis skill runtime.

This handler is adapter-only and converts host MCP sentiment results into
SoftEvidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.schemas.skill import SkillError, SkillInput, SkillOutput
from src.tools.evidence.builders import build_soft_evidence_from_sentiment


class SentimentAnalysisSkill:
    """Adapter-only sentiment research skill."""

    def __init__(self, mcp_adapter: Any = None) -> None:
        self.mcp_adapter = mcp_adapter

    def run(self, skill_input: SkillInput) -> SkillOutput:
        capability = self._select_capability(
            skill_input.required_mcp_capabilities,
            preferred=("social_sentiment", "trend_radar", "reddit_search"),
        )
        if capability is None:
            return self._failed(
                skill_input,
                "MISSING_MCP_CAPABILITY",
                "SentimentResearch requires social_sentiment",
            )

        response = self.mcp_adapter.call(capability, skill_input.payload)
        if not response.get("ok"):
            return self._failed(
                skill_input,
                "MCP_CALL_FAILED",
                response.get("error", {}).get("message", "MCP call failed"),
                details={"capability": capability, "error": response.get("error", {})},
            )

        evidence_items = []
        errors = []
        entities = _entities_from_input(skill_input)
        for item in _items_from_response(response.get("data", {})):
            try:
                score = float(item.get("sentiment_score", item.get("score", 0.0)))
                evidence_items.append(
                    build_soft_evidence_from_sentiment(
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

        status = "OK" if evidence_items and not errors else "PARTIAL"
        if not evidence_items:
            status = "FAILED"
            if not errors:
                errors.append(
                    SkillError(
                        code="EMPTY_RESULT",
                        message="SentimentResearch returned no evidence items",
                        details={"skill_name": skill_input.skill_name},
                    ).to_dict()
                )
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
        details: dict | None = None,
    ) -> SkillOutput:
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            warnings=[message],
            errors=[
                SkillError(
                    code=error_type,
                    message=message,
                    details=details or {"skill_name": skill_input.skill_name},
                ).to_dict()
            ],
            status="FAILED",
        )


def _items_from_response(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    for key in ("items", "results", "sentiments", "signals"):
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
