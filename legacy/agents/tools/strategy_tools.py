"""Strategy-specific tools for LangGraph agents."""
from __future__ import annotations

from typing import Any

from legacy.strategy.models import TriggerPoint
from src.tools.registry import ToolRegistry


def register_strategy_tools(registry: ToolRegistry) -> ToolRegistry:
    """Register deterministic strategy helper tools."""

    @registry.tool(
        "strategy.evaluate_trigger",
        "Evaluate one strategy trigger point against a compact context.",
        agents=("strategy", "summary"),
    )
    def evaluate_trigger(trigger: dict[str, Any], context: dict[str, Any]):
        trigger_point = TriggerPoint(
            metric=str(trigger.get("metric", "")),
            operator=str(trigger.get("operator", "")),
            threshold=trigger.get("threshold"),
            description=str(trigger.get("description", "")),
            confidence=float(trigger.get("confidence", 0.5) or 0.5),
        )
        return {
            "triggered": trigger_point.is_triggered(context),
            "description": trigger_point.description,
        }

    return registry
