"""LangGraph multi-agent system graphs and node functions.

Exports:
    - build_research_graph: Research pipeline with planner/critic/ledger + iteration loop
    - build_research_graph_legacy: Original sequential pipeline (5 nodes, no loop)
    - build_research_graph_with_routing: Dynamic routing via supervisor
    - Eight agent node functions: planner, news, quant, research, risk, critic, strategy, ledger
"""
from __future__ import annotations

from legacy.agents.graphs.planner_agent import planner_agent_node
from legacy.agents.graphs.news_agent import news_agent_node
from legacy.agents.graphs.quant_agent import quant_agent_node
from legacy.agents.graphs.research_agent import research_agent_node
from legacy.agents.graphs.risk_agent import risk_agent_node
from legacy.agents.graphs.critic_agent import critic_agent_node
from legacy.agents.graphs.strategy_agent import strategy_agent_node
from legacy.agents.graphs.ledger_node import ledger_agent_node
from legacy.agents.graphs.supervisor import (
    build_research_graph,
    build_research_graph_legacy,
    build_research_graph_with_routing,
)

__all__ = [
    "planner_agent_node",
    "news_agent_node",
    "quant_agent_node",
    "research_agent_node",
    "risk_agent_node",
    "critic_agent_node",
    "strategy_agent_node",
    "ledger_agent_node",
    "build_research_graph",
    "build_research_graph_legacy",
    "build_research_graph_with_routing",
]
