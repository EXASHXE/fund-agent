"""Pure ToolRegistry tests for plugin core."""

from __future__ import annotations

import pytest

from src.tools.registry import ToolDefinition, ToolRegistry


def test_tool_registry_filters_tools_by_agent_and_invokes_handler():
    registry = ToolRegistry()

    @registry.tool("news.brief", "Return compressed news context", agents=("news",))
    def news_brief(code):
        return {"code": code, "brief": "ok"}

    @registry.tool("portfolio.summary", "Return portfolio summary", agents=("portfolio",))
    def portfolio_summary():
        return {"total": 100}

    assert [tool.name for tool in registry.list("news")] == ["news.brief"]
    assert [tool.name for tool in registry.list("portfolio")] == [
        "portfolio.summary"
    ]
    assert registry.invoke("news.brief", code="000001") == {
        "code": "000001",
        "brief": "ok",
    }


def test_tool_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    registry.register(ToolDefinition("dup", "first", lambda: None))

    with pytest.raises(ValueError, match="工具已注册"):
        registry.register(ToolDefinition("dup", "second", lambda: None))
