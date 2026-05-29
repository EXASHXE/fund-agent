"""AI Financial Research OS — Orchestration entry points.

Legacy analyze workflow has been moved to legacy/workflows/analyze.py.
Use research_os for new pipelines, or import legacy.cli for CLI operations.
"""
from src.workflows.research_os import run_research_task as _run_research_task

__all__ = ["run_research_task"]


def run_research_task(task, **kwargs):
    """Run a ResearchTask through the Research OS loop. Convenience wrapper."""
    return _run_research_task(task, **kwargs)
