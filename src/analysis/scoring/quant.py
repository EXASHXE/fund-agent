"""QuantScore: data-driven quantitative scoring with dynamic regime-based weights."""
from __future__ import annotations

import pandas as pd

from src.analysis.metrics import MetricsCalculator
from src.analysis.scoring.types import ScoreComponent, MarketRegime


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
        weights = self._regime_weights(regime, metrics)
        raw = sum(metrics.get(k, 0) for k in weights)
        score = max(0.0, min(100.0, raw))

        confidence = self._compute_confidence(completeness, metrics)

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
            result["sortino"] = self._score_sortino(daily_returns)

        perf = None
        if isinstance(nav, pd.DataFrame) and "日增长率" in nav.columns:
            perf = self._metrics.compute_perf_from_nav(nav)

        if perf:
            perf_1y = perf.get("近1年", {})
            sharpe = perf_1y.get("sharpe_ratio", 0) or 0
            result["sharpe"] = self._score_sharpe(float(sharpe))

            drawdown_3y = perf.get("近3年", {}).get("max_drawdown", 25) or 25
            result["max_drawdown"] = self._score_drawdown(float(drawdown_3y))

            vol_1y = perf_1y.get("annual_volatility", 20) or 20
            result["volatility"] = self._score_volatility(float(vol_1y))

        adv = self._metrics.advanced_metrics(nav, basic)
        if adv:
            alpha = adv.get("jensen_alpha", 0) or 0
            result["alpha"] = self._score_alpha(float(alpha))

        return result

    def _score_sharpe(self, sharpe: float) -> float:
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

    def _score_sortino(self, daily_returns) -> float:
        sortino = self._metrics.sortino_ratio(list(daily_returns))
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

    def _score_drawdown(self, dd: float) -> float:
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

    def _score_volatility(self, vol: float) -> float:
        if vol < 10:
            return 80.0
        if vol < 15:
            return 70.0
        if vol < 20:
            return 60.0
        if vol < 25:
            return 50.0
        return 40.0

    def _score_alpha(self, alpha: float) -> float:
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

    def _regime_weights(self, regime: MarketRegime, metrics: dict) -> dict[str, float]:
        """Get per-metric weights adjusted by regime."""
        # Base weights for individual quant sub-metrics
        base_weights = {
            "sharpe": 0.25,
            "sortino": 0.20,
            "alpha": 0.15,
            "max_drawdown": 0.15,
            "volatility": 0.15,
            "hhi": 0.10,
        }

        if regime == MarketRegime.HIGH_VOLATILITY:
            # Emphasize risk metrics in volatile markets
            base_weights = {
                "sharpe": 0.15,
                "sortino": 0.15,
                "alpha": 0.10,
                "max_drawdown": 0.25,
                "volatility": 0.25,
                "hhi": 0.10,
            }
        elif regime == MarketRegime.CRISIS:
            # Max emphasis on risk
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

    def _compute_confidence(self, completeness: str, metrics: dict) -> float:
        """Compute confidence based on data completeness and metric availability."""
        base = {"A": 0.92, "B": 0.82, "C": 0.60, "D": 0.25}.get(completeness, 0.50)
        # Count how many metrics have non-default values
        computed = sum(1 for v in metrics.values() if v != 50.0)
        total = max(len(metrics), 1)
        coverage = computed / total
        return round(base * (0.5 + 0.5 * coverage), 2)
