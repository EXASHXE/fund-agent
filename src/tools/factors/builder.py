"""Factor matrix builder and score confidence calculator.

Extracted from legacy/analysis/factors.py.

All methods are PURE: zero IO, zero network, zero LLM calls.
"""

from __future__ import annotations

from typing import Dict


class FactorMatrixBuilder:
    """Build factor matrix and compute score confidence.

    Pure Python — no IO, no network, no LLM.
    """

    def build(self, score: dict, news_context: dict | None = None) -> dict:
        features = score.get("feature_matrix") or {}
        news_eval = (news_context or {}).get("news_evaluation") or {}
        catalyst = news_eval.get("overall_score")
        meso_score = score.get("meso_score")

        def factor(name, value, points, weight, source, missing_policy="neutral"):
            return {
                "name": name,
                "value": value,
                "score": points,
                "weight": weight,
                "source": source,
                "missing_policy": missing_policy,
            }

        macro = [
            factor(
                "fund_type_cycle_fit",
                score.get("fund_type", ""),
                round((score.get("macro_score") or 0) / 20, 4),
                0.20,
                "basic",
            )
        ]

        meso = []
        if meso_score is not None:
            meso.append(
                factor(
                    "sector_position",
                    meso_score,
                    round((meso_score or 0) / 30, 4),
                    0.18,
                    "rules",
                )
            )
        hhi_value = features.get("hhi_index")
        meso.append(
            factor(
                "hhi_index",
                hhi_value,
                self._score_hhi_factor(hhi_value),
                0.07,
                "holdings",
                "neutral_when_missing",
            )
        )
        if catalyst is not None:
            meso.append(
                factor(
                    "news_catalyst",
                    round(float(catalyst), 4),
                    round(max(-1.0, min(1.0, float(catalyst))), 4),
                    0.05,
                    "news_evaluation",
                    "ignore_when_missing",
                )
            )

        micro = [
            factor("sortino_ratio", features.get("sortino_ratio"), self._score_positive_ratio(features.get("sortino_ratio"), 1.5), 0.10, "feature_matrix"),
            factor("sharpe_1y", features.get("sharpe_1y"), self._score_positive_ratio(features.get("sharpe_1y"), 1.5), 0.10, "performance"),
            factor("max_drawdown_3y_pct", features.get("max_drawdown_3y_pct"), self._score_drawdown_factor(features.get("max_drawdown_3y_pct")), 0.10, "performance"),
            factor("annual_volatility", features.get("annual_volatility"), self._score_volatility_factor(features.get("annual_volatility")), 0.08, "performance"),
            factor("jensen_alpha", features.get("jensen_alpha"), self._score_positive_ratio(features.get("jensen_alpha"), 0.08), 0.06, "feature_matrix", "neutral_when_missing"),
            factor("information_ratio", features.get("information_ratio"), self._score_positive_ratio(features.get("information_ratio"), 0.8), 0.04, "feature_matrix", "neutral_when_missing"),
            factor("beta", features.get("beta"), self._score_beta_factor(features.get("beta")), 0.02, "feature_matrix", "neutral_when_missing"),
            factor("win_rate_1y", features.get("win_rate_1y"), self._score_positive_ratio(features.get("win_rate_1y"), 0.6), 0.05, "feature_matrix", "neutral_when_missing"),
            factor("calmar_ratio_1y", features.get("calmar_ratio_1y"), self._score_positive_ratio(features.get("calmar_ratio_1y"), 1.0), 0.05, "feature_matrix", "neutral_when_missing"),
        ]

        return {"macro": macro, "meso": meso, "micro": micro}

    def score_confidence(self, completeness: str, features: dict, factor_matrix: dict) -> float:
        base = {"A": 0.92, "B": 0.82, "C": 0.60, "D": 0.25}.get(completeness, 0.50)
        factors = [
            factor
            for dimension in (factor_matrix or {}).values()
            for factor in (dimension or [])
        ]
        if not factors:
            return round(base * 0.8, 2)
        available = sum(1 for f in factors if f.get("value") not in (None, ""))
        coverage = available / len(factors)
        key_metrics = ["max_drawdown_3y_pct", "annual_volatility", "sharpe_1y"]
        key_coverage = sum(1 for k in key_metrics if features.get(k) is not None) / len(key_metrics)
        confidence = base * (0.75 + 0.15 * coverage + 0.10 * key_coverage)
        return round(min(0.98, max(0.20, confidence)), 2)

    def _score_positive_ratio(self, value, good_threshold: float) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.5
        if good_threshold == 0:
            return 0.5
        return round(max(0.0, min(1.0, val / good_threshold)), 4)

    def _score_drawdown_factor(self, value) -> float:
        try:
            val = abs(float(value))
        except (TypeError, ValueError):
            return 0.5
        if val <= 10:
            return 1.0
        if val >= 35:
            return 0.1
        return round(1.0 - (val - 10) / 25 * 0.9, 4)

    def _score_volatility_factor(self, value) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.5
        if val <= 8:
            return 1.0
        if val >= 35:
            return 0.1
        return round(1.0 - (val - 8) / 27 * 0.9, 4)

    def _score_hhi_factor(self, value) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.5
        if val <= 1500:
            return 1.0
        if val >= 3500:
            return 0.2
        return round(1.0 - (val - 1500) / 2000 * 0.8, 4)

    def _score_beta_factor(self, value) -> float:
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.5
        # Score based on distance from 1.0 (market beta). Beta = 1.0 → perfect score 1.0.
        # Beta = -1.5 is farther (2.5 away) than Beta = 1.5 (0.5 away), so scores lower.
        dist = abs(val - 1.0)
        return round(max(0.0, min(1.0, 1.0 - dist * 0.4)), 4)
