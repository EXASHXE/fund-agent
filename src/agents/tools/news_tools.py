"""News tools for LangGraph agents."""
from __future__ import annotations

from src.events.extractor import extract_events_from_text
from src.tools.registry import ToolRegistry


def register_news_tools(registry: ToolRegistry, llm_client=None) -> ToolRegistry:
    """Register local news analysis tools."""

    @registry.tool(
        "news.extract_events",
        "Extract structured market events from one news text.",
        agents=("news", "research", "strategy"),
    )
    def extract_events(text: str):
        return extract_events_from_text(text, llm_client=llm_client)

    return registry
