"""Supervisor graph builder: constructs LangGraph StateGraph with 8 agents.

Graph structure (new, with iteration loop):

    planner ─→ news ─→ quant ─→ risk ─→ research ─→ critic
       ↑                                                │
       │                     ┌──────────────────────────┤
       │                     │ (not passed AND iter < 3) │
       └─────────────────────┘                          │
                                                        ↓
                                                   strategy ─→ ledger ─→ END

Provides three graph variants:
  1. build_research_graph — full graph with planner/critic/ledger + iteration loop
  2. build_research_graph_legacy — original sequential pipeline (5 agents, no loop)
  3. build_research_graph_with_routing — dynamic routing via supervisor logic
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from legacy.agents.state import FundResearchState
from legacy.agents.graphs.planner_agent import planner_agent_node
from legacy.agents.graphs.news_agent import news_agent_node
from legacy.agents.graphs.quant_agent import quant_agent_node
from legacy.agents.graphs.research_agent import research_agent_node
from legacy.agents.graphs.risk_agent import risk_agent_node
from legacy.agents.graphs.critic_agent import critic_agent_node
from legacy.agents.graphs.strategy_agent import strategy_agent_node
from legacy.agents.graphs.ledger_node import ledger_agent_node
from legacy.agents.supervisor import AGENT_ORDER, get_supervisor_routing

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy sequential graph (5 agents, no iteration loop)
# ---------------------------------------------------------------------------

def build_research_graph_legacy() -> StateGraph:
    """Build the sequential research graph with fixed agent order.

    Legacy variant — 5 agents, no planner/critic/ledger, no iteration loop.

    Graph structure:
        Start → news → quant → risk → research → strategy → END

    Returns:
        Compiled StateGraph ready for invocation with FundResearchState.
    """
    graph_builder = StateGraph(FundResearchState)

    graph_builder.add_node("news", news_agent_node)
    graph_builder.add_node("quant", quant_agent_node)
    graph_builder.add_node("risk", risk_agent_node)
    graph_builder.add_node("research", research_agent_node)
    graph_builder.add_node("strategy", strategy_agent_node)

    graph_builder.set_entry_point("news")
    graph_builder.add_edge("news", "quant")
    graph_builder.add_edge("quant", "risk")
    graph_builder.add_edge("risk", "research")
    graph_builder.add_edge("research", "strategy")
    graph_builder.add_edge("strategy", END)

    return graph_builder.compile()


# ---------------------------------------------------------------------------
# New full graph with planner, critic, ledger, and iteration loop
# ---------------------------------------------------------------------------

def _critic_router(state: FundResearchState) -> Literal["planner", "strategy"]:
    """Route after critic: loop back to planner or proceed to strategy.

    Logic:
      - If critic_report.passed == True → strategy
      - If iteration >= 3 (circuit breaker) → strategy
      - Otherwise → loop back to planner

    The critic node itself forces passed=True when the circuit breaker
    triggers (iteration >= 3), so both conditions converge to strategy.
    """
    critic_report = state.get("critic_report", {})
    iteration = state.get("iteration", 1)

    if critic_report.get("passed", False) or iteration >= 3:
        logger.info(
            "Critic passed=True or iteration=%d >= 3 → routing to strategy",
            iteration,
        )
        return "strategy"

    logger.info("Critic found gaps, iteration=%d < 3 → looping to planner", iteration)
    return "planner"


def build_research_graph() -> StateGraph:
    """Build the full research graph with planner, critic, ledger, and iteration loop.

    This is the Phase 6 graph that adds iterative refinement:
      1. Planner — identifies research gaps and emits tasks
      2. News — fetches and scores news for all funds
      3. Quant — computes quantitative scores
      4. Risk — assesses risk factors and timing
      5. Research — scores fundamental, event, position dimensions
      6. Critic — reviews for gaps/bias; if passed or iter>=3 → strategy, else → planner
      7. Strategy — synthesizes final advice
      8. Ledger — produces FinalThesis + ExecutionLedger

    Circuit breaker: if iteration >= 3, critic forces pass and routes to strategy.

    Graph structure:
        planner → news → quant → risk → research → critic
           ↑                                                │
           └────────── (loop if not passed AND iter < 3) ───┘
                                                           ↓
                                                      strategy → ledger → END

    Returns:
        Compiled StateGraph ready for invocation with FundResearchState.
    """
    graph_builder = StateGraph(FundResearchState)

    # Add all eight agent nodes
    graph_builder.add_node("planner", planner_agent_node)
    graph_builder.add_node("news", news_agent_node)
    graph_builder.add_node("quant", quant_agent_node)
    graph_builder.add_node("risk", risk_agent_node)
    graph_builder.add_node("research", research_agent_node)
    graph_builder.add_node("critic", critic_agent_node)
    graph_builder.add_node("strategy", strategy_agent_node)
    graph_builder.add_node("ledger", ledger_agent_node)

    # Entry point: planner first
    graph_builder.set_entry_point("planner")

    # Sequential pipeline: planner → news → quant → risk → research → critic
    graph_builder.add_edge("planner", "news")
    graph_builder.add_edge("news", "quant")
    graph_builder.add_edge("quant", "risk")
    graph_builder.add_edge("risk", "research")
    graph_builder.add_edge("research", "critic")

    # Conditional edge from critic: loop back to planner or proceed to strategy
    graph_builder.add_conditional_edges(
        "critic",
        _critic_router,
        {"planner": "planner", "strategy": "strategy"},
    )

    # Terminal path: strategy → ledger → END
    graph_builder.add_edge("strategy", "ledger")
    graph_builder.add_edge("ledger", END)

    return graph_builder.compile()


# ---------------------------------------------------------------------------
# Dynamic routing graph (keeps original 5 agents, uses supervisor router)
# ---------------------------------------------------------------------------

def _supervisor_router(state: FundResearchState) -> Literal[
    "news", "quant", "risk", "research", "strategy", "__end__"
]:
    """Route to the next agent based on current state completion.

    Uses get_supervisor_routing from legacy.agents.supervisor to determine
    which agent should run next. Returns END when all agents done.
    """
    routing = get_supervisor_routing(state)
    next_agent = routing["next_agent"]
    if next_agent == "done":
        return END  # type: ignore[return-value]
    if next_agent in AGENT_ORDER:
        return next_agent  # type: ignore[return-value]
    # Fallback: follow sequential order
    has_news = bool(state.get("scored_news"))
    has_quant = bool(state.get("quant_scores"))
    has_risk = bool(state.get("risk_assessments"))
    has_research = bool(state.get("fundamental_scores") and state.get("timing_scores"))
    has_strategy = bool(state.get("strategies"))
    if not has_news:
        return "news"
    if not has_quant:
        return "quant"
    if not has_risk:
        return "risk"
    if not has_research:
        return "research"
    if not has_strategy:
        return "strategy"
    return END  # type: ignore[return-value]


def build_research_graph_with_routing() -> StateGraph:
    """Build a dynamic-routing research graph using supervisor logic.

    Instead of fixed sequential edges, this graph uses conditional edges
    from each node to a supervisor router that determines the next agent
    based on which results are already present in state.

    Graph structure:
        Start → news ─→ supervisor ─→ quant ─→ supervisor ─→ ... → END
                         ↑               ↑
                     risk ─┘       research ─┘

    Returns:
        Compiled StateGraph with dynamic routing (5 original agents only).
    """
    graph_builder = StateGraph(FundResearchState)

    graph_builder.add_node("news", news_agent_node)
    graph_builder.add_node("quant", quant_agent_node)
    graph_builder.add_node("risk", risk_agent_node)
    graph_builder.add_node("research", research_agent_node)
    graph_builder.add_node("strategy", strategy_agent_node)

    graph_builder.set_entry_point("news")

    graph_builder.add_conditional_edges("news", _supervisor_router)
    graph_builder.add_conditional_edges("quant", _supervisor_router)
    graph_builder.add_conditional_edges("risk", _supervisor_router)
    graph_builder.add_conditional_edges("research", _supervisor_router)
    graph_builder.add_conditional_edges("strategy", _supervisor_router)

    return graph_builder.compile()
