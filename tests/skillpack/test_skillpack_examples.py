"""Golden skillpack example tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput

EXAMPLE_DIR = Path("skillpack/examples")


def test_all_skillpack_examples_are_valid_json():
    for path in EXAMPLE_DIR.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_all_skill_input_examples_have_required_fields():
    required = {"task_id", "step_id", "skill_name", "payload"}
    input_files = [
        "news_research_input.json",
        "fund_analysis_input.json",
        "sentiment_analysis_input.json",
        "decision_support_input.json",
    ]
    for fname in input_files:
        data = _load(fname)
        missing = required - set(data.keys())
        assert not missing, f"{fname} missing fields: {missing}"


def test_news_research_example_matches_skill_input_shape():
    data = _load("news_research_input.json")
    skill_input = SkillInput(**data)

    assert skill_input.skill_name == "news_research"
    assert "financial_news" in skill_input.required_mcp_capabilities
    assert skill_input.payload["mock_mcp_response"]["items"]


def test_fund_analysis_example_matches_skill_input_shape():
    data = _load("fund_analysis_input.json")
    skill_input = SkillInput(**data)

    assert skill_input.skill_name == "fund_analysis"
    assert skill_input.required_mcp_capabilities == []
    assert "portfolio" in skill_input.payload
    assert "nav_history" in skill_input.payload
    assert skill_input.payload["portfolio"]["positions"][0]["fund_code"] == "110011"


def test_sentiment_analysis_example_matches_skill_input_shape():
    data = _load("sentiment_analysis_input.json")
    skill_input = SkillInput(**data)

    assert skill_input.skill_name == "sentiment_analysis"
    assert "social_sentiment" in skill_input.required_mcp_capabilities


def test_decision_support_example_matches_skill_input_shape():
    data = _load("decision_support_input.json")
    skill_input = SkillInput(**data)

    assert skill_input.skill_name == "decision_support"
    assert "evidence_graph" in skill_input.payload
    assert skill_input.required_mcp_capabilities == []


def test_decision_support_output_contains_decision_and_ledger():
    data = _load("decision_support_output.json")

    assert data["status"] == "OK"
    assert "decision" in data["artifacts"]
    assert "execution_ledger" in data["artifacts"]
    assert data["artifacts"]["decision"]["rationale_anchor"]
    assert data["artifacts"]["execution_ledger"]["decisions"]


def test_examples_do_not_reference_research_os_as_required_path():
    serialized = "\n".join(path.read_text(encoding="utf-8") for path in EXAMPLE_DIR.glob("*.json"))

    assert "src.core.research_os" not in serialized
    assert "src/workflows/research_os.py" not in serialized
    assert "required_research_os" not in serialized


def _load(filename: str) -> dict:
    return json.loads((EXAMPLE_DIR / filename).read_text(encoding="utf-8"))
