"""RiskAgent graph node: position risk and timing scoring.

For each fund in state, computes PositionScore using holdings concentration
analysis and TimingScore using market regime + event momentum signals.
"""
from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from legacy.agents.state import FundResearchState
from legacy.analysis.scoring.position import PositionScoreCalculator
from legacy.analysis.scoring.timing import TimingScoreCalculator
from legacy.analysis.scoring.types import MarketRegime, ScoreComponent

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


def _parse_regime(state: FundResearchState) -> MarketRegime:
    """Parse market_regime string from state into MarketRegime enum."""
    regime_str = state.get("market_regime", "normal")
    try:
        return MarketRegime(regime_str)
    except (ValueError, TypeError):
        return MarketRegime.NORMAL


def risk_agent_node(state: FundResearchState) -> dict:
    """Compute position risk and timing scores for all funds.

    Reads funds_data, knowledge_graph, market_regime, and extracted_events
    from state. For each fund:
      1. Calls PositionScoreCalculator.compute(fund_data, kg)
      2. Calls TimingScoreCalculator.compute(fund_data, regime, events)
      3. Updates position_scores and timing_scores in state.

    Args:
        state: FundResearchState with funds_data, knowledge_graph, market_regime.

    Returns:
        Dict with position_scores and timing_scores updates.
    """
    funds_data = state.get("funds_data", {})
    if not funds_data:
        return {"position_scores": {}, "timing_scores": {}}

    kg = _resolve_kg(state)
    regime = _parse_regime(state)
    extracted_events = state.get("extracted_events", {})

    position_calc = PositionScoreCalculator()
    timing_calc = TimingScoreCalculator()

    position_scores: dict[str, Any] = {}
    timing_scores: dict[str, Any] = {}

    for fund_code, fund_data in funds_data.items():
        events = extracted_events.get(fund_code, [])
        if not isinstance(events, list):
            events = []

        # Position score
        try:
            ps: ScoreComponent = position_calc.compute(fund_data, kg)
            position_scores[fund_code] = ps
        except Exception as exc:
            logger.error("Position score failed for %s: %s", fund_code, exc)
            position_scores[fund_code] = ScoreComponent(
                score=50.0, detail={"error": str(exc)}, weights={}, confidence=0.1,
            )

        # Timing score
        try:
            ts: ScoreComponent = timing_calc.compute(fund_data, regime, events)
            timing_scores[fund_code] = ts
        except Exception as exc:
            logger.error("Timing score failed for %s: %s", fund_code, exc)
            timing_scores[fund_code] = ScoreComponent(
                score=50.0, detail={"error": str(exc)}, weights={}, confidence=0.1,
            )

    return {
        "position_scores": position_scores,
        "timing_scores": timing_scores,
    }
