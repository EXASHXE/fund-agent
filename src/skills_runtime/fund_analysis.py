"""Fund analysis skill runtime.

This skill is intentionally local-only. It emits HardEvidence from structured
task/KG inputs and does not call MCP, network, or LLM providers.
"""

from __future__ import annotations

from src.schemas.skill import SkillInput, SkillOutput
from src.tools.evidence.builders import build_hard_evidence_from_metric


class FundAnalysisSkill:
    """Local quant/fund analysis skill."""

    mcp_adapter = None
    tool_registry = None

    def run(self, skill_input: SkillInput) -> SkillOutput:
        entities = _entities_from_input(skill_input)
        evidence_items = []
        errors = []
        for entity in entities:
            try:
                metric_value = {
                    "fund": entity,
                    "fund_count": len(entities),
                    "source": "local_quant_tools",
                }
                evidence_items.append(
                    build_hard_evidence_from_metric(
                        metric_name="local_quant_tools",
                        metric_value=metric_value,
                        claim=f"Local quant baseline generated for {entity}",
                        related_entities=[entity],
                        direction="neutral",
                        provenance={
                            "skill_name": skill_input.skill_name,
                            "tool": "local_quant_tools",
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
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            evidence_items=evidence_items,
            errors=errors,
            status="OK" if evidence_items and not errors else "FAILED",
        )


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
