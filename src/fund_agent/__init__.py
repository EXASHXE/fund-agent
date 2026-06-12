"""fund-agent public facade.

Stable import paths for external consumers. Thin wrappers over
existing implementation -- no logic duplication, no provider SDKs,
no network calls, no broker execution.

Recommended import paths:
    fund_agent.workflow
    fund_agent.regression
    fund_agent.quality
    fund_agent.providers
    fund_agent.reporting
    fund_agent.runtime
    fund_agent.version
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
