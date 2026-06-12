"""fund-agent public facade (top-level shim).

This package re-exports the stable public API from ``src.fund_agent`` so
that downstream consumers can use the documented import paths::

    from fund_agent import __version__
    from fund_agent.workflow import WorkflowTrace
    from fund_agent.regression import run_personal_regression_fixture
    ...
"""
from __future__ import annotations

from src.fund_agent import __version__
from src.fund_agent import *  # noqa: F401,F403

__all__ = ["__version__"]
