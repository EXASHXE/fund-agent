"""Shared report helper functions for the workflow tools layer.

These are pure, side-effect-free utilities used by ``final_report.py``,
``report_zh.py``, and other report composers. They must not import from
``src.skills_runtime`` -- this is a tools-only module.
"""

from __future__ import annotations

from typing import Any


def theme_text(fa_artifacts: dict[str, Any]) -> str:
    """Build a lowercased text blob from common fund_analysis artifact keys.

    Used for keyword matching (e.g. detecting theme/sector mentions) in
    report section builders.
    """
    parts: list[str] = []
    for key in (
        "fund_profiles",
        "portfolio_summary",
        "position_summary",
        "exposure_summary",
        "fund_analysis_report",
    ):
        value = fa_artifacts.get(key)
        if isinstance(value, dict):
            parts.append(str(value))
    return " ".join(parts).lower()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    """Return deduplicated strings preserving first-occurrence order."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
