"""Agent tool bindings for the LangGraph research OS."""
from __future__ import annotations

from typing import Any, Mapping

from src.agents.tools.analysis_tools import register_analysis_tools
from src.agents.tools.kg_tools import register_kg_tools
from src.agents.tools.news_tools import register_news_tools
from src.agents.tools.strategy_tools import register_strategy_tools
from src.agents.tools.vector_tools import register_vector_tools
from src.tools.evidence_tools import build_evidence_tool_registry
from src.tools.registry import ToolDefinition, ToolRegistry


AGENT_TOOL_MODULES = (
    "kg_tools",
    "vector_tools",
    "news_tools",
    "analysis_tools",
    "strategy_tools",
)


def build_agent_tool_registry(
    evidence: Mapping[str, Any] | None = None,
    *,
    graph=None,
    embedding_pipeline=None,
    llm_client=None,
) -> ToolRegistry:
    """Build the default read-only tool registry for graph agents."""
    registry = build_evidence_tool_registry(evidence or {})
    register_kg_tools(registry, graph=graph)
    register_vector_tools(registry, embedding_pipeline=embedding_pipeline)
    register_news_tools(registry, llm_client=llm_client)
    register_analysis_tools(registry)
    register_strategy_tools(registry)
    return registry


def tools_for_agent(registry: ToolRegistry, agent: str) -> list[ToolDefinition]:
    """Return tools available to one agent role."""
    return registry.list(agent)


__all__ = [
    "AGENT_TOOL_MODULES",
    "build_agent_tool_registry",
    "register_analysis_tools",
    "register_kg_tools",
    "register_news_tools",
    "register_strategy_tools",
    "register_vector_tools",
    "tools_for_agent",
]
