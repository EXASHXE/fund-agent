"""Optional reference workflow entry points.

Host integrations should use the skillpack manifest and src.skills_runtime
directly. ResearchOS wrappers are retained for optional reference only.
"""
from src.workflows.research_os import run_research_task as _run_research_task

__all__ = ["run_research_task"]


def run_research_task(task, **kwargs):
    """Run a ResearchTask through the Research OS loop. Convenience wrapper."""
    return _run_research_task(task, **kwargs)
