"""Report composer — thin re-export shim.

All implementation has been moved to the report_sections package.
This module re-exports the public API for backward compatibility.
"""

from src.tools.portfolio.report_sections import (
    SECTION_ORDER,
    ZH_CN_SECTION_TITLES,
    SectionBuilder,
    compose_personal_fund_report,
    render_report_markdown,
    section_registry,
)

__all__ = [
    "SECTION_ORDER",
    "ZH_CN_SECTION_TITLES",
    "SectionBuilder",
    "compose_personal_fund_report",
    "render_report_markdown",
    "section_registry",
]
