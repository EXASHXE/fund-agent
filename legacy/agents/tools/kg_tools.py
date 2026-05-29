"""Knowledge-graph tools for LangGraph agents."""
from __future__ import annotations

from typing import Any

import networkx as nx

from src.graph.builder import KnowledgeGraphBuilder
from src.tools.registry import ToolRegistry


def register_kg_tools(registry: ToolRegistry, graph: nx.DiGraph | None = None) -> ToolRegistry:
    """Register read-only KG query tools."""
    kg = KnowledgeGraphBuilder()

    @registry.tool(
        "kg.fund_exposure",
        "Return industry/theme exposure for one fund from the knowledge graph.",
        agents=("news", "research", "risk", "strategy"),
    )
    def fund_exposure(code: str):
        if graph is None:
            return {"industries": [], "themes": [], "macro_factors": []}
        return kg.get_fund_exposure(graph, code)

    @registry.tool(
        "kg.news_relevance",
        "Score one news item against a fund using KG overlap.",
        agents=("news", "research"),
    )
    def news_relevance(code: str, news_item: dict[str, Any]):
        if graph is None:
            return {"relevance": 0.0}
        return {"relevance": kg.query_relevance(graph, code, news_item)}

    @registry.tool(
        "kg.impact_chain",
        "Trace an extracted event's impact path through holdings to one fund.",
        agents=("research", "risk", "strategy"),
    )
    def impact_chain(code: str, event_id: str):
        if graph is None:
            return {"total_polarity": 0.0, "total_magnitude": 0.0, "paths": []}
        return kg.get_impact_chain(graph, event_id, code)

    return registry
