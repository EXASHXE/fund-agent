"""LangGraph multi-agent system graphs and node functions.

Exports:
    - build_research_graph: Sequential research pipeline graph
    - build_research_graph_with_routing: Dynamic routing via supervisor
    - Five agent node functions: news, quant, research, risk, strategy
"""
from __future__ import annotations

from src.agents.graphs.news_agent import news_agent_node
from src.agents.graphs.quant_agent import quant_agent_node
from src.agents.graphs.research_agent import research_agent_node
from src.agents.graphs.risk_agent import risk_agent_node
from src.agents.graphs.strategy_agent import strategy_agent_node
from src.agents.graphs.supervisor import build_research_graph, build_research_graph_with_routing

__all__ = [
    "news_agent_node",
    "quant_agent_node",
    "research_agent_node",
    "risk_agent_node",
    "strategy_agent_node",
    "build_research_graph",
    "build_research_graph_with_routing",
]
