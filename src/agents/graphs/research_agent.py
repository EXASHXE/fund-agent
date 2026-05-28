"""ResearchAgent graph node: fundamental and event-based scoring.

For each fund in state, computes FundamentalScore and EventScore using the
corresponding calculators, reading from KG, fund data, and extracted events.
"""
from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from src.agents.state import FundResearchState
from src.analysis.scoring.fundamental import FundamentalScoreCalculator
from src.analysis.scoring.event_score import EventScoreCalculator
from src.analysis.scoring.types import ScoreComponent

logger = logging.getLogger(__name__)


def _resolve_kg(state: FundResearchState) -> nx.DiGraph:
    """Resolve state's knowledge_graph field into a NetworkX DiGraph."""
    kg = state.get("knowledge_graph", {})
    if isinstance(kg, nx.DiGraph):
        return kg
    if isinstance(kg, dict):
        graph = nx.DiGraph()
        for node in kg.get("nodes", []):
            graph.add_node(node.get("id"), **{k: v for k, v in node.items() if k != "id"})
        for edge in kg.get("edges", []):
            src = edge.get("source")
            tgt = edge.get("target")
            if src and tgt:
                graph.add_edge(src, tgt, **{k: v for k, v in edge.items() if k not in ("source", "target")})
        return graph
    return nx.DiGraph()


def research_agent_node(state: FundResearchState) -> dict:
    """Compute fundamental and event scores for all funds.

    Reads funds_data, knowledge_graph, and extracted_events from state.
    For each fund:
      1. Calls FundamentalScoreCalculator.compute(fund_data, kg, events)
      2. Calls EventScoreCalculator.compute(fund_code, events, kg)
      3. Updates fundamental_scores and event_scores in state.

    Args:
        state: FundResearchState with funds_data, knowledge_graph, extracted_events.

    Returns:
        Dict with fundamental_scores and event_scores updates.
    """
    funds_data = state.get("funds_data", {})
    if not funds_data:
        return {"fundamental_scores": {}, "event_scores": {}}

    kg = _resolve_kg(state)
    extracted_events = state.get("extracted_events", {})

    fundamental_calc = FundamentalScoreCalculator()
    event_calc = EventScoreCalculator()

    fundamental_scores: dict[str, Any] = {}
    event_scores: dict[str, Any] = {}

    for fund_code, fund_data in funds_data.items():
        events = extracted_events.get(fund_code, [])

        # Ensure events is a list
        if not isinstance(events, list):
            events = []

        # Fundamental score
        try:
            fs: ScoreComponent = fundamental_calc.compute(fund_data, kg, events)
            fundamental_scores[fund_code] = fs
        except Exception as exc:
            logger.error("Fundamental score failed for %s: %s", fund_code, exc)
            fundamental_scores[fund_code] = ScoreComponent(
                score=50.0, detail={"error": str(exc)}, weights={}, confidence=0.1,
            )

        # Event score
        try:
            es: ScoreComponent = event_calc.compute(fund_code, events, kg)
            event_scores[fund_code] = es
        except Exception as exc:
            logger.error("Event score failed for %s: %s", fund_code, exc)
            event_scores[fund_code] = ScoreComponent(
                score=50.0, detail={"error": str(exc)}, weights={}, confidence=0.1,
            )

    return {
        "fundamental_scores": fundamental_scores,
        "event_scores": event_scores,
    }
