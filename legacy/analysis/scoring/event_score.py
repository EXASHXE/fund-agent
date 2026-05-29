"""EventScore: event-based scoring with time decay and KG impact chain propagation."""
from __future__ import annotations

import math
from datetime import date, datetime

import networkx as nx

from legacy.analysis.scoring.types import ScoreComponent
from src.graph.builder import KnowledgeGraphBuilder


class EventScoreCalculator:
    """Scores fund based on event impacts, using KG for propagation and exponential time decay."""

    def __init__(self, lambda_decay: float = 0.2):
        self.lambda_decay = lambda_decay
        self._kg_builder = KnowledgeGraphBuilder()

    def compute(self, fund_code: str, events: list, kg: nx.DiGraph) -> ScoreComponent:
        """Compute event score from event list and knowledge graph.

        Args:
            fund_code: Fund identifier.
            events: List of event dicts with keys: id, polarity, magnitude, date, type.
            kg: NetworkX DiGraph built by KnowledgeGraphBuilder.

        Returns:
            ScoreComponent with score 0-100.
        """
        if not events:
            return ScoreComponent(
                score=50.0,
                detail={"no_events": True},
                weights={"event": 1.0},
                confidence=0.1,
            )

        total = 0.0
        contributions = []

        for event in events:
            polarity = event.get("polarity", 0) or 0
            magnitude = event.get("magnitude", 0) or 0
            event_date = event.get("date", "")
            event_id = event.get("id", event.get("event_id", ""))

            # Exponential time decay
            days_ago = self._days_since(event_date) if event_date else 0.0
            time_decay = math.exp(-self.lambda_decay * days_ago)

            # Path impact from KG (only if KG has event node with IMPACTS edges)
            path_impact = 0.5  # default neutral
            if event_id:
                try:
                    chain = self._kg_builder.get_impact_chain(kg, event_id, fund_code)
                    if chain and chain.get("paths"):
                        # Use total magnitude as path impact multiplier
                        total_mag = abs(chain.get("total_magnitude", 0))
                        path_impact = min(1.0, max(0.1, total_mag))
                except Exception:
                    pass

            contribution = polarity * magnitude * path_impact * time_decay
            total += contribution

            contributions.append({
                "event_id": event_id,
                "polarity": polarity,
                "magnitude": magnitude,
                "time_decay": round(time_decay, 4),
                "path_impact": round(path_impact, 4),
                "contribution": round(contribution, 4),
            })

        # Normalize to 0-100: 50 + total * 50, clamped
        score = max(0.0, min(100.0, 50.0 + total * 50.0))

        # Confidence: base 0.3 + 0.05 per event, capped at 0.95
        confidence = min(0.95, 0.3 + 0.05 * len(events))

        return ScoreComponent(
            score=round(score, 2),
            detail={"contributions": contributions, "total": round(total, 4)},
            weights={"event": 1.0},
            confidence=round(confidence, 2),
        )

    def _days_since(self, date_str: str) -> float:
        """Calculate days since a given date string (YYYY-MM-DD)."""
        try:
            event_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
            today = date.today()
            return float((today - event_date).days)
        except (ValueError, TypeError):
            return 0.0
