"""Knowledge graph summary stage for fund_analysis.

Produces an optional knowledge_graph_summary artifact when host-provided
holdings data is sufficient. Does not fail fund_analysis if KG cannot be built.
Never emits formal Decision or ExecutionLedger.
"""
from __future__ import annotations

from typing import Any

from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.enrichment import enrich_with_events
from src.graph.schema import EventNode


def build_knowledge_graph_summary(
    *,
    positions: list[dict[str, Any]],
    fund_profiles: dict[str, Any],
    holdings: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not positions and not holdings:
        return {
            "enabled": False,
            "fund_count": 0,
            "stock_count": 0,
            "industry_count": 0,
            "theme_count": 0,
            "event_count": 0,
            "top_shared_holdings": [],
            "theme_paths": [],
            "related_events": [],
            "limitations": ["No holdings data available to build knowledge graph"],
        }

    fund_data_list = _build_fund_data_from_positions(positions, holdings, fund_profiles)

    if not fund_data_list:
        return {
            "enabled": False,
            "fund_count": 0,
            "stock_count": 0,
            "industry_count": 0,
            "theme_count": 0,
            "event_count": 0,
            "top_shared_holdings": [],
            "theme_paths": [],
            "related_events": [],
            "limitations": ["Insufficient holdings data to build knowledge graph"],
        }

    kg = KnowledgeGraph()
    if len(fund_data_list) == 1:
        kg.build_from_holdings(fund_data_list[0])
    else:
        kg.build_from_holdings(fund_data_list[0])
        kg.refresh(fund_data_list[1:])

    event_nodes = _parse_host_events(events)
    affected_entities = []
    if event_nodes and kg.graph is not None:
        for node_id in list(kg.graph.nodes):
            if node_id.startswith("stock:") or node_id.startswith("industry:"):
                affected_entities.append(node_id)
        enrich_with_events(kg.graph, event_nodes, affected_entities)

    if kg.graph is None:
        return {
            "enabled": False,
            "fund_count": 0,
            "stock_count": 0,
            "industry_count": 0,
            "theme_count": 0,
            "event_count": 0,
            "top_shared_holdings": [],
            "theme_paths": [],
            "related_events": [],
            "limitations": ["Knowledge graph build returned empty"],
        }

    fund_count = sum(1 for n in kg.graph.nodes if n.startswith("fund:"))
    stock_count = sum(1 for n in kg.graph.nodes if n.startswith("stock:"))
    industry_count = sum(1 for n in kg.graph.nodes if n.startswith("industry:"))
    theme_count = sum(1 for n in kg.graph.nodes if n.startswith("theme:"))
    event_count = sum(1 for n in kg.graph.nodes if n.startswith("event:"))

    fund_codes = [n.replace("fund:", "") for n in kg.graph.nodes if n.startswith("fund:")]
    top_shared = _compute_top_shared_holdings(kg, fund_codes)
    theme_paths = _compute_theme_paths(kg, fund_codes)
    related_events = _compute_related_events(kg, fund_codes)

    limitations = []
    if stock_count == 0:
        limitations.append("No stock nodes in knowledge graph")
    if industry_count == 0:
        limitations.append("No industry nodes in knowledge graph")
    if event_count == 0 and not events:
        limitations.append("No host-provided events; event relations not available")

    return {
        "enabled": True,
        "fund_count": fund_count,
        "stock_count": stock_count,
        "industry_count": industry_count,
        "theme_count": theme_count,
        "event_count": event_count,
        "top_shared_holdings": top_shared,
        "theme_paths": theme_paths,
        "related_events": related_events,
        "limitations": limitations,
    }


def _build_fund_data_from_positions(
    positions: list[dict[str, Any]],
    holdings: dict[str, Any],
    fund_profiles: dict[str, Any],
) -> list[dict[str, Any]]:
    fund_data_list: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for pos in positions:
        fund_code = pos.get("fund_code", "")
        if not fund_code or fund_code in seen_codes:
            continue
        seen_codes.add(fund_code)

        fund_holdings = holdings.get(fund_code, [])
        if isinstance(fund_holdings, dict):
            fund_holdings = fund_holdings.get("holdings", [])

        profile = fund_profiles.get(fund_code, {})
        if isinstance(fund_profiles, list):
            profile = next((p for p in fund_profiles if p.get("fund_code") == fund_code), {})

        normalized_holdings = _normalize_holdings(fund_holdings)

        sectors = profile.get("sectors", [])
        if not sectors and normalized_holdings:
            sectors = _infer_sectors_from_holdings(normalized_holdings)

        fund_data_list.append({
            "code": fund_code,
            "name": pos.get("fund_name", profile.get("fund_name", "")),
            "fund_type": profile.get("fund_type", ""),
            "holdings": normalized_holdings,
            "sectors": sectors,
        })

    return fund_data_list


def _normalize_holdings(holdings_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for h in holdings_list:
        if not isinstance(h, dict):
            continue
        stock_code = h.get("stock_code", h.get("code", ""))
        if not stock_code:
            continue
        normalized.append({
            "stock_code": stock_code,
            "stock_name": h.get("stock_name", h.get("name", "")),
            "weight": float(h.get("weight", h.get("holding_weight", 0))),
            "sector": h.get("sector", ""),
            "industry": h.get("industry", ""),
        })
    return normalized


def _infer_sectors_from_holdings(holdings_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sector_map: dict[str, float] = {}
    for h in holdings_list:
        sector = h.get("sector", h.get("industry", ""))
        weight = float(h.get("weight", 0))
        if sector:
            sector_map[sector] = sector_map.get(sector, 0) + weight
    return [{"industry": k, "weight": v} for k, v in sorted(sector_map.items(), key=lambda x: -x[1])]


def _parse_host_events(events: list[dict[str, Any]] | None) -> list[EventNode]:
    if not events:
        return []
    result = []
    for ev in events:
        if isinstance(ev, dict):
            result.append(EventNode(
                event_id=str(ev.get("event_id", ev.get("id", ""))),
                event_type=str(ev.get("event_type", ev.get("type", ""))),
                subtype=str(ev.get("subtype", "")),
                date=str(ev.get("date", "")),
                polarity=float(ev.get("polarity", 0.0)),
                magnitude=float(ev.get("magnitude", 0.0)),
                time_horizon=str(ev.get("time_horizon", "medium")),
                description=str(ev.get("description", "")),
            ))
    return result


def _compute_top_shared_holdings(kg: KnowledgeGraph, fund_codes: list[str]) -> list[dict[str, Any]]:
    if not kg.graph or len(fund_codes) < 2:
        return []
    from src.graph.builder import KnowledgeGraphBuilder
    builder = KnowledgeGraphBuilder()
    overlap = builder.cross_fund_overlap(kg.graph, fund_codes)
    return overlap.get("shared_stocks", [])[:5]


def _compute_theme_paths(kg: KnowledgeGraph, fund_codes: list[str]) -> list[dict[str, Any]]:
    if not kg.graph:
        return []
    from src.graph.builder import KnowledgeGraphBuilder
    builder = KnowledgeGraphBuilder()
    paths = []
    for code in fund_codes[:5]:
        chain = builder.entity_chain(kg.graph, code)
        for holding in chain.get("holdings", []):
            for theme in holding.get("themes", []):
                paths.append({
                    "fund": code,
                    "industry": holding.get("industry", {}).get("name", ""),
                    "theme": theme.get("name", ""),
                })
    return paths[:20]


def _compute_related_events(kg: KnowledgeGraph, fund_codes: list[str]) -> list[dict[str, Any]]:
    if not kg.graph:
        return []
    from src.graph.queries import find_related_events
    result = []
    for code in fund_codes[:5]:
        events = find_related_events(kg, f"fund:{code}")
        for ev in events:
            ev_copy = dict(ev)
            ev_copy["fund_code"] = code
            result.append(ev_copy)
    return result[:20]
