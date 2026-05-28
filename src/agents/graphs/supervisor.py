"""Supervisor graph builder: constructs LangGraph StateGraph with 5 agents.

Provides two graph variants:
  1. build_research_graph — simple sequential pipeline
  2. build_research_graph_with_routing — dynamic routing via supervisor logic

Graph structure (sequential):
    Start → news → quant → risk → research → strategy → END

Graph structure (dynamic):
    Start → supervisor → (routes to next agent based on state completion)
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from src.agents.state import FundResearchState
from src.agents.graphs.news_agent import news_agent_node
from src.agents.graphs.quant_agent import quant_agent_node
from src.agents.graphs.research_agent import research_agent_node
from src.agents.graphs.risk_agent import risk_agent_node
from src.agents.graphs.strategy_agent import strategy_agent_node
from src.agents.supervisor import get_supervisor_routing, AGENT_ORDER

logger = logging.getLogger(__name__)


def build_research_graph() -> StateGraph:
    """Build the sequential research graph with fixed agent order.

    Graph structure:
        Start → news → quant → risk → research → strategy → END

    All five specialized agents run in sequence: news first (data
    prerequisite), followed by quant and risk (parallel-capable but
    sequential in this simplified version), then research (needs
    scores), and finally strategy (synthesizes all results).

    Returns:
        Compiled StateGraph ready for invocation with FundResearchState.
    """
    graph_builder = StateGraph(FundResearchState)

    # Add all five agent nodes
    graph_builder.add_node("news", news_agent_node)
    graph_builder.add_node("quant", quant_agent_node)
    graph_builder.add_node("risk", risk_agent_node)
    graph_builder.add_node("research", research_agent_node)
    graph_builder.add_node("strategy", strategy_agent_node)

    # Sequential edges
    graph_builder.set_entry_point("news")
    graph_builder.add_edge("news", "quant")
    graph_builder.add_edge("quant", "risk")
    graph_builder.add_edge("risk", "research")
    graph_builder.add_edge("research", "strategy")
    graph_builder.add_edge("strategy", END)

    return graph_builder.compile()


def _supervisor_router(state: FundResearchState) -> Literal[
    "news", "quant", "risk", "research", "strategy", "__end__"
]:
    """Route to the next agent based on current state completion.

    Uses get_supervisor_routing from src.agents.supervisor to determine
    which agent should run next. Returns END when all agents done.
    """
    routing = get_supervisor_routing(state)
    next_agent = routing["next_agent"]
    if next_agent == "done":
        return END
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
    return END


def build_research_graph_with_routing() -> StateGraph:
    """Build a dynamic-routing research graph using supervisor logic.

    Instead of fixed sequential edges, this graph uses conditional edges
    from each node to a supervisor router that determines the next agent
    based on which results are already present in state. This enables:
      - Skipping agents whose results are already in state
      - Dynamic reordering in future (for now, still follows AGENT_ORDER)

    Graph structure:
        Start → news ─→ supervisor ─→ quant ─→ supervisor ─→ ... → END
                         ↑               ↑
                     risk ─┘       research ─┘

    Returns:
        Compiled StateGraph with dynamic routing.
    """
    graph_builder = StateGraph(FundResearchState)

    # Add all five agent nodes
    graph_builder.add_node("news", news_agent_node)
    graph_builder.add_node("quant", quant_agent_node)
    graph_builder.add_node("risk", risk_agent_node)
    graph_builder.add_node("research", research_agent_node)
    graph_builder.add_node("strategy", strategy_agent_node)

    # Set entry point
    graph_builder.set_entry_point("news")

    # Each node conditionally routes to the next via supervisor
    graph_builder.add_conditional_edges("news", _supervisor_router)
    graph_builder.add_conditional_edges("quant", _supervisor_router)
    graph_builder.add_conditional_edges("risk", _supervisor_router)
    graph_builder.add_conditional_edges("research", _supervisor_router)
    graph_builder.add_conditional_edges("strategy", _supervisor_router)

    return graph_builder.compile()
