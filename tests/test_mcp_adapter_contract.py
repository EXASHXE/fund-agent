"""Contract tests for host-native MCP adapter abstraction."""

from __future__ import annotations

import importlib
import json
import sys

from src.tools.adapters.mcp import (
    InMemoryMCPHostAdapter,
    MCPCapability,
)


def test_mcp_capability_is_serializable():
    """MCPCapability should serialize without provider SDK objects."""
    capability = MCPCapability(
        name="web_search",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        priority=10,
        fallback=["news_search"],
    )

    json.dumps(capability.to_dict())


def test_inmemory_mcp_adapter_lists_capabilities():
    """InMemory adapter exposes registered capabilities."""
    adapter = InMemoryMCPHostAdapter([
        MCPCapability("b", {}, {}, priority=20),
        MCPCapability("a", {}, {}, priority=10),
    ])

    assert [capability.name for capability in adapter.list_capabilities()] == ["a", "b"]
    assert adapter.has_capability("a") is True
    assert adapter.has_capability("missing") is False


def test_inmemory_mcp_adapter_calls_registered_capability():
    """Registered capability calls return structured dict responses."""
    adapter = InMemoryMCPHostAdapter()
    adapter.register(
        MCPCapability("echo", {"type": "object"}, {"type": "object"}),
        handler=lambda payload: {"received": payload["value"]},
    )

    result = adapter.call("echo", {"value": 42})

    assert result == {"ok": True, "data": {"received": 42}}


def test_missing_mcp_capability_returns_structured_error():
    """Missing capabilities return structured errors, not raw exceptions."""
    adapter = InMemoryMCPHostAdapter()

    result = adapter.call("missing", {"value": 1})

    assert result["ok"] is False
    assert result["error"]["type"] == "missing_capability"
    assert result["error"]["capability"] == "missing"


def test_mcp_adapter_does_not_import_provider_sdks():
    """Adapter module must not import provider SDK modules."""
    provider_modules = {"tavily", "finnhub", "exa", "firecrawl", "reddit"}
    before = set(sys.modules)
    importlib.import_module("src.tools.adapters.mcp")
    imported = set(sys.modules) - before

    assert provider_modules.isdisjoint(imported)
