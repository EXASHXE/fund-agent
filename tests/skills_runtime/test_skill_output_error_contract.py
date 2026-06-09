"""Runtime-wide skill output error contract tests.

Verifies that all runtime skills produce canonical SkillError-shaped
error dictionaries in SkillOutput.errors when given invalid inputs.
"""

from __future__ import annotations

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.base import BaseSkillRuntime
from src.skills_runtime.fund_analysis.skill import FundAnalysisSkill
from src.skills_runtime.decision_support.skill import DecisionSupportSkill
from src.skills_runtime.news_research import NewsResearchSkill
from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill
from src.skills_runtime.thesis_generation import ThesisGenerationSkill


def _make_input(skill_name: str, payload: dict | None = None) -> SkillInput:
    return SkillInput(
        task_id="test-task",
        step_id="test-step",
        skill_name=skill_name,
        payload=payload or {},
    )


def _assert_canonical_errors(output: SkillOutput) -> None:
    assert isinstance(output.errors, list), f"errors is not a list: {type(output.errors)}"
    for err in output.errors:
        assert isinstance(err, dict), f"error is not a dict: {type(err)}"
        assert "code" in err, f"error missing 'code': {err}"
        assert "message" in err, f"error missing 'message': {err}"
        assert "details" in err, f"error missing 'details': {err}"
        assert "recoverable" in err, f"error missing 'recoverable': {err}"
        assert isinstance(err["code"], str) and len(err["code"]) > 0
        assert isinstance(err["message"], str) and len(err["message"]) > 0
        assert isinstance(err["details"], dict), f"details not dict: {type(err['details'])}"
        assert isinstance(err["recoverable"], bool), f"recoverable not bool: {type(err['recoverable'])}"


class TestFundAnalysisErrorContract:
    def test_invalid_payload_returns_canonical_errors(self):
        skill = FundAnalysisSkill()
        output = skill.run(_make_input("fund_analysis", "not a dict"))
        _assert_canonical_errors(output)

    def test_empty_positions_returns_canonical_errors(self):
        skill = FundAnalysisSkill()
        output = skill.run(_make_input("fund_analysis", {"portfolio": {"positions": []}}))
        if output.errors:
            _assert_canonical_errors(output)


class TestDecisionSupportErrorContract:
    def test_missing_evidence_graph_returns_canonical_errors(self):
        skill = DecisionSupportSkill()
        output = skill.run(_make_input("decision_support", {"requested_action": "BUY"}))
        _assert_canonical_errors(output)


class TestThesisGenerationErrorContract:
    def test_invalid_payload_returns_canonical_errors(self):
        skill = ThesisGenerationSkill()
        output = skill.run(_make_input("thesis_generation", "not a dict"))
        _assert_canonical_errors(output)


class TestNewsResearchErrorContract:
    def test_missing_mcp_adapter_returns_canonical_errors(self):
        skill = NewsResearchSkill(mcp_adapter=None)
        output = skill.run(_make_input("news_research", {"query": "test"}))
        _assert_canonical_errors(output)


class TestSentimentAnalysisErrorContract:
    def test_missing_mcp_adapter_returns_canonical_errors(self):
        skill = SentimentAnalysisSkill(mcp_adapter=None)
        output = skill.run(_make_input("sentiment_analysis", {"query": "test"}))
        _assert_canonical_errors(output)


class TestBaseSkillRuntimeErrorContract:
    def test_failed_output_returns_canonical_errors(self):
        base = BaseSkillRuntime()
        si = _make_input("test_skill")
        output = base.failed_output(si, "TEST_ERROR", "something failed")
        _assert_canonical_errors(output)

    def test_make_skill_error_returns_canonical(self):
        base = BaseSkillRuntime()
        err = base.make_skill_error("CODE", "msg", {"k": 1}, recoverable=False)
        assert isinstance(err, dict)
        assert err["code"] == "CODE"
        assert err["message"] == "msg"
        assert err["details"] == {"k": 1}
        assert err["recoverable"] is False

    def test_normalize_error_skill_error_object(self):
        base = BaseSkillRuntime()
        from src.schemas.skill import SkillError
        err = base.normalize_error(SkillError(code="X", message="m"))
        assert err["code"] == "X"
        assert err["recoverable"] is True

    def test_normalize_error_dict(self):
        base = BaseSkillRuntime()
        err = base.normalize_error({"code": "Y", "message": "n"})
        assert err["code"] == "Y"
        assert err["recoverable"] is True

    def test_normalize_error_string(self):
        base = BaseSkillRuntime()
        err = base.normalize_error("string error")
        assert err["code"] == "RUNTIME_ERROR"
        assert err["message"] == "string error"

    def test_normalize_error_exception(self):
        base = BaseSkillRuntime()
        err = base.normalize_error(ValueError("bad"), code="INTERNAL_ERROR")
        assert err["code"] == "INTERNAL_ERROR"
        assert err["message"] == "bad"
        assert err["details"] == {"exception_type": "ValueError"}

    def test_normalize_errors_list(self):
        base = BaseSkillRuntime()
        result = base.normalize_errors([
            {"code": "A", "message": "a"},
            "string",
        ])
        assert len(result) == 2
        assert result[0]["code"] == "A"
        assert result[1]["code"] == "RUNTIME_ERROR"

    def test_normalize_errors_none(self):
        base = BaseSkillRuntime()
        assert base.normalize_errors(None) == []
