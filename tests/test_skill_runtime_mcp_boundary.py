"""Skill runtime MCP boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.news_research import NewsResearchSkill
from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill
from src.skills_runtime.thesis_generation import ThesisGenerationSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability


def test_news_research_skill_uses_mcp_adapter_only():
    adapter = _adapter(
        "financial_news",
        {"items": [_news_item()]},
    )
    output = NewsResearchSkill(mcp_adapter=adapter).run(
        _input("NewsResearch", required=["financial_news"])
    )

    assert output.status == "OK"
    assert output.used_mcp_capabilities == ["financial_news"]


def test_news_research_missing_mcp_returns_structured_error():
    output = NewsResearchSkill(mcp_adapter=InMemoryMCPHostAdapter()).run(
        _input("NewsResearch", required=["financial_news"])
    )

    assert output.status == "FAILED"
    assert output.errors[0]["type"] == "MissingMCPCapability"


def test_news_research_outputs_soft_evidence():
    adapter = _adapter("financial_news", {"items": [_news_item()]})
    output = NewsResearchSkill(mcp_adapter=adapter).run(
        _input("NewsResearch", required=["financial_news"])
    )

    assert output.evidence_items
    assert output.evidence_items[0].evidence_type == "SoftEvidence"
    assert output.evidence_items[0].source_type == "financial_news"


def test_sentiment_skill_uses_mcp_adapter_only():
    adapter = _adapter(
        "social_sentiment",
        {"items": [_sentiment_item()]},
    )
    output = SentimentAnalysisSkill(mcp_adapter=adapter).run(
        _input("SentimentResearch", required=["social_sentiment"])
    )

    assert output.status == "OK"
    assert output.used_mcp_capabilities == ["social_sentiment"]


def test_sentiment_missing_mcp_returns_structured_error():
    output = SentimentAnalysisSkill(mcp_adapter=InMemoryMCPHostAdapter()).run(
        _input("SentimentResearch", required=["social_sentiment"])
    )

    assert output.status == "FAILED"
    assert output.errors[0]["type"] == "MissingMCPCapability"


def test_fund_analysis_outputs_hard_evidence():
    output = FundAnalysisSkill().run(_input("QuantRiskAnalysis"))

    assert output.evidence_items
    assert output.evidence_items[0].evidence_type == "HardEvidence"
    assert output.evidence_items[0].confidence_weight == 1.0


def test_fund_analysis_does_not_import_network_or_llm():
    imports = _imports_from(Path("src/skills_runtime/fund_analysis.py"))
    forbidden = {"requests", "httpx", "aiohttp", "openai", "anthropic", "langchain"}

    assert not (imports & forbidden)


def test_thesis_generation_does_not_return_decision():
    output = ThesisGenerationSkill().run(_input("ThesisGeneration"))
    data = output.to_dict()

    assert data["artifacts"]["thesis_draft"]
    assert "decision" not in data


def _adapter(capability_name: str, data: dict) -> InMemoryMCPHostAdapter:
    return InMemoryMCPHostAdapter(
        capabilities=[
            MCPCapability(
                name=capability_name,
                input_schema={},
                output_schema={},
            )
        ],
        handlers={capability_name: lambda _: data},
    )


def _input(skill_name: str, required: list[str] | None = None) -> SkillInput:
    return SkillInput(
        task_id="skill-runtime",
        step_id="step-1",
        skill_name=skill_name,
        payload={"related_entities": ["fund:110011"]},
        kg_context={"fund_codes": ["110011"]},
        required_mcp_capabilities=required or [],
    )


def _news_item() -> dict:
    return {
        "claim": "Fund holdings received positive coverage",
        "timestamp": "2026-05-30T00:00:00",
        "related_entities": ["fund:110011"],
        "confidence_weight": 0.6,
        "direction": "positive",
    }


def _sentiment_item() -> dict:
    return {
        "claim": "Social sentiment is positive",
        "timestamp": "2026-05-30T00:00:00",
        "related_entities": ["fund:110011"],
        "sentiment_score": 0.7,
    }


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports
