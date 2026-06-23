"""Tests verifying FundAnalysisSkill and DecisionSupportSkill inherit BaseSkillRuntime."""

from __future__ import annotations

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.base import BaseSkillRuntime
from src.skills_runtime.decision_support.skill import DecisionSupportSkill
from src.skills_runtime.decision_support.status_stage import build_failed_output as ds_build_failed_output
from src.skills_runtime.fund_analysis.input_stage import entities_from_input as fa_entities_from_input
from src.skills_runtime.fund_analysis.skill import FundAnalysisSkill
from src.skills_runtime.fund_analysis.status_stage import failed_output as fa_failed_output


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


class TestFundAnalysisSkillInheritance:
    def test_is_instance_of_base_skill_runtime(self):
        skill = FundAnalysisSkill()
        assert isinstance(skill, BaseSkillRuntime)

    def test_has_mcp_adapter_inherited(self):
        skill = FundAnalysisSkill()
        assert hasattr(skill, "mcp_adapter")
        assert skill.mcp_adapter is None

    def test_has_tool_registry_inherited(self):
        skill = FundAnalysisSkill()
        assert hasattr(skill, "tool_registry")
        assert skill.tool_registry is None

    def test_run_with_invalid_payload_returns_failed(self):
        skill = FundAnalysisSkill()
        si = _skill_input(payload="not_a_dict", skill_name="fund_analysis")
        result = skill.run(si)
        assert isinstance(result, SkillOutput)
        assert result.status == "FAILED"


class TestDecisionSupportSkillInheritance:
    def test_is_instance_of_base_skill_runtime(self):
        skill = DecisionSupportSkill()
        assert isinstance(skill, BaseSkillRuntime)

    def test_has_mcp_adapter_inherited(self):
        skill = DecisionSupportSkill()
        assert hasattr(skill, "mcp_adapter")
        assert skill.mcp_adapter is None

    def test_has_tool_registry_inherited(self):
        skill = DecisionSupportSkill()
        assert hasattr(skill, "tool_registry")
        assert skill.tool_registry is None

    def test_init_with_decision_engine_and_ledger_builder(self):
        engine = object()
        builder = object()
        skill = DecisionSupportSkill(decision_engine=engine, ledger_builder=builder)
        assert skill.decision_engine is engine
        assert skill.ledger_builder is builder

    def test_run_without_evidence_graph_returns_failed(self):
        skill = DecisionSupportSkill()
        si = _skill_input(payload={}, skill_name="decision_support")
        result = skill.run(si)
        assert isinstance(result, SkillOutput)
        assert result.status == "FAILED"


class TestFailedOutputAutoRecoverable:
    def test_invalid_input_is_not_recoverable(self):
        si = _skill_input(skill_name="test_skill")
        out = BaseSkillRuntime.failed_output(si, "INVALID_INPUT", "bad input")
        assert out.errors[0]["recoverable"] is False

    def test_contract_violation_is_not_recoverable(self):
        si = _skill_input(skill_name="test_skill")
        out = BaseSkillRuntime.failed_output(si, "CONTRACT_VIOLATION", "violation")
        assert out.errors[0]["recoverable"] is False

    def test_internal_error_is_recoverable_by_default(self):
        si = _skill_input(skill_name="test_skill")
        out = BaseSkillRuntime.failed_output(si, "INTERNAL_ERROR", "oops")
        assert out.errors[0]["recoverable"] is True

    def test_explicit_recoverable_true_overrides_auto_detect(self):
        si = _skill_input(skill_name="test_skill")
        out = BaseSkillRuntime.failed_output(
            si, "INVALID_INPUT", "bad", recoverable=True
        )
        assert out.errors[0]["recoverable"] is True

    def test_explicit_recoverable_false_overrides_auto_detect(self):
        si = _skill_input(skill_name="test_skill")
        out = BaseSkillRuntime.failed_output(
            si, "INTERNAL_ERROR", "oops", recoverable=False
        )
        assert out.errors[0]["recoverable"] is False


class TestFailedOutputDetailsMerge:
    def test_details_merged_with_skill_name(self):
        si = _skill_input(skill_name="my_skill")
        out = BaseSkillRuntime.failed_output(
            si, "INTERNAL_ERROR", "err", details={"extra": "val"}
        )
        details = out.errors[0]["details"]
        assert details["skill_name"] == "my_skill"
        assert details["extra"] == "val"

    def test_details_defaults_to_skill_name_only(self):
        si = _skill_input(skill_name="my_skill")
        out = BaseSkillRuntime.failed_output(si, "INTERNAL_ERROR", "err")
        details = out.errors[0]["details"]
        assert details == {"skill_name": "my_skill"}

    def test_details_none_treated_as_empty(self):
        si = _skill_input(skill_name="my_skill")
        out = BaseSkillRuntime.failed_output(
            si, "INTERNAL_ERROR", "err", details=None
        )
        details = out.errors[0]["details"]
        assert details == {"skill_name": "my_skill"}


class TestEntityNormalizationStrCoercion:
    def test_integer_entities_coerced_to_strings(self):
        si = _skill_input(payload={"related_entities": [1, 2, 3]})
        result = BaseSkillRuntime.normalize_entities_from_input(si)
        assert result == ["1", "2", "3"]
        assert all(isinstance(e, str) for e in result)

    def test_mixed_type_entities_coerced_to_strings(self):
        si = _skill_input(payload={"related_entities": ["abc", 42, True]})
        result = BaseSkillRuntime.normalize_entities_from_input(si)
        assert result == ["abc", "42", "True"]

    def test_string_entities_unchanged(self):
        si = _skill_input(payload={"related_entities": ["fund:A", "fund:B"]})
        result = BaseSkillRuntime.normalize_entities_from_input(si)
        assert result == ["fund:A", "fund:B"]


class TestFundAnalysisStatusStageDelegation:
    def test_failed_output_delegates_to_base(self):
        si = _skill_input(skill_name="fund_analysis")
        out = fa_failed_output(si, "INVALID_INPUT", "bad payload")
        assert out.status == "FAILED"
        assert out.errors[0]["code"] == "INVALID_INPUT"
        assert out.errors[0]["recoverable"] is False
        assert out.errors[0]["details"]["skill_name"] == "fund_analysis"

    def test_failed_output_recoverable_code(self):
        si = _skill_input(skill_name="fund_analysis")
        out = fa_failed_output(si, "INTERNAL_ERROR", "oops")
        assert out.errors[0]["recoverable"] is True


class TestDecisionSupportStatusStageDelegation:
    def test_build_failed_output_delegates_to_base(self):
        si = _skill_input(skill_name="decision_support")

        class ContractError(ValueError):
            code = "CONTRACT_VIOLATION"

        exc = ContractError("missing evidence graph")
        out = ds_build_failed_output(si, exc)
        assert out.status == "FAILED"
        assert out.errors[0]["code"] == "CONTRACT_VIOLATION"
        assert out.errors[0]["recoverable"] is False
        assert out.errors[0]["details"]["skill_name"] == "decision_support"
        assert out.errors[0]["details"]["error_type"] == "ContractError"

    def test_build_failed_output_internal_error(self):
        si = _skill_input(skill_name="decision_support")
        exc = RuntimeError("something broke")
        out = ds_build_failed_output(si, exc)
        assert out.errors[0]["code"] == "INTERNAL_ERROR"
        assert out.errors[0]["recoverable"] is True


class TestFundAnalysisInputStageDelegation:
    def test_entities_from_input_delegates_to_base(self):
        si = _skill_input(payload={"related_entities": ["fund:X", "fund:Y"]})
        result = fa_entities_from_input(si)
        assert result == ["fund:X", "fund:Y"]

    def test_entities_from_input_coerces_integers(self):
        si = _skill_input(payload={"related_entities": [100, 200]})
        result = fa_entities_from_input(si)
        assert result == ["100", "200"]

    def test_entities_from_input_falls_back_to_kg_context(self):
        si = _skill_input(kg_context={"fund_codes": ["A", "B"]})
        result = fa_entities_from_input(si)
        assert result == ["fund:A", "fund:B"]

    def test_entities_from_input_falls_back_to_research_task(self):
        si = _skill_input()
        result = fa_entities_from_input(si)
        assert result == ["research_task"]
