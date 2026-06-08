"""Runtime contract surface architecture tests.

Verifies that runtime error helpers, tools registry, and decision boundaries
are maintained correctly.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class TestErrorNormalizationNoBannedImports:
    def test_skill_schema_no_provider_sdks(self):
        mod = importlib.import_module("src.schemas.skill")
        source = Path(mod.__file__).read_text(encoding="utf-8")
        banned = [
            "requests", "httpx", "aiohttp", "urllib3", "socket",
            "openai", "anthropic", "langchain",
            "tavily", "finnhub", "exa", "firecrawl", "reddit", "akshare",
        ]
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            for b in banned:
                assert b not in line, f"src.schemas.skill imports banned module '{b}'"

    def test_base_runtime_no_provider_sdks(self):
        mod = importlib.import_module("src.skills_runtime.base")
        source = Path(mod.__file__).read_text(encoding="utf-8")
        banned = [
            "requests", "httpx", "aiohttp", "urllib3", "socket",
            "openai", "anthropic", "langchain",
            "tavily", "finnhub", "exa", "firecrawl", "reddit", "akshare",
        ]
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            for b in banned:
                assert b not in line, f"src.skills_runtime.base imports banned module '{b}'"


class TestToolsRegistryTestsExist:
    def test_tools_registry_consistency_test_exists(self):
        path = ROOT / "tests" / "skillpack" / "test_tools_registry_consistency.py"
        assert path.exists()

    def test_tools_inventory_docs_test_exists(self):
        path = ROOT / "tests" / "docs" / "test_tools_inventory_docs.py"
        assert path.exists()


class TestToolsInventoryDocExists:
    def test_tools_inventory_doc_exists(self):
        path = ROOT / "docs" / "tools-inventory.md"
        assert path.exists()


class TestNoRuntimeSkillImportsProviderSDKs:
    @pytest.mark.parametrize("module_name", [
        "src.skills_runtime.fund_analysis.skill",
        "src.skills_runtime.decision_support.skill",
        "src.skills_runtime.news_research",
        "src.skills_runtime.sentiment_analysis",
        "src.skills_runtime.thesis_generation",
    ])
    def test_no_provider_sdk_imports(self, module_name: str):
        mod = importlib.import_module(module_name)
        source = Path(mod.__file__).read_text(encoding="utf-8")
        banned = [
            "requests", "httpx", "aiohttp", "urllib3", "socket",
            "openai", "anthropic", "langchain",
            "tavily", "finnhub", "exa", "firecrawl", "reddit", "akshare",
        ]
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            for b in banned:
                assert b not in line, f"{module_name} imports banned module '{b}'"


class TestDecisionBoundary:
    def test_only_decision_support_produces_decision(self):
        from src.skills_runtime.fund_analysis.skill import FundAnalysisSkill
        from src.skills_runtime.thesis_generation import ThesisGenerationSkill
        from src.skills_runtime.news_research import NewsResearchSkill
        from src.skills_runtime.sentiment_analysis import SentimentAnalysisSkill

        for cls in [FundAnalysisSkill, ThesisGenerationSkill, NewsResearchSkill, SentimentAnalysisSkill]:
            source = Path(cls.__module__.replace(".", "/") + ".py")
            if not source.exists():
                mod = importlib.import_module(cls.__module__)
                source = Path(mod.__file__)
            text = source.read_text(encoding="utf-8")
            assert "Decision(" not in text or "decision_support" in text, (
                f"{cls.__name__} appears to produce formal Decision objects"
            )
            assert "ExecutionLedger(" not in text or "decision_support" in text, (
                f"{cls.__name__} appears to produce formal ExecutionLedger objects"
            )
