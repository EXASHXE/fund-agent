"""Scoring helpers: threshold functions, regime weights, confidence, completeness.

All functions are pure: no IO, no network, no LLM dependencies.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

import pandas as pd


# ---------------------------------------------------------------------------
# Threshold scoring helpers (extracted from QuantScoreCalculator)
# ---------------------------------------------------------------------------

def score_sharpe(sharpe: float) -> float:
    """Map Sharpe ratio to a 0-100 score using fixed thresholds."""
    if sharpe > 2.0:
        return 90.0
    if sharpe > 1.5:
        return 80.0
    if sharpe > 1.0:
        return 70.0
    if sharpe > 0.5:
        return 60.0
    if sharpe > 0.0:
        return 50.0
    return 40.0


def score_sortino_from_ratio(sortino: float) -> float:
    """Map a pre-computed Sortino ratio to a 0-100 score using fixed thresholds."""
    if sortino > 2.0:
        return 90.0
    if sortino > 1.5:
        return 80.0
    if sortino > 1.0:
        return 70.0
    if sortino > 0.5:
        return 60.0
    if sortino > 0.0:
        return 50.0
    return 40.0


def score_drawdown(dd: float) -> float:
    """Map max drawdown percentage to a 0-100 score (lower drawdown = higher score)."""
    if dd < 10:
        return 90.0
    if dd < 15:
        return 80.0
    if dd < 20:
        return 70.0
    if dd < 25:
        return 60.0
    if dd < 30:
        return 50.0
    return 40.0


def score_volatility(vol: float) -> float:
    """Map annual volatility percentage to a 0-100 score (lower vol = higher score)."""
    if vol < 10:
        return 80.0
    if vol < 15:
        return 70.0
    if vol < 20:
        return 60.0
    if vol < 25:
        return 50.0
    return 40.0


def score_alpha(alpha: float) -> float:
    """Map Jensen Alpha to a 0-100 score."""
    if alpha > 0.15:
        return 90.0
    if alpha > 0.08:
        return 80.0
    if alpha > 0.03:
        return 70.0
    if alpha > 0.0:
        return 60.0
    if alpha > -0.05:
        return 50.0
    return 40.0


# ---------------------------------------------------------------------------
# Regime-based weight construction
# ---------------------------------------------------------------------------

def regime_weights(regime, metrics: dict) -> dict[str, float]:
    """Get per-metric weights adjusted by market regime (pure dict construction).

    Args:
        regime: A MarketRegime enum value (or anything with .value == str).
        metrics: Dict of metric name -> computed score.

    Returns:
        Dict of metric name -> weight, filtered to keys present in *metrics*.
    """
    # Base weights for individual quant sub-metrics
    base_weights = {
        "sharpe": 0.25,
        "sortino": 0.20,
        "alpha": 0.15,
        "max_drawdown": 0.15,
        "volatility": 0.15,
        "hhi": 0.10,
    }

    regime_name = regime.value if hasattr(regime, 'value') else str(regime)

    if regime_name == "high_volatility":
        base_weights = {
            "sharpe": 0.15,
            "sortino": 0.15,
            "alpha": 0.10,
            "max_drawdown": 0.25,
            "volatility": 0.25,
            "hhi": 0.10,
        }
    elif regime_name == "crisis":
        base_weights = {
            "sharpe": 0.10,
            "sortino": 0.10,
            "alpha": 0.05,
            "max_drawdown": 0.30,
            "volatility": 0.30,
            "hhi": 0.15,
        }

    # Only include metrics that were actually computed
    return {k: v for k, v in base_weights.items() if k in metrics}


# ---------------------------------------------------------------------------
# Confidence computation
# ---------------------------------------------------------------------------

def compute_confidence(completeness: str, metrics: dict) -> float:
    """Compute confidence based on data completeness and metric availability (pure math)."""
    base = {"A": 0.92, "B": 0.82, "C": 0.60, "D": 0.25}.get(completeness, 0.50)
    computed = sum(1 for v in metrics.values() if v != 50.0)
    total = max(len(metrics), 1)
    coverage = computed / total
    return round(base * (0.5 + 0.5 * coverage), 2)


# ---------------------------------------------------------------------------
# Composite score level
# ---------------------------------------------------------------------------

def score_level(composite: float) -> Literal["green", "yellow", "orange", "red"]:
    """Convert composite score (0-100) to a human-readable level.

    - >= 75 -> "green"
    - >= 50 -> "yellow"
    - >= 30 -> "orange"
    - else  -> "red"
    """
    if composite >= 75:
        return "green"
    elif composite >= 50:
        return "yellow"
    elif composite >= 30:
        return "orange"
    else:
        return "red"


# ---------------------------------------------------------------------------
# Data completeness assessment
# ---------------------------------------------------------------------------

def assess_completeness(
    basic: Any,
    perf: Any,
    nav: Any,
    holdings: Any,
    sectors: Any,
) -> str:
    """Assess fund data completeness based on available data sources (pure logic).

    Returns one of "A", "B", "C", "D" based on coverage of basic, perf, nav,
    holdings, and sectors data.
    """
    has_basic = bool(basic) and isinstance(basic, dict) and "error" not in basic
    has_nav = isinstance(nav, pd.DataFrame) and len(nav) > 30
    has_perf = bool(perf) and isinstance(perf, dict) and "error" not in perf

    if not has_basic or not has_nav:
        return "D"

    core_ok = has_basic and has_nav
    enhanced_ok = (
        isinstance(holdings, pd.DataFrame) and len(holdings) > 0 and
        isinstance(sectors, pd.DataFrame) and len(sectors) > 0
    )

    if not core_ok:
        return "D"
    if has_perf and enhanced_ok:
        return "A"
    if has_perf:
        return "B"
    if core_ok and enhanced_ok:
        return "B"
    if core_ok:
        return "C"
    return "D"
