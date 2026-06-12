"""Quality facade -- top-level shim."""
from __future__ import annotations

from src.fund_agent.quality import *  # noqa: F401,F403
from src.fund_agent.quality import __all__ as _all

__all__ = list(_all)
