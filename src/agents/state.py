"""LangGraph state definition: shared state across all agents."""
from __future__ import annotations

from typing import Any, TypedDict


class FundResearchState(TypedDict, total=False):
    """Shared state across all LangGraph agents.

    Used as the state schema for the supervisor graph.
    All fields are optional (total=False) to allow partial updates.

    Fields are organized by layer:
      - Input: portfolio_config, report_date
      - Data: funds_data, knowledge_graph
      - News pipeline: search_plans, raw_news, classified_news, scored_news, ...
      - Scoring: quant_scores, fundamental_scores, event_scores, position_scores, timing_scores, final_scores
      - Strategy: risk_assessments, strategies, portfolio_strategy
      - Planner: research_tasks, planner_iteration_log
      - Critic: critic_report
      - Ledger: final_thesis, execution_ledger, phase
      - Orchestration: iteration, next_agent, errors
    """
    # Input
    portfolio_config: dict
    report_date: str

    # Data layer (populated by tools)
    funds_data: dict
    knowledge_graph: dict         # KG snapshot (serializable dict, not nx.Graph)
                                   # Keys: {nodes: [...], edges: [...], exposures: {fund_code: {...}}}

    # News pipeline results
    search_plans: dict            # Per-fund SearchPlan
    raw_news: dict                # Per-fund raw news pool
    classified_news: dict         # Per-fund classified news
    scored_news: dict             # Per-fund scored+reranked news
    research_summaries: dict      # Per-fund research-style summaries
    extracted_events: dict        # Per-fund extracted events

    # Scoring results
    market_regime: str            # Detected regime
    quant_scores: dict            # Per-fund QuantScore
    fundamental_scores: dict      # Per-fund FundamentalScore
    event_scores: dict            # Per-fund EventScore
    position_scores: dict         # Per-fund PositionScore
    timing_scores: dict           # Per-fund TimingScore
    final_scores: dict            # Per-fund composite scores

    # Strategy results
    risk_assessments: dict        # Per-fund risk assessment
    strategies: dict              # Per-fund StrategyAdvice
    portfolio_strategy: dict      # Portfolio-level strategy

    # Planner (Phase 6)
    research_tasks: list[dict]           # Emitted by planner_agent_node
    planner_iteration_log: list[dict]    # History of planner iterations

    # Critic (Phase 6)
    critic_report: dict[str, Any]        # bias, gaps, conflicts, passed
    critic_iteration: int                # How many critique rounds

    # Ledger (Phase 6)
    final_thesis: dict[str, Any]         # Structured research conclusions
    execution_ledger: dict[str, Any]     # Trade-ready decisions
    phase: str                           # lifecycle: planning | scoring | review | complete

    # Orchestration
    iteration: int
    next_agent: str
    errors: list[str]


# Empty state template for initialization
EMPTY_STATE: FundResearchState = {
    "portfolio_config": {},
    "report_date": "",
    "funds_data": {},
    "knowledge_graph": {},
    "search_plans": {},
    "raw_news": {},
    "classified_news": {},
    "scored_news": {},
    "research_summaries": {},
    "extracted_events": {},
    "market_regime": "normal",
    "quant_scores": {},
    "fundamental_scores": {},
    "event_scores": {},
    "position_scores": {},
    "timing_scores": {},
    "final_scores": {},
    "risk_assessments": {},
    "strategies": {},
    "portfolio_strategy": {},
    "research_tasks": [],
    "planner_iteration_log": [],
    "critic_report": {},
    "critic_iteration": 0,
    "final_thesis": {},
    "execution_ledger": {},
    "phase": "planning",
    "iteration": 0,
    "next_agent": "",
    "errors": [],
}
