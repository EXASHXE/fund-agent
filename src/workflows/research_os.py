"""Deprecated optional Research OS reference wrapper.

This wrapper is retained for compatibility/reference examples only. External
agent hosts should use the skill pack manifest and ``src.skills_runtime``
handlers directly.
"""

from __future__ import annotations

from typing import Any

from src.core.research_os import run_research_task
from src.graph.knowledge_graph import KnowledgeGraph
from src.schemas.research_task import ResearchTask


def analyze(task_data: dict[str, Any] | ResearchTask) -> dict[str, Any]:
    """Reference-only Research OS workflow.

    Converts a dict or ResearchTask into the typed contract, optionally
    builds a KnowledgeGraph from portfolio holdings, then delegates to the
    main ``run_research_task`` loop.

    Args:
        task_data: Dict with ResearchTask fields (task_id, fund_universe,
                   objective, etc.) or a pre-built ResearchTask instance.

    Returns:
        FinalThesis dict from ``run_research_task`` (thesis_id, task_id,
        decision, ledger, evidence_count, iterations, etc.).
    """

    # Normalize input to ResearchTask
    if isinstance(task_data, dict):
        task = ResearchTask(**task_data)
    elif isinstance(task_data, ResearchTask):
        task = task_data
    else:
        raise TypeError(
            f"Expected dict or ResearchTask, got {type(task_data).__name__}"
        )

    # Optionally build KG from portfolio holdings
    kg = KnowledgeGraph()
    portfolio = getattr(task, "portfolio", None) or {}
    if portfolio:
        try:
            kg.build_from_holdings(portfolio)
        except Exception:
            # KG construction is best-effort; the main loop handles None safely
            pass

    return run_research_task(task, kg=kg)
