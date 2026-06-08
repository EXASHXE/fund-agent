"""Runtime skill error shape tests.

Verifies that runtime skill error outputs produce canonical SkillError-shaped
dictionaries with code, message, details, and recoverable fields.
"""

from __future__ import annotations

from src.schemas.skill import SkillInput, SkillOutput
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
        assert isinstance(err["code"], str) and len(err["code"]) > 0, f"error code invalid: {err['code']}"
        assert isinstance(err["message"], str) and len(err["message"]) > 0, f"error message invalid: {err['message']}"
        assert isinstance(err["details"], dict), f"error details not dict: {type(err['details'])}"
        assert isinstance(err["recoverable"], bool), f"error recoverable not bool: {type(err['recoverable'])}"


class TestThesisGenerationErrorShapes:
    def test_invalid_payload_returns_canonical_errors(self):
        skill = ThesisGenerationSkill()
        output = skill.run(_make_input("thesis_generation", "not a dict"))
        _assert_canonical_errors(output)


class TestDecisionSupportErrorShapes:
    def test_missing_evidence_graph_returns_canonical_errors(self):
        skill = DecisionSupportSkill()
        output = skill.run(_make_input("decision_support", {"requested_action": "BUY"}))
        _assert_canonical_errors(output)


class TestNewsResearchErrorShapes:
    def test_missing_mcp_adapter_returns_canonical_errors(self):
        skill = NewsResearchSkill(mcp_adapter=None)
        output = skill.run(_make_input("news_research", {"query": "test"}))
        _assert_canonical_errors(output)


class TestSentimentAnalysisErrorShapes:
    def test_missing_mcp_adapter_returns_canonical_errors(self):
        skill = SentimentAnalysisSkill(mcp_adapter=None)
        output = skill.run(_make_input("sentiment_analysis", {"query": "test"}))
        _assert_canonical_errors(output)


class TestFundAnalysisErrorShapes:
    def test_invalid_payload_returns_canonical_errors(self):
        skill = FundAnalysisSkill()
        output = skill.run(_make_input("fund_analysis", "not a dict"))
        _assert_canonical_errors(output)

    def test_empty_positions_returns_canonical_errors(self):
        skill = FundAnalysisSkill()
        output = skill.run(_make_input("fund_analysis", {"portfolio": {"positions": []}}))
        if output.errors:
            _assert_canonical_errors(output)
