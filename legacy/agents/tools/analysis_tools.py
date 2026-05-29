"""Analysis tools for LangGraph agents."""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.tools.registry import ToolRegistry


def register_analysis_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register deterministic analysis helpers."""

    @registry.tool(
        "analysis.score_summary",
        "Summarize a list of numeric scores for routing and risk agents.",
        agents=("quant", "risk", "strategy", "summary"),
    )
    def score_summary(scores: list[float | int]):
        clean_scores = [float(item) for item in scores if isinstance(item, (int, float))]
        if not clean_scores:
            return {"count": 0, "avg": None, "min": None, "max": None}
        return {
            "count": len(clean_scores),
            "avg": round(mean(clean_scores), 2),
            "min": min(clean_scores),
            "max": max(clean_scores),
        }

    @registry.tool(
        "analysis.compact_keys",
        "Return sorted top-level keys for an evidence object.",
        agents=("news", "quant", "research", "risk", "strategy", "summary"),
    )
    def compact_keys(payload: dict[str, Any]):
        return sorted(str(key) for key in payload)

    return registry
