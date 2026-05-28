"""QuantScore: data-driven quantitative scoring with dynamic regime-based weights."""
from __future__ import annotations

import pandas as pd

from src.analysis.metrics import MetricsCalculator
from src.analysis.scoring.types import ScoreComponent, MarketRegime
from src.tools.scoring.helpers import (
    score_sharpe,
    score_sortino_from_ratio,
    score_drawdown,
    score_volatility,
    score_alpha,
    regime_weights,
    compute_confidence,
)


class QuantScoreCalculator:
    """Data-driven quantitative scoring. Uses existing metrics, no keyword lookups."""

    def __init__(self, metrics: MetricsCalculator | None = None):
        self._metrics = metrics or MetricsCalculator()

    def compute(self, fund_data: dict, regime: MarketRegime) -> ScoreComponent:
        """Compute quant score from fund data with regime-adjusted weights.

        Returns ScoreComponent(score=0-100, detail={metrics}, weights={}, confidence=0-1).
        """
        completeness = fund_data.get("completeness", "D")
        nav = fund_data.get("nav")
        basic = fund_data.get("basic", {})

        # Default fallback: no data
        nav_missing = nav is None or (isinstance(nav, pd.DataFrame) and nav.empty)
        perf_missing = not fund_data.get("perf")
        if not fund_data or (nav_missing and perf_missing):
            return ScoreComponent(
                score=50.0,
                detail={},
                weights={},
                confidence=max(0.1, {"A": 0.15, "B": 0.12, "C": 0.08, "D": 0.05}.get(completeness, 0.05)),
            )

        metrics = self._compute_all_metrics(nav, basic)
        weights = regime_weights(regime, metrics)
        raw = sum(metrics.get(k, 0) for k in weights)
        score = max(0.0, min(100.0, raw))

        confidence = compute_confidence(completeness, metrics)

        return ScoreComponent(
            score=round(score, 2),
            detail=metrics,
            weights=weights,
            confidence=round(confidence, 2),
        )

    def _compute_all_metrics(self, nav, basic: dict) -> dict[str, float]:
        """Compute all quantitative metrics from NAV data."""
        result: dict[str, float] = {
            "sharpe": 50.0,
            "sortino": 50.0,
            "alpha": 50.0,
            "max_drawdown": 50.0,
            "volatility": 50.0,
            "hhi": 50.0,
        }

        if nav is None or (isinstance(nav, pd.DataFrame) and nav.empty):
            return result

        daily_returns = None
        if isinstance(nav, pd.DataFrame) and "日增长率" in nav.columns:
            daily_returns = nav["日增长率"].dropna().values / 100.0

        if daily_returns is not None and len(daily_returns) >= 20:
            sortino = self._metrics.sortino_ratio(list(daily_returns))
            result["sortino"] = score_sortino_from_ratio(float(sortino))

        perf = None
        if isinstance(nav, pd.DataFrame) and "日增长率" in nav.columns:
            perf = self._metrics.compute_perf_from_nav(nav)

        if perf:
            perf_1y = perf.get("近1年", {})
            sharpe = perf_1y.get("sharpe_ratio", 0) or 0
            result["sharpe"] = score_sharpe(float(sharpe))

            drawdown_3y = perf.get("近3年", {}).get("max_drawdown", 25) or 25
            result["max_drawdown"] = score_drawdown(float(drawdown_3y))

            vol_1y = perf_1y.get("annual_volatility", 20) or 20
            result["volatility"] = score_volatility(float(vol_1y))

        adv = self._metrics.advanced_metrics(nav, basic)
        if adv:
            alpha = adv.get("jensen_alpha", 0) or 0
            result["alpha"] = score_alpha(float(alpha))

        return result

    # ------------------------------------------------------------------ #
    # Pure threshold methods — now delegated to src.tools.scoring.helpers #
    # ------------------------------------------------------------------ #

    def _score_sharpe(self, sharpe: float) -> float:
        return score_sharpe(sharpe)

    def _score_sortino(self, daily_returns) -> float:
        sortino = self._metrics.sortino_ratio(list(daily_returns))
        return score_sortino_from_ratio(float(sortino))

    def _score_drawdown(self, dd: float) -> float:
        return score_drawdown(dd)

    def _score_volatility(self, vol: float) -> float:
        return score_volatility(vol)

    def _score_alpha(self, alpha: float) -> float:
        return score_alpha(alpha)

    def _regime_weights(self, regime: MarketRegime, metrics: dict) -> dict[str, float]:
        return regime_weights(regime, metrics)

    def _compute_confidence(self, completeness: str, metrics: dict) -> float:
        return compute_confidence(completeness, metrics)
