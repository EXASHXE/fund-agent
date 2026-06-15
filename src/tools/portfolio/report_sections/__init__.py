"""Report sections package — modular section builders and rendering.

Re-exports all public API from submodules for backward compatibility.
"""

from src.tools.portfolio.report_sections.registry import (
    SECTION_ORDER,
    ZH_CN_SECTION_TITLES,
    SectionBuilder,
    section_registry,
)
from src.tools.portfolio.report_sections.render import (
    compose_personal_fund_report,
    render_report_markdown,
)

__all__ = [
    "SECTION_ORDER",
    "ZH_CN_SECTION_TITLES",
    "SectionBuilder",
    "section_registry",
    "compose_personal_fund_report",
    "render_report_markdown",
]
