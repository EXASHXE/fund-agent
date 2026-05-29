"""PositionScore: position risk scoring with concentration, diversification, and risk factors."""
from __future__ import annotations

import networkx as nx

from legacy.analysis.scoring.types import ScoreComponent


class PositionScoreCalculator:
    """Scores fund position risk via 5 factors: concentration (HHI), style drift, industry
    exposure, single-name risk, and overseas exposure.

    Weights: concentration 0.25, style_drift 0.25, industry_exposure 0.25,
             single_name_risk 0.15, overseas 0.10.
    """

    # Sub-factor weights (must sum to 1.0)
    FACTOR_WEIGHTS: dict[str, float] = {
        "concentration": 0.25,
        "style_drift": 0.25,
        "industry_exposure": 0.25,
        "single_name_risk": 0.15,
        "overseas": 0.10,
    }

    def compute(self, fund_data: dict, kg: nx.DiGraph) -> ScoreComponent:
        """Compute position risk score from holdings data.

        Args:
            fund_data: Fund data dict with holdings list.
            kg: NetworkX DiGraph (unused for position scoring, accepted for interface consistency).

        Returns:
            ScoreComponent with score 0-100.
        """
        holdings = fund_data.get("holdings", [])
        if not holdings:
            return ScoreComponent(
                score=50.0,
                detail={
                    "concentration": 50.0,
                    "style_drift": 50.0,
                    "industry_exposure": 50.0,
                    "single_name_risk": 50.0,
                    "overseas": 50.0,
                },
                weights=dict(self.FACTOR_WEIGHTS),
                confidence=0.10,
            )

        # 1. Concentration risk (HHI)
        hhi = self._compute_hhi(holdings)
        concentration_score = self._hhi_to_score(hhi)

        # 2. Style drift (placeholder: use holdings count as proxy)
        n_holdings = len(holdings)
        style_score = min(100.0, 40.0 + n_holdings * 4.0)

        # 3. Industry exposure diversification
        industries = set()
        for h in holdings:
            ind = h.get("industry", h.get("sector", ""))
            if ind:
                industries.add(ind)
        n_industries = len(industries)
        industry_score = min(100.0, 30.0 + n_industries * 10.0)

        # 4. Single-name risk (penalize high individual weights)
        max_weight = max((h.get("weight", 0) or 0 for h in holdings), default=0)
        single_score = max(0.0, min(100.0, 100.0 - max_weight * 1.5))

        # 5. Overseas exposure (default neutral, fund_data override)
        overseas = fund_data.get("overseas_exposure", 0.0) or 0.0
        overseas_score = max(0.0, min(100.0, 100.0 - overseas * 2.0))

        sub_scores = {
            "concentration": round(concentration_score, 2),
            "style_drift": round(style_score, 2),
            "industry_exposure": round(industry_score, 2),
            "single_name_risk": round(single_score, 2),
            "overseas": round(overseas_score, 2),
        }

        # Weighted combination
        total = sum(sub_scores[k] * self.FACTOR_WEIGHTS[k] for k in self.FACTOR_WEIGHTS)
        total = round(total, 2)

        # Confidence based on data richness
        confidence = 0.40 + min(0.50, n_holdings * 0.03)

        return ScoreComponent(
            score=max(0.0, min(100.0, total)),
            detail={
                **sub_scores,
                "hhi": round(hhi, 2),
                "n_holdings": n_holdings,
                "n_industries": n_industries,
                "max_weight": round(max_weight, 2),
            },
            weights=dict(self.FACTOR_WEIGHTS),
            confidence=round(confidence, 2),
        )

    @staticmethod
    def _compute_hhi(holdings: list[dict]) -> float:
        """Compute Herfindahl-Hirschman Index from holdings weights.

        HHI = sum(w_i²) where w_i are weight percentages.
        Higher HHI = more concentrated.
        """
        if not holdings:
            return 10000.0
        weights = [(h.get("weight", 0) or 0) for h in holdings]
        total_weight = sum(weights)
        if total_weight < 0.01:
            return 10000.0
        # Normalize to percentages then square
        return sum((w * w) for w in weights)

    @staticmethod
    def _hhi_to_score(hhi: float) -> float:
        """Convert HHI to a 0-100 score (lower HHI = better diversification = higher score).

        HHI < 1000: excellent diversification → 85-100
        HHI 1000-1800: moderate → 60-85
        HHI 1800-2500: high concentration → 35-60
        HHI > 2500: very high concentration → 0-35
        """
        if hhi < 500:
            return 95.0
        elif hhi < 1000:
            return 85.0 + (1000 - hhi) / 500 * 10.0
        elif hhi < 1800:
            return 60.0 + (1800 - hhi) / 800 * 25.0
        elif hhi < 2500:
            return 35.0 + (2500 - hhi) / 700 * 25.0
        else:
            return max(0.0, 35.0 - (hhi - 2500) / 2500 * 35.0)
