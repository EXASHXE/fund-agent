"""Diagnostics stage for professional rule evaluation.

Wires deterministic, local-only professional diagnostic rules into the
fund_analysis pipeline. These rules do NOT fetch data, call providers, use LLMs,
or make formal decisions.
"""

from __future__ import annotations

from typing import Any

from .context import CoreMetricsBundle, PortfolioInputBundle
from .professional_rules import run_professional_diagnostics


def compute_diagnostics(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
    warnings: list[str],
) -> dict[str, Any]:
    """Compute professional diagnostic artifacts from host-supplied data.

    Returns a dict suitable for merging into the artifact payload.
    """
    return run_professional_diagnostics(
        bundle=bundle,
        metrics=metrics,
        warnings=warnings,
    )
