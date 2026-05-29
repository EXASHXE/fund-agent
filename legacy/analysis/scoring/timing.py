"""TimingScore: timing/momentum scoring with regime-aware base and event momentum signals."""
from __future__ import annotations

from legacy.analysis.scoring.types import ScoreComponent, MarketRegime


class TimingScoreCalculator:
    """Scores the timing suitability of investing in a fund.

    Rule-based fallback: base score from market regime + momentum adjustment
    from relevant event types (earnings_surprise, fund_flow, tech_breakthrough).
    LLM integration accepted as a no-op stub.
    """

    # Regime base scores (higher = better time to invest)
    REGIME_BASES: dict[MarketRegime, float] = {
        MarketRegime.NORMAL: 65.0,
        MarketRegime.TRENDING: 78.0,
        MarketRegime.HIGH_VOLATILITY: 40.0,
        MarketRegime.CRISIS: 25.0,
    }

    # Event types that signal momentum (used for adjustment)
    MOMENTUM_EVENT_TYPES: set[str] = {
        "earnings_surprise", "fund_flow", "tech_breakthrough",
        "rate_change", "policy_shift", "earnings_miss",
    }

    def compute(
        self,
        fund_data: dict,
        regime: MarketRegime,
        events: list,
        llm_client: object | None = None,
    ) -> ScoreComponent:
        """Compute timing score from market regime and event momentum.

        Args:
            fund_data: Fund data dict (used for future NAV-based momentum signals).
            regime: Detected market regime.
            events: List of event dicts with type/polarity/magnitude.
            llm_client: Reserved for LLM integration (no-op in rule-based fallback).

        Returns:
            ScoreComponent with score 0-100.
        """
        base = self.REGIME_BASES.get(regime, 50.0)

        # Momentum adjustment from relevant event types
        momentum = 0.0
        if events:
            relevant = [
                e for e in events
                if e.get("type", "") in self.MOMENTUM_EVENT_TYPES
            ]
            if relevant:
                polarities = [(e.get("polarity", 0) or 0) for e in relevant]
                magnitudes = [(e.get("magnitude", 0) or 0) for e in relevant]
                avg_pol = sum(polarities) / len(polarities)
                avg_mag = sum(magnitudes) / len(magnitudes)
                momentum = avg_pol * avg_mag * 15.0  # scale to 0-15 range

        score = max(0.0, min(100.0, base + momentum))

        confidence = 0.55
        if events:
            confidence = min(0.80, confidence + 0.10)

        return ScoreComponent(
            score=round(score, 2),
            detail={
                "regime": regime.value,
                "base": round(base, 2),
                "momentum_adjustment": round(momentum, 2),
                "n_events_used": len([e for e in events if e.get("type", "") in self.MOMENTUM_EVENT_TYPES]) if events else 0,
            },
            weights={"timing": 1.0},
            confidence=round(confidence, 2),
        )
