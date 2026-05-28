"""Scoring type definitions: ScoreComponent, MarketRegime, CompositeScore."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


@dataclass
class ScoreComponent:
    """A single dimension score with detail breakdown and confidence."""
    score: float
    detail: dict
    weights: dict[str, float]
    confidence: float


class MarketRegime(Enum):
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    TRENDING = "trending"
    CRISIS = "crisis"

    def weights(self) -> dict[str, float]:
        """Return scoring dimension weights for this regime."""
        regime_weights = {
            MarketRegime.NORMAL: {
                "quant": 0.40, "fundamental": 0.20,
                "event": 0.15, "position": 0.15, "timing": 0.10,
            },
            MarketRegime.HIGH_VOLATILITY: {
                "quant": 0.25, "fundamental": 0.15,
                "event": 0.30, "position": 0.20, "timing": 0.10,
            },
            MarketRegime.TRENDING: {
                "quant": 0.35, "fundamental": 0.25,
                "event": 0.10, "position": 0.15, "timing": 0.15,
            },
            MarketRegime.CRISIS: {
                "quant": 0.15, "fundamental": 0.10,
                "event": 0.40, "position": 0.25, "timing": 0.10,
            },
        }
        return regime_weights[self]


@dataclass
class CompositeScore:
    """Composite score combining all five dimensions with regime-based weights."""
    quant_score: ScoreComponent
    fundamental_score: ScoreComponent
    event_score: ScoreComponent
    position_score: ScoreComponent
    timing_score: ScoreComponent
    weights_used: dict[str, float]
    composite: float
    level: Literal["green", "yellow", "orange", "red"]
    regime: MarketRegime


def score_level(composite: float) -> Literal["green", "yellow", "orange", "red"]:
    """Convert composite score to level."""
    if composite >= 75:
        return "green"
    elif composite >= 50:
        return "yellow"
    elif composite >= 30:
        return "orange"
    else:
        return "red"