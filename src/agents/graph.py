"""Compatibility entrypoint for the LangGraph research pipeline."""
from src.agents.graphs.supervisor import (
    build_research_graph,
    build_research_graph_with_routing,
)

__all__ = [
    "build_research_graph",
    "build_research_graph_with_routing",
]
