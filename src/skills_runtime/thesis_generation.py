"""Thesis generation skill runtime.

This skill creates draft artifacts only. Formal decisions are produced by
DecisionEngine after EvidenceGraph compilation and Critic review.
"""

from __future__ import annotations

from src.schemas.skill import SkillInput, SkillOutput


class ThesisGenerationSkill:
    """Artifact-only thesis draft skill."""

    mcp_adapter = None
    tool_registry = None

    def run(self, skill_input: SkillInput) -> SkillOutput:
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            artifacts={
                "thesis_draft": {
                    "task_id": skill_input.task_id,
                    "evidence_context": list(skill_input.evidence_context),
                    "note": "Draft only; DecisionEngine owns formal decisions.",
                }
            },
            status="OK",
        )
