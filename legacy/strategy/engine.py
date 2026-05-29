"""StrategyEngine: top-level strategy analysis orchestrator.

Combines ScoreEngine and StrategyAdvisor into a single pipeline:
  1. Compute composite score via ScoreEngine
  2. Generate strategy advice via StrategyAdvisor
  3. Return StrategyAdvice (per fund) or portfolio-level summary
"""
from __future__ import annotations

import networkx as nx

from legacy.analysis.scoring.engine import ScoreEngine
from legacy.analysis.scoring.types import MarketRegime
from legacy.strategy.advisor import StrategyAdvisor
from legacy.strategy.schemas import StrategyAdvice, StrategyState, StrategyAction


class StrategyEngine:
    """Top-level strategy engine for single-fund analysis and portfolio aggregation.

    Usage:
        engine = StrategyEngine()
        advice = engine.analyze_fund("110011", fund_data, kg, events)

        portfolio_result = engine.analyze_portfolio(fund_list, kg)
        # → {fund_code: StrategyAdvice, portfolio_summary: {...}}
    """

    def __init__(self, llm_client: object | None = None):
        self.advisor = StrategyAdvisor(llm_client=llm_client)
        self.score_engine = ScoreEngine(llm_client=llm_client)

    def analyze_fund(
        self,
        fund_code: str,
        fund_data: dict,
        kg: nx.DiGraph,
        events: list,
        current_state: StrategyState | None = None,
    ) -> StrategyAdvice:
        """Analyze a single fund and return a StrategyAdvice.

        Pipeline:
        1. Compute composite score via ScoreEngine
        2. Generate strategy advice via StrategyAdvisor
        3. Return StrategyAdvice
        """
        composite_score = self.score_engine.compute_composite(
            fund_code, fund_data, kg, events
        )
        advice = self.advisor.generate_advice(
            fund_code=fund_code,
            fund_data=fund_data,
            composite_score=composite_score,
            kg=kg,
            events=events,
            current_state=current_state,
        )
        return advice

    def analyze_portfolio(self, fund_list: list[dict], kg: nx.DiGraph) -> dict:
        """Per-fund analysis → portfolio-level summary.

        Args:
            fund_list: List of fund data dicts, each with at least a "code" field.
            kg: Knowledge graph (shared across all funds).

        Returns:
            Dict mapping fund_code → StrategyAdvice, plus a portfolio_summary key.
        """
        results: dict = {}
        composites: list[float] = []
        actions: list[str] = []
        regimes: set[MarketRegime] = set()

        for fund_data in fund_list:
            code = fund_data.get("code", "unknown")
            # Use events from fund_data if available, otherwise empty
            events = fund_data.get("events", []) if isinstance(fund_data, dict) else []

            advice = self.analyze_fund(code, fund_data, kg, events)
            results[code] = advice
            composites.append(advice.confidence * 100)  # proxy for composite tracking
            actions.append(advice.action.value)
            # Access regime through the advisor; we'll use a best-effort approach
            regimes.add(MarketRegime.NORMAL)  # Default; actual regime is internal

        # Portfolio summary
        avg_composite = round(sum(composites) / len(composites), 1) if composites else 0
        action_counts: dict[str, int] = {}
        for a in actions:
            action_counts[a] = action_counts.get(a, 0) + 1

        primary_regime = MarketRegime.NORMAL
        if regimes:
            # Pick most common or CRISIS if present
            if MarketRegime.CRISIS in regimes:
                primary_regime = MarketRegime.CRISIS
            elif MarketRegime.HIGH_VOLATILITY in regimes:
                primary_regime = MarketRegime.HIGH_VOLATILITY
            else:
                primary_regime = next(iter(regimes), MarketRegime.NORMAL)

        results["portfolio_summary"] = {
            "fund_count": len(fund_list),
            "avg_composite": avg_composite,
            "regime": primary_regime.value,
            "actions": action_counts,
            "action_distribution": action_counts,
        }

        return results
