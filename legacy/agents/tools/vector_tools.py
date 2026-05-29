"""Vector-search tools for LangGraph agents."""
from __future__ import annotations

from src.tools.registry import ToolRegistry


def register_vector_tools(registry: ToolRegistry, embedding_pipeline=None) -> ToolRegistry:
    """Register optional vector search helpers.

    The tool is deliberately inert without an injected embedding pipeline, so
    tests and offline report generation do not contact external services.
    """

    @registry.tool(
        "vector.similar_funds",
        "Return funds similar to a compact profile text.",
        agents=("research", "risk", "strategy"),
    )
    def similar_funds(query: str, top_k: int = 5):
        if embedding_pipeline is None:
            return []
        return embedding_pipeline.search(query, top_k=top_k)

    return registry
