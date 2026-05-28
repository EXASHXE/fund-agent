"""Dynamic factor weights: regime-based weight mapping and enhanced factor matrix."""
from __future__ import annotations

from typing import Any

import networkx as nx

from src.analysis.scoring.types import MarketRegime


def get_regime_weights(regime: MarketRegime) -> dict[str, float]:
    """Return five-dimension scoring weights for a given market regime.

    Delegates to MarketRegime.weights() which is defined in types.py.
    """
    return dict(regime.weights())


def compute_factor_matrix(
    fund_data: dict,
    kg: nx.DiGraph | None,
    events: list[dict],
) -> dict[str, float]:
    """Compute a 5-dimension factor matrix from fund data, KG, and events.

    Returns normalized factors (0.0-1.0) for: quant, fundamental, event, position, timing.
    Used as pre-scoring signal before full ScoreComponent computation.
    """
    factors: dict[str, float] = {
        "quant": 0.5,
        "fundamental": 0.5,
        "event": 0.5,
        "position": 0.5,
        "timing": 0.5,
    }

    # Quant factor: influenced by performance metrics
    perf = fund_data.get("perf", {})
    if perf:
        perf_1y = perf.get("近1年", {})
        sharpe = perf_1y.get("sharpe_ratio", 0) or 0
        vol = perf_1y.get("annual_volatility", 20) or 20
        factors["quant"] = _normalize_quant(sharpe, vol)

    # Event factor: influenced by event polarity aggregation
    if events:
        polarities = [e.get("polarity", 0) or 0 for e in events]
        mags = [e.get("magnitude", 0) or 0 for e in events]
        if polarities:
            avg_pol = sum(polarities) / len(polarities)
            avg_mag = sum(mags) / len(mags)
            factors["event"] = _normalize_sigmoid(avg_pol * avg_mag * 5)

    return factors


def _normalize_quant(sharpe: float, volatility: float) -> float:
    """Normalize Sharpe ratio and volatility into 0-1 quant factor."""
    # Map sharpe [0, 2] → [0, 1]
    sharpe_score = max(0.0, min(1.0, (sharpe or 0) / 2.0))
    # Map volatility [35, 5] → [0, 1] (lower is better)
    vol_score = max(0.0, min(1.0, 1.0 - ((volatility or 20) - 5) / 30.0))
    return (sharpe_score * 0.6 + vol_score * 0.4)


def _normalize_sigmoid(x: float) -> float:
    """Sigmoid normalization to [0, 1]."""
    import math
    try:
        return round(1.0 / (1.0 + math.exp(-x)), 4)
    except OverflowError:
        return 1.0 if x > 0 else 0.0
