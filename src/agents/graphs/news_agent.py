"""NewsAgent graph node: runs the 8-stage news pipeline for all funds.

Reads fund codes and knowledge graph from state, invokes NewsPipeline.run(),
and writes search plans, raw news, classified news, scored news, research
summaries, and extracted events back into state.
"""
from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from src.agents.state import FundResearchState
from src.news.news_pipeline import NewsPipeline

logger = logging.getLogger(__name__)


def _resolve_kg(state: FundResearchState) -> nx.DiGraph:
    """Resolve state's knowledge_graph field into a NetworkX DiGraph.

    Supports both serialized dict form and native nx.DiGraph.
    """
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


def news_agent_node(state: FundResearchState) -> dict:
    """Run the 8-stage NewsPipeline for all funds in state.

    Reads fund codes from funds_data, KG from knowledge_graph, calls
    NewsPipeline.run(), and writes results to state.

    Args:
        state: FundResearchState with funds_data and knowledge_graph.

    Returns:
        Dict of state updates for search_plans, raw_news, classified_news,
        scored_news, research_summaries, and extracted_events.
    """
    funds_data = state.get("funds_data", {})
    if not funds_data:
        return {
            "search_plans": {},
            "raw_news": {},
            "classified_news": {},
            "scored_news": {},
            "research_summaries": {},
            "extracted_events": {},
        }

    graph = _resolve_kg(state)
    fund_codes = list(funds_data.keys())

    if not fund_codes:
        return {
            "search_plans": {},
            "raw_news": {},
            "classified_news": {},
            "scored_news": {},
            "research_summaries": {},
            "extracted_events": {},
        }

    pipeline = NewsPipeline()
    try:
        pipeline_results = pipeline.run(fund_codes, graph)
    except Exception as exc:
        logger.error("NewsPipeline.run() failed: %s", exc)
        return {
            "search_plans": {},
            "raw_news": {},
            "classified_news": {},
            "scored_news": {},
            "research_summaries": {},
            "extracted_events": {},
            "errors": state.get("errors", []) + [f"news_agent: {exc}"],
        }

    # Map per-fund results to state keys
    search_plans: dict[str, Any] = {}
    raw_news: dict[str, list[dict]] = {}
    classified_news: dict[str, list[dict]] = {}
    scored_news: dict[str, list[dict]] = {}
    research_summaries: dict[str, list[dict]] = {}
    extracted_events: dict[str, list[dict]] = {}

    for fund_code in fund_codes:
        result = pipeline_results.get(fund_code, {})
        search_plans[fund_code] = result.get("search_plan", {})
        raw_news[fund_code] = result.get("raw_news", [])
        classified_news[fund_code] = result.get("classified_news", [])
        scored_news[fund_code] = result.get("scored_news", [])
        research_summaries[fund_code] = result.get("research_summaries", [])
        extracted_events[fund_code] = result.get("events", [])

    return {
        "search_plans": search_plans,
        "raw_news": raw_news,
        "classified_news": classified_news,
        "scored_news": scored_news,
        "research_summaries": research_summaries,
        "extracted_events": extracted_events,
    }
