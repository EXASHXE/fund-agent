"""Runtime skill surface architecture tests.

Verifies that runtime skills follow architectural boundaries:
- news_research and sentiment_analysis inherit from MCPAdapterSkill
- thesis_generation uses BaseSkillRuntime or its helpers
- mcp_adapter_skill.py does not import provider SDKs
- base.py does not import provider SDKs/network clients
- no runtime skill imports OpenCode plugin
- thesis_generation does not import decision_support
- thesis_generation does not produce formal decision artifacts
- fund_analysis and decision_support runtime paths still resolve
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from src.skills_runtime.base import BaseSkillRuntime
from src.skills_runtime.mcp_adapter_skill import MCPAdapterSkill
from src.skills_runtime.news_research import NewsResearchSkill
from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill
from src.skills_runtime.thesis_generation import ThesisGenerationSkill
from src.schemas.skill import SkillInput, SkillOutput

ROOT = Path(__file__).resolve().parents[2]

BANNED_PROVIDER_IMPORTS = [
    "tavily", "finnhub", "exa", "firecrawl", "akshare",
    "openai", "anthropic", "langchain", "requests", "httpx",
    "aiohttp", "urllib3", "socket",
]


def _source_text(module_name: str) -> str:
    mod = importlib.import_module(module_name)
    return Path(mod.__file__).read_text(encoding="utf-8")


def _import_lines(source: str) -> list[str]:
    return [line for line in source.splitlines() if line.strip().startswith(("import ", "from "))]


class TestMCPAdapterInheritance:
    def test_news_research_inherits_mcp_adapter(self):
        assert issubclass(NewsResearchSkill, MCPAdapterSkill)

    def test_sentiment_analysis_inherits_mcp_adapter(self):
        assert issubclass(SentimentAnalysisSkill, MCPAdapterSkill)

    def test_mcp_adapter_inherits_base(self):
        assert issubclass(MCPAdapterSkill, BaseSkillRuntime)


class TestThesisGenerationBase:
    def test_thesis_generation_inherits_base(self):
        assert issubclass(ThesisGenerationSkill, BaseSkillRuntime)


class TestNoProviderSDKImports:
    @pytest.mark.parametrize("module_name", [
        "src.skills_runtime.mcp_adapter_skill",
        "src.skills_runtime.base",
        "src.skills_runtime.thesis_generation",
        "src.skills_runtime.news_research",
        "src.skills_runtime.sentiment_analysis",
    ])
    def test_no_provider_imports(self, module_name: str):
        source = _source_text(module_name)
        import_lines = _import_lines(source)
        for line in import_lines:
            for banned in BANNED_PROVIDER_IMPORTS:
                assert banned not in line, (
                    f"{module_name} contains banned import '{banned}' in line: {line}"
                )


class TestNoOpenCodePluginImports:
    @pytest.mark.parametrize("module_name", [
        "src.skills_runtime.news_research",
        "src.skills_runtime.sentiment_analysis",
        "src.skills_runtime.thesis_generation",
        "src.skills_runtime.mcp_adapter_skill",
        "src.skills_runtime.base",
    ])
    def test_no_opencode_plugin_import(self, module_name: str):
        source = _source_text(module_name)
        assert "opencode" not in source.lower(), (
            f"{module_name} references OpenCode plugin"
        )


class TestThesisGenerationBoundaries:
    def test_thesis_does_not_import_decision_support(self):
        source = _source_text("src.skills_runtime.thesis_generation")
        import_lines = _import_lines(source)
        for line in import_lines:
            assert "decision_support" not in line, (
                f"thesis_generation imports decision_support: {line}"
            )

    def test_thesis_does_not_produce_formal_decisions(self):
        skill = ThesisGenerationSkill()
        si = SkillInput(
            task_id="test",
            step_id="test",
            skill_name="thesis_generation",
            payload={
                "thesis_question": "Test thesis",
                "evidence_items": [
                    {"claim": "Support", "direction": "positive", "source_type": "test"},
                ],
            },
        )
        result = skill.run(si)
        assert result.status in ("OK", "PARTIAL", "FAILED")
        artifacts = result.artifacts
        for key in ("decision", "decisions", "execution_ledger", "execution_ledgers"):
            assert key not in artifacts, f"ThesisGenerationSkill produced forbidden artifact '{key}'"

    def test_thesis_draft_has_decision_boundary_note(self):
        skill = ThesisGenerationSkill()
        si = SkillInput(
            task_id="test",
            step_id="test",
            skill_name="thesis_generation",
            payload={"thesis_question": "Test"},
        )
        result = skill.run(si)
        draft = result.artifacts.get("thesis_draft", {})
        assert "decision_boundary_note" in draft
        assert "decision_support" in draft["decision_boundary_note"]


class TestRuntimePathsResolve:
    def test_fund_analysis_imports(self):
        from src.skills_runtime.fund_analysis import FundAnalysisSkill
        assert FundAnalysisSkill is not None

    def test_decision_support_imports(self):
        from src.skills_runtime.decision_support import DecisionSupportSkill
        assert DecisionSupportSkill is not None

    def test_news_research_imports(self):
        from src.skills_runtime.news_research import NewsResearchSkill
        assert NewsResearchSkill is not None

    def test_sentiment_analysis_imports(self):
        from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill
        assert SentimentAnalysisSkill is not None

    def test_thesis_generation_imports(self):
        from src.skills_runtime.thesis_generation import ThesisGenerationSkill
        assert ThesisGenerationSkill is not None
