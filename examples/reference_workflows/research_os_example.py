"""Optional reference workflow example.

The skill pack product does not require this workflow. External agent hosts can
use the manifest and runtime skills directly.
"""

from src.core.research_os import run_research_task

__all__ = ["run_research_task"]
