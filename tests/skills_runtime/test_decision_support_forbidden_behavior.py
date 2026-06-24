"""Tests for decision_support forbidden behavior constraints.

Only decision_support may produce formal Decision and ExecutionLedger.
Other skills must not.
"""

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis.skill import FundAnalysisSkill
from src.skills_runtime.thesis_generation import ThesisGenerationSkill


def _skill_input(**overrides):
    defaults = {
        "task_id": "t-1",
        "step_id": "s-1",
        "skill_name": "test_skill",
        "payload": {},
        "required_mcp_capabilities": [],
        "kg_context": {},
        "evidence_context": [],
    }
    defaults.update(overrides)
    return SkillInput(**defaults)


class TestForbiddenDecisionProduction:
    """fund_analysis, thesis_generation must NOT produce Decision or ExecutionLedger artifacts."""

    def test_fund_analysis_no_decision_artifact(self):
        skill = FundAnalysisSkill()
        result = skill.run(_skill_input(
            skill_name="fund_analysis",
            payload={"related_entities": ["fund:001"]},
        ))
        if result.artifacts:
            assert "decision" not in result.artifacts
            assert "execution_ledger" not in result.artifacts

    def test_thesis_generation_no_decision_artifact(self):
        skill = ThesisGenerationSkill()
        result = skill.run(_skill_input(
            skill_name="thesis_generation",
            payload={"related_entities": ["fund:001"]},
        ))
        if result.artifacts:
            assert "decision" not in result.artifacts
            assert "execution_ledger" not in result.artifacts

    def test_fund_analysis_output_is_skill_output(self):
        from src.schemas.skill import SkillOutput
        skill = FundAnalysisSkill()
        result = skill.run(_skill_input(
            skill_name="fund_analysis",
            payload={"related_entities": ["fund:001"]},
        ))
        assert isinstance(result, SkillOutput)

    def test_thesis_generation_output_is_skill_output(self):
        from src.schemas.skill import SkillOutput
        skill = ThesisGenerationSkill()
        result = skill.run(_skill_input(
            skill_name="thesis_generation",
            payload={"related_entities": ["fund:001"]},
        ))
        assert isinstance(result, SkillOutput)
