"""Planner Agent Node — KG-first inquiry decomposition and research task generation.

For each fund in state, checks which scoring dimensions already have results,
identifies gaps, and emits a prioritized list of ResearchTask dicts describing
what needs to be scored or re-scored. Increments the iteration counter.
"""
from __future__ import annotations

import logging
from typing import Any

from legacy.agents.state import FundResearchState

logger = logging.getLogger(__name__)


def planner_agent_node(state: FundResearchState) -> dict:
    """Queries KG and state to identify research gaps and emit ResearchTask list.

    For each fund with data in state:
      1. Check which scoring dimensions already have results
      2. Mark unscored dimensions as needed
      3. Build research_tasks list with priorities
      4. Append to planner_iteration_log

    Args:
        state: FundResearchState with funds_data and optional existing scores.

    Returns:
        Dict with research_tasks, iteration, and planner_iteration_log updates.
    """
    funds_data = state.get("funds_data", {})
    if not funds_data:
        return {
            "research_tasks": [],
            "iteration": state.get("iteration", 0) + 1,
            "planner_iteration_log": state.get("planner_iteration_log", []),
        }

    tasks: list[dict[str, Any]] = []
    iteration_log_entry: dict[str, Any] = {
        "iteration": state.get("iteration", 0) + 1,
        "funds_analyzed": list(funds_data.keys()),
        "tasks_generated": 0,
    }

    for code in funds_data:
        # Determine which dimensions are already scored
        existing_dims = set()
        if state.get("quant_scores", {}).get(code):
            existing_dims.add("quant")
        if state.get("fundamental_scores", {}).get(code):
            existing_dims.add("fundamental")
        if state.get("event_scores", {}).get(code):
            existing_dims.add("event")
        if state.get("position_scores", {}).get(code):
            existing_dims.add("position")
        if state.get("timing_scores", {}).get(code):
            existing_dims.add("timing")

        all_dims = ["quant", "fundamental", "event", "position", "timing"]
        missing_dims = [d for d in all_dims if d not in existing_dims]

        # Determine priority based on completion level
        if not existing_dims:
            priority = "high"
        elif missing_dims:
            priority = "medium"
        else:
            priority = "low"

        task = {
            "task_id": f"research_{code}",
            "fund_code": code,
            "type": "score_fund",
            "required_dimensions": all_dims,
            "missing_dimensions": missing_dims,
            "existing_dimensions": list(existing_dims),
            "priority": priority,
        }
        tasks.append(task)

    iteration_log_entry["tasks_generated"] = len(tasks)

    # Append to iteration log
    existing_log = state.get("planner_iteration_log", [])

    return {
        "research_tasks": tasks,
        "iteration": state.get("iteration", 0) + 1,
        "planner_iteration_log": existing_log + [iteration_log_entry],
    }
