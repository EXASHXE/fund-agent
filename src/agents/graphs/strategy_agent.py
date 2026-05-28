"""StrategyAgent graph node: final strategy synthesis and risk assessment.

For each fund in state, runs StrategyEngine.analyze_fund() combining all
scoring dimensions, then aggregates portfolio-level strategy summary.
"""
from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from src.agents.state import FundResearchState
from src.analysis.scoring.engine import ScoreEngine
from src.analysis.scoring.types import CompositeScore, MarketRegime, ScoreComponent
from src.strategy.engine import StrategyEngine

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


def _get_score_value(score: Any) -> float:
    """Extract float value from ScoreComponent or raw float."""
    if isinstance(score, ScoreComponent):
        return score.score
    if isinstance(score, (int, float)):
        return float(score)
    return 50.0


def strategy_agent_node(state: FundResearchState) -> dict:
    """Synthesize final strategy advice and risk assessments for all funds.

    Reads all scores, KG, events, and fund data from state. For each fund:
      1. Calls StrategyEngine.analyze_fund() for strategy advice
      2. Computes composite final score via ScoreEngine
      3. Extracts risk_assessments from strategy output
      4. Aggregates portfolio-level strategy summary.

    Args:
        state: FundResearchState with all scoring results and fund data.

    Returns:
        Dict with strategies, risk_assessments, final_scores,
        and portfolio_strategy.
    """
    funds_data = state.get("funds_data", {})
    if not funds_data:
        return {"strategies": {}, "risk_assessments": {}, "final_scores": {}, "portfolio_strategy": {}}

    kg = _resolve_kg(state)
    extracted_events = state.get("extracted_events", {})

    quant_scores = state.get("quant_scores", {})
    fundamental_scores = state.get("fundamental_scores", {})
    event_scores = state.get("event_scores", {})
    position_scores = state.get("position_scores", {})
    timing_scores = state.get("timing_scores", {})

    strategy_engine = StrategyEngine()
    score_engine = ScoreEngine()

    strategies: dict[str, Any] = {}
    risk_assessments: dict[str, dict] = {}
    final_scores: dict[str, float] = {}

    for fund_code, fund_data in funds_data.items():
        events = extracted_events.get(fund_code, [])
        if not isinstance(events, list):
            events = []

        # Strategy advice
        try:
            advice = strategy_engine.analyze_fund(fund_code, fund_data, kg, events)
            strategies[fund_code] = advice

            # Risk assessment from advice
            risk_assessments[fund_code] = {
                "risk_level": advice.risk_level,
                "action": advice.action.value,
                "confidence": advice.confidence,
                "stop_loss_pct": advice.stop_loss_pct,
                "take_profit_pct": advice.take_profit_pct,
                "time_horizon": advice.time_horizon,
            }
        except Exception as exc:
            logger.error("Strategy analysis failed for %s: %s", fund_code, exc)
            strategies[fund_code] = {"error": str(exc)}
            risk_assessments[fund_code] = {
                "risk_level": "unknown",
                "error": str(exc),
            }

        # Final composite score
        try:
            composite: CompositeScore = score_engine.compute_composite(
                fund_code, fund_data, kg, events
            )
            final_scores[fund_code] = composite.composite
        except Exception as exc:
            logger.error("Composite score failed for %s: %s", fund_code, exc)
            # Fallback: compute from already available ScoreComponents
            qs = quant_scores.get(fund_code)
            fs = fundamental_scores.get(fund_code)
            es = event_scores.get(fund_code)
            ps_s = position_scores.get(fund_code)
            ts = timing_scores.get(fund_code)

            regime = _parse_regime(state)
            weights = dict(regime.weights())

            composite_val = (
                _get_score_value(qs) * weights.get("quant", 0.40)
                + _get_score_value(fs) * weights.get("fundamental", 0.20)
                + _get_score_value(es) * weights.get("event", 0.15)
                + _get_score_value(ps_s) * weights.get("position", 0.15)
                + _get_score_value(ts) * weights.get("timing", 0.10)
            )
            final_scores[fund_code] = round(composite_val, 2)

    # Portfolio-level strategy summary
    portfolio_strategy: dict[str, Any] = {
        "fund_count": len(funds_data),
        "avg_final_score": (
            round(sum(final_scores.values()) / len(final_scores), 2)
            if final_scores else 0.0
        ),
        "regime": _parse_regime(state).value,
        "action_counts": {},
    }

    # Count actions
    for advice in strategies.values():
        action = getattr(advice, "action", None)
        if action is not None:
            action_value = action.value if hasattr(action, "value") else str(action)
        else:
            action_value = "unknown"
        portfolio_strategy["action_counts"][action_value] = (
            portfolio_strategy["action_counts"].get(action_value, 0) + 1
        )

    return {
        "strategies": strategies,
        "risk_assessments": risk_assessments,
        "final_scores": final_scores,
        "portfolio_strategy": portfolio_strategy,
    }
