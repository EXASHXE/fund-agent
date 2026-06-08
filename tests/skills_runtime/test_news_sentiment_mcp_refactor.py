"""Tests for news_research and sentiment_analysis MCP refactor.

Verifies that the refactored skills preserve their externally visible behavior
while inheriting from MCPAdapterSkill.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.news_research import NewsResearchSkill
from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill
from src.skills_runtime.mcp_adapter_skill import MCPAdapterSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability


def _skill_input(
    payload=None,
    required_mcp=None,
    kg_context=None,
    evidence_context=None,
    skill_name="news_research",
):
    return SkillInput(
        task_id="test-task",
        step_id="test-step",
        skill_name=skill_name,
        payload=payload or {},
        required_mcp_capabilities=required_mcp or [],
        kg_context=kg_context or {},
        evidence_context=evidence_context or [],
    )


class TestNewsResearchMCPRefactor:
    def test_inherits_from_mcp_adapter_skill(self):
        assert issubclass(NewsResearchSkill, MCPAdapterSkill)

    def test_missing_mcp_adapter_returns_failed(self):
        skill = NewsResearchSkill(mcp_adapter=None)
        si = _skill_input(skill_name="news_research")
        result = skill.run(si)
        assert result.status == "FAILED"
        assert any(e.get("code") == "MISSING_MCP_CAPABILITY" for e in result.errors)

    def test_no_capability_returns_failed(self):
        adapter = InMemoryMCPHostAdapter()
        skill = NewsResearchSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="news_research")
        result = skill.run(si)
        assert result.status == "FAILED"
        assert any(e.get("code") == "MISSING_MCP_CAPABILITY" for e in result.errors)

    def test_mcp_call_failure_returns_failed(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="financial_news", input_schema={}, output_schema={}),
            ],
        )
        skill = NewsResearchSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="news_research")
        result = skill.run(si)
        assert result.status == "FAILED"
        assert any(e.get("code") == "MCP_CALL_FAILED" for e in result.errors)

    def test_empty_response_returns_failed(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="financial_news", input_schema={}, output_schema={}),
            ],
            handlers={
                "financial_news": lambda p: {"items": []},
            },
        )
        skill = NewsResearchSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="news_research")
        result = skill.run(si)
        assert result.status == "FAILED"
        assert any(e.get("code") == "EMPTY_RESULT" for e in result.errors)

    def test_valid_response_produces_soft_evidence(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="financial_news", input_schema={}, output_schema={}),
            ],
            handlers={
                "financial_news": lambda p: {
                    "items": [
                        {
                            "claim": "Market rises",
                            "source_type": "financial_news",
                            "timestamp": datetime.now().isoformat(),
                            "related_entities": ["fund:001"],
                            "direction": "positive",
                        }
                    ]
                },
            },
        )
        skill = NewsResearchSkill(mcp_adapter=adapter)
        si = _skill_input(
            payload={"related_entities": ["fund:001"]},
            skill_name="news_research",
        )
        result = skill.run(si)
        assert result.status == "OK"
        assert len(result.evidence_items) == 1
        assert result.evidence_items[0].evidence_type == "SoftEvidence"

    def test_prefers_financial_news_over_web_search(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="financial_news", input_schema={}, output_schema={}, priority=1),
                MCPCapability(name="web_search", input_schema={}, output_schema={}, priority=2),
            ],
            handlers={
                "financial_news": lambda p: {"items": [{"claim": "News", "source_type": "financial_news", "timestamp": datetime.now().isoformat(), "related_entities": ["fund:001"], "direction": "neutral"}]},
                "web_search": lambda p: {"items": [{"claim": "Web", "source_type": "web_search", "timestamp": datetime.now().isoformat(), "related_entities": ["fund:001"], "direction": "neutral"}]},
            },
        )
        skill = NewsResearchSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="news_research")
        result = skill.run(si)
        assert result.used_mcp_capabilities == ["financial_news"]

    def test_artifacts_mcp_response_preserved(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="financial_news", input_schema={}, output_schema={}),
            ],
            handlers={
                "financial_news": lambda p: {
                    "items": [
                        {"claim": "Test", "source_type": "financial_news", "timestamp": datetime.now().isoformat(), "related_entities": ["fund:001"], "direction": "neutral"}
                    ]
                },
            },
        )
        skill = NewsResearchSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="news_research")
        result = skill.run(si)
        assert "mcp_response" in result.artifacts

    def test_used_mcp_capabilities_populated(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="web_search", input_schema={}, output_schema={}),
            ],
            handlers={
                "web_search": lambda p: {
                    "items": [{"claim": "Test", "source_type": "web_search", "timestamp": datetime.now().isoformat(), "related_entities": ["fund:001"], "direction": "neutral"}]
                },
            },
        )
        skill = NewsResearchSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="news_research")
        result = skill.run(si)
        assert result.used_mcp_capabilities == ["web_search"]


class TestSentimentAnalysisMCPRefactor:
    def test_inherits_from_mcp_adapter_skill(self):
        assert issubclass(SentimentAnalysisSkill, MCPAdapterSkill)

    def test_missing_mcp_adapter_returns_failed(self):
        skill = SentimentAnalysisSkill(mcp_adapter=None)
        si = _skill_input(skill_name="sentiment_analysis")
        result = skill.run(si)
        assert result.status == "FAILED"
        assert any(e.get("code") == "MISSING_MCP_CAPABILITY" for e in result.errors)

    def test_no_capability_returns_failed(self):
        adapter = InMemoryMCPHostAdapter()
        skill = SentimentAnalysisSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="sentiment_analysis")
        result = skill.run(si)
        assert result.status == "FAILED"

    def test_valid_response_produces_soft_evidence(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="social_sentiment", input_schema={}, output_schema={}),
            ],
            handlers={
                "social_sentiment": lambda p: {
                    "items": [
                        {
                            "claim": "Positive sentiment",
                            "source_type": "social_sentiment",
                            "timestamp": datetime.now().isoformat(),
                            "related_entities": ["fund:001"],
                            "sentiment_score": 0.6,
                            "direction": "positive",
                        }
                    ]
                },
            },
        )
        skill = SentimentAnalysisSkill(mcp_adapter=adapter)
        si = _skill_input(
            payload={"related_entities": ["fund:001"]},
            skill_name="sentiment_analysis",
        )
        result = skill.run(si)
        assert result.status == "OK"
        assert len(result.evidence_items) == 1
        assert result.evidence_items[0].evidence_type == "SoftEvidence"

    def test_prefers_social_sentiment(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="social_sentiment", input_schema={}, output_schema={}, priority=1),
                MCPCapability(name="trend_radar", input_schema={}, output_schema={}, priority=2),
            ],
            handlers={
                "social_sentiment": lambda p: {"items": [{"claim": "Sentiment", "source_type": "social_sentiment", "timestamp": datetime.now().isoformat(), "related_entities": ["fund:001"], "sentiment_score": 0.5, "direction": "neutral"}]},
                "trend_radar": lambda p: {"items": [{"claim": "Trend", "source_type": "trend_radar", "timestamp": datetime.now().isoformat(), "related_entities": ["fund:001"], "sentiment_score": 0.5, "direction": "neutral"}]},
            },
        )
        skill = SentimentAnalysisSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="sentiment_analysis")
        result = skill.run(si)
        assert result.used_mcp_capabilities == ["social_sentiment"]

    def test_artifacts_mcp_response_preserved(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="social_sentiment", input_schema={}, output_schema={}),
            ],
            handlers={
                "social_sentiment": lambda p: {
                    "items": [{"claim": "Test", "source_type": "social_sentiment", "timestamp": datetime.now().isoformat(), "related_entities": ["fund:001"], "sentiment_score": 0.5, "direction": "neutral"}]
                },
            },
        )
        skill = SentimentAnalysisSkill(mcp_adapter=adapter)
        si = _skill_input(skill_name="sentiment_analysis")
        result = skill.run(si)
        assert "mcp_response" in result.artifacts


class TestNoProviderNetworkImports:
    def test_news_research_no_provider_imports(self):
        import importlib
        mod = importlib.import_module("src.skills_runtime.news_research")
        source = open(mod.__file__, encoding="utf-8").read()
        import_lines = [l for l in source.splitlines() if l.strip().startswith(("import ", "from "))]
        banned = ["tavily", "finnhub", "exa", "firecrawl", "akshare", "openai", "anthropic", "langchain", "requests", "httpx", "aiohttp", "urllib3", "socket"]
        for line in import_lines:
            for word in banned:
                assert word not in line, f"news_research contains banned import: {word}"

    def test_sentiment_analysis_no_provider_imports(self):
        import importlib
        mod = importlib.import_module("src.skills_runtime.sentiment_analysis")
        source = open(mod.__file__, encoding="utf-8").read()
        import_lines = [l for l in source.splitlines() if l.strip().startswith(("import ", "from "))]
        banned = ["tavily", "finnhub", "exa", "firecrawl", "akshare", "openai", "anthropic", "langchain", "requests", "httpx", "aiohttp", "urllib3", "socket"]
        for line in import_lines:
            for word in banned:
                assert word not in line, f"sentiment_analysis contains banned import: {word}"

    def test_mcp_adapter_skill_no_provider_imports(self):
        import importlib
        mod = importlib.import_module("src.skills_runtime.mcp_adapter_skill")
        source = open(mod.__file__, encoding="utf-8").read()
        import_lines = [l for l in source.splitlines() if l.strip().startswith(("import ", "from "))]
        banned = ["tavily", "finnhub", "exa", "firecrawl", "akshare", "openai", "anthropic", "langchain", "requests", "httpx", "aiohttp", "urllib3", "socket"]
        for line in import_lines:
            for word in banned:
                assert word not in line, f"mcp_adapter_skill contains banned import: {word}"
