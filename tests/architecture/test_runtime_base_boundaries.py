"""Architecture boundaries for shared runtime bases."""

from __future__ import annotations

import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports_from_file(filepath: Path) -> set[str]:
    imports: set[str] = set()
    if not filepath.is_file():
        return imports
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


_PROVIDER_NETWORK = {
    "requests", "httpx", "aiohttp", "urllib3", "socket",
    "tavily", "exa", "firecrawl", "finnhub", "reddit",
    "akshare", "openai", "anthropic", "langchain",
}

_BROKER_SERVER = {
    "flask", "fastapi", "django", "aiohttp.web", "starlette",
    "uvicorn", "gunicorn", "ccxt", "alpaca", "ib_insync",
}


def test_base_runtime_no_provider_network_or_server():
    """src/skills_runtime/base.py must not import provider SDKs, network, or server."""
    imports = _imports_from_file(SRC / "skills_runtime" / "base.py")
    violations = imports & (_PROVIDER_NETWORK | _BROKER_SERVER)
    assert not violations, f"base.py imports prohibited modules: {violations}"


def test_mcp_adapter_skill_no_provider_network_or_server():
    """src/skills_runtime/mcp_adapter_skill.py must not import provider SDKs, network, or server."""
    imports = _imports_from_file(SRC / "skills_runtime" / "mcp_adapter_skill.py")
    violations = imports & (_PROVIDER_NETWORK | _BROKER_SERVER)
    assert not violations, f"mcp_adapter_skill.py imports prohibited modules: {violations}"


def test_news_research_no_provider_network_imports():
    """news_research.py must not import provider SDKs or network clients."""
    imports = _imports_from_file(SRC / "skills_runtime" / "news_research.py")
    violations = imports & _PROVIDER_NETWORK
    assert not violations, f"news_research.py imports prohibited modules: {violations}"


def test_sentiment_analysis_no_provider_network_imports():
    """sentiment_analysis.py must not import provider SDKs or network clients."""
    imports = _imports_from_file(SRC / "skills_runtime" / "sentiment_analysis.py")
    violations = imports & _PROVIDER_NETWORK
    assert not violations, f"sentiment_analysis.py imports prohibited modules: {violations}"


def test_news_research_inherits_mcp_adapter_skill():
    """news_research.py must inherit from MCPAdapterSkill."""
    filepath = SRC / "skills_runtime" / "news_research.py"
    text = filepath.read_text(encoding="utf-8")
    assert "MCPAdapterSkill" in text
    assert "class NewsResearchSkill" in text


def test_sentiment_analysis_inherits_mcp_adapter_skill():
    """sentiment_analysis.py must inherit from MCPAdapterSkill."""
    filepath = SRC / "skills_runtime" / "sentiment_analysis.py"
    text = filepath.read_text(encoding="utf-8")
    assert "MCPAdapterSkill" in text
    assert "class SentimentAnalysisSkill" in text


def test_mcp_adapter_skill_only_calls_host_injected_mcp_adapter():
    """MCPAdapterSkill must call host-injected mcp_adapter, not instantiate providers."""
    filepath = SRC / "skills_runtime" / "mcp_adapter_skill.py"
    text = filepath.read_text(encoding="utf-8")
    assert "self.mcp_adapter" in text
    assert "mcp_adapter.call" in text or "self.call_mcp" in text


def test_base_runtime_exposes_normalize_error():
    """BaseSkillRuntime must expose normalize_error and normalize_errors helpers."""
    filepath = SRC / "skills_runtime" / "base.py"
    text = filepath.read_text(encoding="utf-8")
    assert "normalize_error" in text
    assert "normalize_errors" in text


def test_runtime_skills_no_plain_string_errors():
    """Runtime skills must not append plain string errors to SkillOutput.errors."""
    runtime_dir = SRC / "skills_runtime"
    for py_file in runtime_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert 'errors=["' not in text, f"{py_file.name} uses plain string in errors list"
        assert "errors=[str(" not in text, f"{py_file.name} uses str() in errors list"
