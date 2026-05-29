"""FundamentalScore: fundamental analysis scoring via KG exposure and event aggregation."""
from __future__ import annotations

import networkx as nx

from legacy.analysis.scoring.types import ScoreComponent
from src.graph.builder import KnowledgeGraphBuilder


class FundamentalScoreCalculator:
    """Scores fund based on fundamental factors: industry/themes exposure and event sentiment.

    Uses KG exposure data for diversification scoring and aggregates event polarities
    for sentiment signal. LLM integration is accepted but serves as a no-op stub in
    this rule-based implementation.
    """

    def __init__(self):
        self._kg_builder = KnowledgeGraphBuilder()

    def compute(
        self,
        fund_data: dict,
        kg: nx.DiGraph,
        events: list,
        llm_client: object | None = None,
    ) -> ScoreComponent:
        """Compute fundamental score from KG exposure and event sentiment.

        Args:
            fund_data: Fund data dict with optional holdings/sectors.
            kg: NetworkX DiGraph built by KnowledgeGraphBuilder.
            events: List of event dicts with polarity/magnitude.
            llm_client: Reserved for LLM integration (no-op in rule-based fallback).

        Returns:
            ScoreComponent with score 0-100.
        """
        fund_code = fund_data.get("code", "")
        no_exposure = not fund_data or (not fund_data.get("holdings") and not fund_data.get("sectors"))

        if no_exposure and not events:
            return ScoreComponent(
                score=50.0,
                detail={"industries": 0, "themes": 0, "event_sentiment": 0.0},
                weights={"fundamental": 1.0},
                confidence=0.15,
            )

        # KG exposure: industry/themes diversity
        exposure = {}
        if fund_code and kg and kg.number_of_nodes() > 0:
            try:
                exposure = self._kg_builder.get_fund_exposure(kg, fund_code)
            except Exception:
                exposure = {}

        industries = exposure.get("industries", [])
        themes = exposure.get("themes", [])
        n_industries = len(industries)
        n_themes = len(themes)

        # Diversity score: more industries/themes → higher score (diminishing returns)
        diversity_score = min(100.0, 40.0 + n_industries * 5.0 + n_themes * 3.0)

        # Event sentiment aggregation
        event_sentiment = 0.0
        if events:
            polarities = [e.get("polarity", 0) or 0 for e in events]
            magnitudes = [e.get("magnitude", 0) or 0 for e in events]
            if polarities:
                avg_pol = sum(polarities) / len(polarities)
                avg_mag = sum(magnitudes) / len(magnitudes)
                event_sentiment = avg_pol * avg_mag

        # Event score: event sentiment as modifier
        event_score = 50.0 + event_sentiment * 40.0
        event_score = max(0.0, min(100.0, event_score))

        # Combine: diversity 40%, event sentiment 60%
        score = diversity_score * 0.4 + event_score * 0.6
        score = max(0.0, min(100.0, score))

        # Confidence: base 0.3 + exposure modifier
        confidence = 0.30 if n_industries > 0 else 0.15
        if events:
            confidence = min(0.85, confidence + 0.10)

        return ScoreComponent(
            score=round(score, 2),
            detail={
                "industries": n_industries,
                "themes": n_themes,
                "industry_names": industries,
                "theme_names": themes,
                "diversity_score": round(diversity_score, 2),
                "event_sentiment": round(event_sentiment, 4),
                "event_score": round(event_score, 2),
            },
            weights={"fundamental": 1.0},
            confidence=round(confidence, 2),
        )
