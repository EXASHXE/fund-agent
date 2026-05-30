"""SkillInput / SkillOutput contract tests."""

from __future__ import annotations

import json

import pytest

from src.schemas.skill import SkillInput, SkillOutput


def test_skill_input_is_json_serializable():
    skill_input = SkillInput(
        task_id="task-1",
        step_id="step-1",
        skill_name="NewsResearch",
        payload={"query": "fund news"},
        kg_context={"fund_codes": ["110011"]},
        required_mcp_capabilities=["web_search"],
        evidence_context=["ev-1"],
        metadata={"iteration": 1},
    )

    json.dumps(skill_input.to_dict())


def test_skill_output_is_json_serializable():
    output = SkillOutput(
        step_id="step-1",
        skill_name="NewsResearch",
        artifacts={"count": 1},
        warnings=["partial source coverage"],
        used_mcp_capabilities=["web_search"],
    )

    json.dumps(output.to_dict())


def test_skill_output_does_not_contain_decision():
    output = SkillOutput(artifacts={"thesis_draft": "draft"})

    data = output.to_dict()
    assert "decision" not in data
    assert "final_thesis" not in data


def test_failed_skill_output_has_structured_errors():
    output = SkillOutput(
        status="FAILED",
        errors=[{"type": "RuntimeError", "message": "boom"}],
    )

    assert output.errors[0]["type"] == "RuntimeError"
    assert output.status == "FAILED"


def test_skill_output_status_values_are_constrained():
    for status in ("OK", "PARTIAL", "FAILED"):
        assert SkillOutput(status=status).status == status

    with pytest.raises(ValueError):
        SkillOutput(status="PASS")
