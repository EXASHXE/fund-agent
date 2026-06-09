"""Standard SkillError contract tests."""

from __future__ import annotations

import json

from src.schemas.skill import SkillError, SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.news_research import NewsResearchSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability


def test_skill_error_is_json_serializable():
    error = SkillError(
        code="INTERNAL_ERROR",
        message="boom",
        details={"skill_name": "test"},
    )

    json.dumps(error.to_dict())


def test_missing_mcp_uses_standard_error_code():
    output = NewsResearchSkill(mcp_adapter=InMemoryMCPHostAdapter()).run(
        _news_input(required=["financial_news"])
    )

    assert output.errors[0]["code"] == "MISSING_MCP_CAPABILITY"


def test_invalid_input_uses_standard_error_code():
    output = DecisionSupportSkill().run(
        SkillInput(
            task_id="skill-error",
            step_id="decision",
            skill_name="decision_support",
            payload={},
        )
    )

    assert output.errors[0]["code"] == "INVALID_INPUT"


def test_mcp_call_failed_uses_standard_error_code():
    # Force adapter-level structured failure with no handler.
    adapter = InMemoryMCPHostAdapter(
        capabilities=[
            MCPCapability(name="financial_news", input_schema={}, output_schema={})
        ],
        handlers={},
    )

    output = NewsResearchSkill(mcp_adapter=adapter).run(
        _news_input(required=["financial_news"])
    )

    assert output.errors[0]["code"] == "MCP_CALL_FAILED"


def test_decision_support_contract_violation_uses_standard_error_code():
    output = DecisionSupportSkill().run(
        SkillInput(
            task_id="skill-error",
            step_id="decision",
            skill_name="decision_support",
            payload={
                "evidence_graph": {"items": {}, "edges": []},
                "requested_action": "BUY",
            },
        )
    )

    assert output.errors[0]["code"] == "CONTRACT_VIOLATION"


def _news_input(required: list[str]) -> SkillInput:
    return SkillInput(
        task_id="skill-error",
        step_id="news",
        skill_name="news_research",
        payload={"related_entities": ["fund:110011"]},
        required_mcp_capabilities=required,
    )
