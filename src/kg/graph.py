"""Knowledge Graph builder: construct and query the fund-stock-industry-event graph."""
from __future__ import annotations

from typing import Any

import networkx as nx

from src.kg.schema import (
    KGNodeType, KGEdgeType, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
)
from src.kg.industry_map import get_themes_for_industry, get_keywords_for_theme


class KnowledgeGraphBuilder:
    """Build and query a knowledge graph from fund holdings data."""

    def build_from_holdings(self, fund_data: dict) -> nx.DiGraph:
        """Build KG from fund holdings data.

        Args:
            fund_data: Dict with keys: code, name, fund_type, holdings, sectors.

        Returns:
            NetworkX DiGraph with fund, stock, industry, theme nodes and edges.
        """
        G = nx.DiGraph()

        # Create fund node — use string ID as NetworkX node, dataclass as "data" attr
        fund_node = FundNode(
            code=fund_data["code"],
            name=fund_data.get("name", ""),
            fund_type=fund_data.get("fund_type", ""),
            style=fund_data.get("style", ""),
        )
        G.add_node(fund_node.id, data=fund_node)

        # Create stock nodes and HOLDS edges
        holdings = fund_data.get("holdings", [])
        for holding in holdings:
            stock_node = StockNode(
                code=holding["stock_code"],
                name=holding.get("stock_name", ""),
                sector=holding.get("sector", ""),
                industry=holding.get("industry", ""),
            )
            G.add_node(stock_node.id, data=stock_node)
            holds_edge = KGEdge(
                source=f"fund:{fund_data['code']}",
                target=f"stock:{holding['stock_code']}",
                edge_type=KGEdgeType.HOLDS,
                weight=holding.get("weight", 0),
            )
            G.add_edge(fund_node.id, stock_node.id, edge_data=holds_edge)

        # Create industry nodes from sectors data
        sectors = fund_data.get("sectors", [])
        for sector_info in sectors:
            industry_name = sector_info.get("industry", "")
            if not industry_name:
                continue
            industry_node = IndustryNode(
                code=f"sw_{industry_name}",
                name=industry_name,
                sw_code=sector_info.get("sw_code", ""),
            )
            if not G.has_node(industry_node.id):
                G.add_node(industry_node.id, data=industry_node)
            # EXPOSES edge: fund → industry
            exposes_edge = KGEdge(
                source=f"fund:{fund_data['code']}",
                target=industry_node.id,
                edge_type=KGEdgeType.EXPOSES,
                weight=sector_info.get("weight", 0),
            )
            G.add_edge(fund_node.id, industry_node.id, edge_data=exposes_edge)

            # Create theme nodes and IN_THEME edges
            themes = get_themes_for_industry(industry_name)
            for theme_name in themes:
                theme_node = ThemeNode(name=theme_name, keywords=get_keywords_for_theme(theme_name))
                if not G.has_node(theme_node.id):
                    G.add_node(theme_node.id, data=theme_node)
                in_theme_edge = KGEdge(
                    source=industry_node.id,
                    target=theme_node.id,
                    edge_type=KGEdgeType.IN_THEME,
                )
                G.add_edge(industry_node.id, theme_node.id, edge_data=in_theme_edge)

        # Create BELONGS_TO edges: stock → industry
        # First from explicit industry in holdings
        stock_industries = {}
        for holding in holdings:
            stock_code = holding["stock_code"]
            industry = holding.get("industry", "")
            if industry:
                stock_industries[stock_code] = industry
                stock_id = f"stock:{stock_code}"
                industry_id = f"industry:sw_{industry}"
                if G.has_node(stock_id) and G.has_node(industry_id):
                    belongs_edge = KGEdge(
                        source=stock_id,
                        target=industry_id,
                        edge_type=KGEdgeType.BELONGS_TO,
                    )
                    G.add_edge(stock_id, industry_id, edge_data=belongs_edge)

        # For stocks without explicit industry, assign to first sector
        for holding in holdings:
            stock_id = f"stock:{holding['stock_code']}"
            if holding["stock_code"] not in stock_industries:
                # Assign to first sector industry
                for sector_info in sectors:
                    industry_name = sector_info.get("industry", "")
                    industry_id = f"industry:sw_{industry_name}"
                    if G.has_node(stock_id) and G.has_node(industry_id):
                        belongs_edge = KGEdge(
                            source=stock_id,
                            target=industry_id,
                            edge_type=KGEdgeType.BELONGS_TO,
                        )
                        G.add_edge(stock_id, industry_id, edge_data=belongs_edge)
                        break

        return G

    def query_relevance(
        self,
        graph: nx.DiGraph,
        fund_code: str,
        news_item: dict,
        stock_hit_weight: float = 0.25,
        top10_hit_weight: float = 0.20,
        industry_hit_weight: float = 0.15,
        theme_hit_weight: float = 0.10,
        timeliness_weight: float = 0.10,
        severity_weight: float = 0.10,
    ) -> float:
        """Query KG for fund-news relevance score.

        Multi-factor relevance:
        - holding overlap, top-10 hit, industry hit, theme hit, timeliness, severity
        """
        fund_id = f"fund:{fund_code}"
        if not graph.has_node(fund_id):
            return 0.0

        # Get fund's holdings
        hold_edges = []
        for src, dst, data in graph.edges(data=True):
            edge = data.get("edge_data")
            if src == fund_id and edge and edge.edge_type == KGEdgeType.HOLDS:
                hold_edges.append((src, dst, edge))

        holding_codes = set()
        for _, dst, edge in hold_edges:
            stock_code = dst.replace("stock:", "")
            holding_codes.add(stock_code)

        # Get fund's industries and themes
        fund_industries = set()
        fund_themes = set()
        for _, dst, data in graph.edges(fund_id, data=True):
            edge = data.get("edge_data")
            if edge:
                if edge.edge_type == KGEdgeType.EXPOSES:
                    fund_industries.add(dst)
                elif edge.edge_type == KGEdgeType.HOLDS:
                    pass  # Already handled

        # Traverse: industry → theme
        for ind_id in fund_industries:
            for _, theme_dst, _ in graph.edges(ind_id, data=True):
                fund_themes.add(theme_dst)

        # Check news entity overlap
        news_entities = set(news_item.get("entities", []))
        news_title = news_item.get("title", "")

        # Holding hit
        holding_hit = 0.0
        for code in holding_codes:
            if code in news_entities or code in news_title:
                holding_hit = 1.0
                break

        # Industry hit
        industry_hit = 0.0
        for ind_id in fund_industries:
            ind_name = ind_id.replace("industry:sw_", "")
            if ind_name in news_title:
                industry_hit = 1.0
                break

        # Theme hit
        theme_hit = 0.0
        keywords_all = set()
        for theme_id in fund_themes:
            theme_name = theme_id.replace("theme:", "")
            keywords_all.update(get_keywords_for_theme(theme_name))
            if theme_name in news_title:
                theme_hit = 1.0
                break
        if theme_hit == 0.0:
            for kw in keywords_all:
                if kw in news_title:
                    theme_hit = 0.5
                    break

        # Timeliness (default 1.0 — computed externally)
        timeliness = 1.0
        # Severity (default 0.5)
        severity = abs(news_item.get("sentiment", 0.5))

        relevance = (
            holding_hit * stock_hit_weight
            + min(1.0, holding_hit) * top10_hit_weight
            + industry_hit * industry_hit_weight
            + theme_hit * theme_hit_weight
            + timeliness * timeliness_weight
            + severity * severity_weight
        )
        return min(1.0, relevance)

    def get_fund_exposure(self, graph: nx.DiGraph, fund_code: str) -> dict:
        """Get fund's industry/theme/macro exposure profile from KG."""
        fund_id = f"fund:{fund_code}"
        if not graph.has_node(fund_id):
            return {"industries": [], "themes": [], "macro_factors": []}

        industries = []
        themes = []
        macro_factors = []

        for _, dst, data in graph.edges(fund_id, data=True):
            edge = data.get("edge_data")
            if not edge:
                continue
            if edge.edge_type == KGEdgeType.EXPOSES:
                ind_name = dst.replace("industry:sw_", "")
                industries.append({"name": ind_name, "weight": edge.weight or 0})

        # Get themes through industry → theme edges
        seen_themes = set()
        for ind in industries:
            full_ind_id = f"industry:sw_{ind['name']}" if not ind["name"].startswith("industry:") else ind["name"]
            if graph.has_node(full_ind_id):
                for _, theme_dst, _ in graph.edges(full_ind_id, data=True):
                    theme_name = theme_dst.replace("theme:", "")
                    if theme_name not in seen_themes:
                        seen_themes.add(theme_name)
                        themes.append(theme_name)

        return {
            "industries": list(set(ind["name"] for ind in industries)),
            "themes": list(seen_themes),
            "macro_factors": macro_factors,
        }

    def get_impact_chain(self, graph: nx.DiGraph, event_id: str, fund_code: str) -> dict:
        """Trace event impact through KG to affected funds."""
        event_node_id = f"event:{event_id}"
        fund_id = f"fund:{fund_code}"

        if not graph.has_node(event_node_id) or not graph.has_node(fund_id):
            return {"total_polarity": 0.0, "total_magnitude": 0.0, "paths": []}

        paths = []
        total_polarity = 0.0
        total_magnitude = 0.0

        # Direct: event → stock → fund (via HOLDS reverse)
        for _, stock_dst, impact_data in graph.edges(event_node_id, data=True):
            impact_edge = impact_data.get("edge_data")
            if impact_edge and impact_edge.edge_type == KGEdgeType.IMPACTS:
                for fund_src, _, hold_data in graph.in_edges(stock_dst, data=True):
                    if fund_src == fund_id:
                        hold_edge = hold_data.get("edge_data")
                        if hold_edge and hold_edge.edge_type == KGEdgeType.HOLDS:
                            hold_weight = hold_edge.weight or 0
                            path_polarity = (impact_edge.polarity or 0) * (hold_weight / 100.0)
                            path_magnitude = (impact_edge.magnitude or 0) * (hold_weight / 100.0)
                            total_polarity += path_polarity
                            total_magnitude += path_magnitude
                            paths.append({
                                "event": event_id,
                                "stock": stock_dst,
                                "fund": fund_id,
                                "polarity": impact_edge.polarity,
                                "magnitude": impact_edge.magnitude,
                                "hold_weight": hold_weight,
                            })

        # Indirect: event → industry → fund (via EXPOSES reverse)
        for _, ind_dst, impact_data in graph.edges(event_node_id, data=True):
            impact_edge = impact_data.get("edge_data")
            if impact_edge and impact_edge.edge_type == KGEdgeType.IMPACTS:
                for fund_src, _, expose_data in graph.in_edges(ind_dst, data=True):
                    if fund_src == fund_id:
                        expose_edge = expose_data.get("edge_data")
                        if expose_edge and expose_edge.edge_type == KGEdgeType.EXPOSES:
                            exposure_weight = expose_edge.weight or 0
                            path_polarity = (impact_edge.polarity or 0) * (exposure_weight / 100.0)
                            path_magnitude = (impact_edge.magnitude or 0) * (exposure_weight / 100.0)
                            total_polarity += path_polarity
                            total_magnitude += path_magnitude
                            paths.append({
                                "event": event_id,
                                "industry": ind_dst,
                                "fund": fund_id,
                                "polarity": impact_edge.polarity,
                                "magnitude": impact_edge.magnitude,
                                "exposure_weight": exposure_weight,
                            })

        return {
            "total_polarity": round(total_polarity, 4),
            "total_magnitude": round(total_magnitude, 4),
            "paths": paths,
        }