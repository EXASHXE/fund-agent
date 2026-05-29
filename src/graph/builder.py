"""Knowledge Graph builder: construct and query the fund-stock-industry-event graph."""
from __future__ import annotations

import datetime
import os
import pickle
from typing import Any

import networkx as nx

from src.graph.schema import (
    KGNodeType, KGEdgeType, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
)
from src.graph.industry_map import get_themes_for_industry, get_keywords_for_theme
from src.graph.diff import GraphDiff


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
        self._build_fund_subgraph(G, fund_data)
        return G

    @staticmethod
    def _build_fund_subgraph(G: nx.DiGraph, fund_data: dict) -> None:
        """Add fund->stock->industry->theme subgraph to an existing graph.

        Shared helper used by :meth:`build_from_holdings` and :meth:`refresh`.
        Nodes that already exist in *G* are not duplicated. Edges are always
        added/updated so that the latest data (e.g. holding weight) is reflected.

        Args:
            G: An existing NetworkX DiGraph to extend (modified in place).
            fund_data: Dict with keys: code, name, fund_type, holdings, sectors.
        """
        # -- Fund node ----------------------------------------------------------
        fund_node = FundNode(
            code=fund_data["code"],
            name=fund_data.get("name", ""),
            fund_type=fund_data.get("fund_type", ""),
            style=fund_data.get("style", ""),
        )
        if not G.has_node(fund_node.id):
            G.add_node(fund_node.id, data=fund_node)

        # -- Stock nodes + HOLDS edges ------------------------------------------
        holdings = fund_data.get("holdings", [])
        for holding in holdings:
            stock_node = StockNode(
                code=holding["stock_code"],
                name=holding.get("stock_name", ""),
                sector=holding.get("sector", ""),
                industry=holding.get("industry", ""),
            )
            if not G.has_node(stock_node.id):
                G.add_node(stock_node.id, data=stock_node)

            holds_edge = KGEdge(
                source=fund_node.id,
                target=stock_node.id,
                edge_type=KGEdgeType.HOLDS,
                weight=holding.get("weight", 0),
            )
            G.add_edge(fund_node.id, stock_node.id, edge_data=holds_edge)

        # -- Industry nodes + EXPOSES edges -------------------------------------
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

            exposes_edge = KGEdge(
                source=fund_node.id,
                target=industry_node.id,
                edge_type=KGEdgeType.EXPOSES,
                weight=sector_info.get("weight", 0),
            )
            G.add_edge(fund_node.id, industry_node.id, edge_data=exposes_edge)

            # -- Theme nodes + IN_THEME edges -----------------------------------
            themes = get_themes_for_industry(industry_name)
            for theme_name in themes:
                theme_node = ThemeNode(
                    name=theme_name,
                    keywords=get_keywords_for_theme(theme_name),
                )
                if not G.has_node(theme_node.id):
                    G.add_node(theme_node.id, data=theme_node)

                in_theme_edge = KGEdge(
                    source=industry_node.id,
                    target=theme_node.id,
                    edge_type=KGEdgeType.IN_THEME,
                )
                G.add_edge(industry_node.id, theme_node.id, edge_data=in_theme_edge)

        # -- BELONGS_TO edges: stock -> industry ---------------------------------
        # First pass: explicit industry from holdings
        stock_industries: dict[str, str] = {}
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

        # Second pass: stocks without explicit industry -> first sector
        for holding in holdings:
            stock_id = f"stock:{holding['stock_code']}"
            if holding["stock_code"] not in stock_industries:
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

    @staticmethod
    def refresh(
        existing_graph: nx.DiGraph,
        new_fund_data: list[dict],
    ) -> nx.DiGraph:
        """Incrementally update graph with new fund data.

        Strategy:
        1. Work on a **copy** of the existing graph (original is not mutated).
        2. For each fund in *new_fund_data*:
           - If the fund does **not** exist in the graph, build its full
             fund->stock->industry->theme chain via :meth:`_build_fund_subgraph`.
           - If the fund **does** exist, update its holdings and sector
             exposures, adding new nodes/edges and removing stale ones.
        3. Remove **orphan** nodes (stocks, industries, themes no longer
           reachable from any fund). Event nodes and macro-factor nodes are
           **always preserved**.
        4. Increment the graph version counter.

        Args:
            existing_graph: The previously built knowledge graph.
            new_fund_data: List of fund-data dicts (same shape as the argument
                to :meth:`build_from_holdings`).

        Returns:
            A new :class:`nx.DiGraph` with incremental updates applied.
        """
        G = existing_graph.copy()
        active_fund_codes: set[str] = set()

        for fund_data in new_fund_data:
            fund_code = fund_data["code"]
            fund_id = f"fund:{fund_code}"
            active_fund_codes.add(fund_code)

            if not G.has_node(fund_id):
                # -- New fund: build the full subgraph --------------------------
                KnowledgeGraphBuilder._build_fund_subgraph(G, fund_data)
            else:
                # -- Existing fund: update holdings in place --------------------
                KnowledgeGraphBuilder._update_fund_holdings(G, fund_data)

        # -- Remove orphan nodes (stale stocks, industries, themes) -------------
        KnowledgeGraphBuilder._remove_orphan_nodes(G)

        # -- Bump version -------------------------------------------------------
        G.graph["version"] = G.graph.get("version", 0) + 1

        return G

    @staticmethod
    def _update_fund_holdings(G: nx.DiGraph, fund_data: dict) -> None:
        """Update an existing fund's holdings, sectors, and related edges.

        * Adds new stock nodes and HOLDS edges for newly-held stocks.
        * Removes HOLDS edges for stocks no longer held.
        * Updates industry/sector exposure edges.
        * Adds/removes BELONGS_TO edges accordingly.
        * Adds theme nodes/edges for any new industries.
        """
        fund_code = fund_data["code"]
        fund_id = f"fund:{fund_code}"

        # -- Snapshot current state from the graph ------------------------------
        current_stock_ids: set[str] = set()
        current_industry_ids: set[str] = set()
        for _, dst, edge_data in G.out_edges(fund_id, data=True):
            edge = edge_data.get("edge_data")
            if not edge:
                continue
            if edge.edge_type == KGEdgeType.HOLDS:
                current_stock_ids.add(dst)
            elif edge.edge_type == KGEdgeType.EXPOSES:
                current_industry_ids.add(dst)

        # -- New holdings from fund_data ----------------------------------------
        new_holdings = fund_data.get("holdings", [])
        new_stock_ids: set[str] = set()
        new_holding_map: dict[str, dict] = {}  # stock_id -> holding dict
        for holding in new_holdings:
            stock_id = f"stock:{holding['stock_code']}"
            new_stock_ids.add(stock_id)
            new_holding_map[stock_id] = holding

        # -- Add/update stock nodes and HOLDS edges -----------------------------
        for stock_id, holding in new_holding_map.items():
            if not G.has_node(stock_id):
                stock_node = StockNode(
                    code=holding["stock_code"],
                    name=holding.get("stock_name", ""),
                    sector=holding.get("sector", ""),
                    industry=holding.get("industry", ""),
                )
                G.add_node(stock_id, data=stock_node)

            holds_edge = KGEdge(
                source=fund_id,
                target=stock_id,
                edge_type=KGEdgeType.HOLDS,
                weight=holding.get("weight", 0),
            )
            G.add_edge(fund_id, stock_id, edge_data=holds_edge)

        # -- Remove stale HOLDS edges -------------------------------------------
        stale_stocks = current_stock_ids - new_stock_ids
        for stock_id in stale_stocks:
            if G.has_edge(fund_id, stock_id):
                G.remove_edge(fund_id, stock_id)

        # -- Update industry/sector exposures -----------------------------------
        new_sectors = fund_data.get("sectors", [])
        new_industry_ids: set[str] = set()
        for sector_info in new_sectors:
            industry_name = sector_info.get("industry", "")
            if not industry_name:
                continue
            industry_id = f"industry:sw_{industry_name}"
            new_industry_ids.add(industry_id)

            if not G.has_node(industry_id):
                industry_node = IndustryNode(
                    code=f"sw_{industry_name}",
                    name=industry_name,
                    sw_code=sector_info.get("sw_code", ""),
                )
                G.add_node(industry_id, data=industry_node)

            # (Re-)create EXPOSES edge
            exposes_edge = KGEdge(
                source=fund_id,
                target=industry_id,
                edge_type=KGEdgeType.EXPOSES,
                weight=sector_info.get("weight", 0),
            )
            G.add_edge(fund_id, industry_id, edge_data=exposes_edge)

            # Ensure theme nodes/edges exist for this industry
            themes = get_themes_for_industry(industry_name)
            for theme_name in themes:
                theme_node = ThemeNode(
                    name=theme_name,
                    keywords=get_keywords_for_theme(theme_name),
                )
                if not G.has_node(theme_node.id):
                    G.add_node(theme_node.id, data=theme_node)
                in_theme_edge = KGEdge(
                    source=industry_id,
                    target=theme_node.id,
                    edge_type=KGEdgeType.IN_THEME,
                )
                if not G.has_edge(industry_id, theme_node.id):
                    G.add_edge(industry_id, theme_node.id, edge_data=in_theme_edge)

        # -- Remove stale EXPOSES edges -----------------------------------------
        stale_industries = current_industry_ids - new_industry_ids
        for ind_id in stale_industries:
            if G.has_edge(fund_id, ind_id):
                G.remove_edge(fund_id, ind_id)

        # -- Update BELONGS_TO edges --------------------------------------------
        # Remove BELONGS_TO edges from stale stocks
        for stock_id in stale_stocks:
            for _, ind_dst, edge_data in list(G.out_edges(stock_id, data=True)):
                eg = edge_data.get("edge_data")
                if eg and eg.edge_type == KGEdgeType.BELONGS_TO:
                    G.remove_edge(stock_id, ind_dst)

        # Add BELONGS_TO for new / updated stocks
        stock_industries: dict[str, str] = {}
        for holding in new_holdings:
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

        # Stocks without explicit industry -> first sector
        for holding in new_holdings:
            stock_id = f"stock:{holding['stock_code']}"
            if holding["stock_code"] not in stock_industries:
                for sector_info in new_sectors:
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

    @staticmethod
    def _remove_orphan_nodes(G: nx.DiGraph) -> None:
        """Remove stock, industry, and theme nodes not connected to any fund.

        Event nodes and macro-factor nodes are **always preserved**.
        A node is "connected to a fund" if there is an incident edge (in or
        out) from a ``fund:*`` node.
        """
        preserve_prefixes = ("event:", "macro:")
        fund_ids = [n for n in G.nodes if n.startswith("fund:")]

        for node_id in list(G.nodes):
            if node_id.startswith(preserve_prefixes) or node_id.startswith("fund:"):
                continue

            # Check if any fund has a direct edge to this node
            has_fund_connection = any(
                G.has_edge(fund_id, node_id) or G.has_edge(node_id, fund_id)
                for fund_id in fund_ids
            )

            if not has_fund_connection:
                G.remove_node(node_id)

    @staticmethod
    def diff(old_graph: nx.DiGraph, new_graph: nx.DiGraph) -> GraphDiff:
        """Compute structural diff between two graphs.

        Compares node sets, edge sets, and node data equality.

        Args:
            old_graph: The original graph.
            new_graph: The modified/updated graph.

        Returns:
            A :class:`GraphDiff` describing all differences.
        """
        old_nodes: set[str] = set(old_graph.nodes)
        new_nodes: set[str] = set(new_graph.nodes)

        added_nodes: list[str] = sorted(new_nodes - old_nodes)
        removed_nodes: list[str] = sorted(old_nodes - new_nodes)

        # Modified nodes: present in both, but with different ``data``
        common_nodes = old_nodes & new_nodes
        modified_nodes: list[str] = []
        for node_id in common_nodes:
            old_data = old_graph.nodes[node_id].get("data")
            new_data = new_graph.nodes[node_id].get("data")
            if old_data != new_data:
                modified_nodes.append(node_id)
        modified_nodes.sort()

        old_edges: set[tuple] = set(old_graph.edges())
        new_edges: set[tuple] = set(new_graph.edges())

        added_edges: list[tuple] = sorted(new_edges - old_edges)
        removed_edges: list[tuple] = sorted(old_edges - new_edges)

        return GraphDiff(
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            modified_nodes=modified_nodes,
            added_edges=added_edges,
            removed_edges=removed_edges,
        )

    def save(self, graph: nx.DiGraph, path: str) -> None:
        """Serialize knowledge graph to disk using pickle.

        Stores graph topology, node/edge data, and metadata (version,
        fund codes, generation timestamp).

        Args:
            graph: NetworkX DiGraph to persist.
            path: Filesystem path for the pickle file.

        Raises:
            OSError: If the directory cannot be created or file cannot be written.
        """
        # Extract fund codes from graph nodes
        fund_codes = sorted(
            n.replace("fund:", "") for n in graph.nodes if n.startswith("fund:")
        )
        # Set / increment metadata
        graph.graph["version"] = graph.graph.get("version", 0) + 1
        graph.graph["funds_indexed"] = fund_codes
        graph.graph["generated_at"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()

        # Ensure parent directory exists
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(graph, f)

    @staticmethod
    def load(path: str) -> nx.DiGraph:
        """Load knowledge graph from disk.

        Validates the unpickled object is a valid ``nx.DiGraph``.

        Args:
            path: Filesystem path to a pickle file produced by :meth:`save`.

        Returns:
            The deserialized NetworkX DiGraph.

        Raises:
            FileNotFoundError: If the file does not exist.
            TypeError: If the loaded object is not an ``nx.DiGraph``.
            pickle.UnpicklingError: If the file is not valid pickle data.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(
                "Knowledge graph file not found: " + path
            )

        with open(path, "rb") as f:
            obj = pickle.load(f)

        if not isinstance(obj, nx.DiGraph):
            raise TypeError(
                "Expected nx.DiGraph, got " + type(obj).__name__ + ". "
                "The file " + path + " does not contain a valid knowledge graph."
            )

        return obj

    @staticmethod
    def cache_key(fund_codes: list[str]) -> str:
        """Generate a deterministic cache filename from sorted fund codes.

        Args:
            fund_codes: List of fund codes (e.g. ``["110011", "006123"]``).

        Returns:
            A stable filename like ``kg_cache_006123_110011.pkl``.
        """
        sorted_codes = sorted(fund_codes)
        codes_str = "_".join(sorted_codes)
        return "kg_cache_" + codes_str + ".pkl"

    @staticmethod
    def entity_chain(graph: nx.DiGraph, fund_code: str) -> dict:
        """Trace fund → stocks → industries → themes chain.

        Walks HOLDS edges from the fund to its stocks, then BELONGS_TO edges
        from each stock to its industry, then IN_THEME edges from each industry
        to its investment themes.

        Args:
            graph: Knowledge graph built by :meth:`build_from_holdings`.
            fund_code: Fund code (e.g. ``"110011"``).

        Returns:
            A nested dict with keys:
            - ``fund``: ``{code, name, fund_type}``
            - ``holdings``: list of ``{stock: {code, name}, industry: {name, code},
                themes: [{name}, ...]}``
            - ``exposure``: ``{industry_name: [theme_name, ...]}``
        """
        fund_id = f"fund:{fund_code}"
        result: dict[str, Any] = {"fund": {}, "holdings": [], "exposure": {}}

        if not graph.has_node(fund_id):
            return result

        fund_node = graph.nodes[fund_id].get("data")
        result["fund"] = {
            "code": fund_code,
            "name": fund_node.name if fund_node else "",
            "fund_type": fund_node.fund_type if fund_node else "",
        }

        exposure_map: dict[str, set[str]] = {}

        for _, stock_dst, data in graph.edges(fund_id, data=True):
            edge = data.get("edge_data")
            if not edge or edge.edge_type != KGEdgeType.HOLDS:
                continue

            stock_node = graph.nodes[stock_dst].get("data")
            holding_entry: dict[str, Any] = {
                "stock": {
                    "code": stock_dst.replace("stock:", ""),
                    "name": stock_node.name if stock_node else "",
                },
                "industry": {},
                "themes": [],
            }

            # Trace BELONGS_TO: stock → industry
            for _, ind_dst, ind_data in graph.edges(stock_dst, data=True):
                ind_edge = ind_data.get("edge_data")
                if not ind_edge or ind_edge.edge_type != KGEdgeType.BELONGS_TO:
                    continue

                ind_node = graph.nodes[ind_dst].get("data")
                ind_name = ind_node.name if ind_node else ind_dst.replace("industry:sw_", "")
                holding_entry["industry"] = {
                    "name": ind_name,
                    "code": ind_dst.replace("industry:", ""),
                }

                # Trace IN_THEME: industry → themes
                themes_list: list[dict[str, str]] = []
                for _, theme_dst, th_data in graph.edges(ind_dst, data=True):
                    th_edge = th_data.get("edge_data")
                    if not th_edge or th_edge.edge_type != KGEdgeType.IN_THEME:
                        continue
                    theme_node = graph.nodes[theme_dst].get("data")
                    theme_name = theme_node.name if theme_node else theme_dst.replace("theme:", "")
                    themes_list.append({"name": theme_name})

                holding_entry["themes"] = themes_list

                if ind_name not in exposure_map:
                    exposure_map[ind_name] = set()
                for t in themes_list:
                    exposure_map[ind_name].add(t["name"])

            result["holdings"].append(holding_entry)

        result["exposure"] = {
            ind: sorted(themes) for ind, themes in exposure_map.items()
        }
        return result

    @staticmethod
    def theme_diffusion(graph: nx.DiGraph, theme_name: str, max_depth: int = 2) -> dict:
        """Find all funds exposed to a theme through the industry chain.

        Traces: theme → industry nodes (depth 1) → stock nodes and fund nodes
        (depth 2) via reversed IN_THEME, BELONGS_TO, and HOLDS edges.

        Args:
            graph: Knowledge graph built by :meth:`build_from_holdings`.
            theme_name: Investment theme name (e.g. ``"\u767d\u9152"``).
            max_depth: Maximum traversal depth. ``1`` stops at industries;
                ``2`` includes stocks and funds.

        Returns:
            A dict with keys:
            - ``theme``: the queried theme name
            - ``industries``: ``[{industry_name, relevance_weight}, ...]``
            - ``stocks``: ``[{stock_code, stock_name, industry}, ...]`` (depth 2)
            - ``exposed_funds``: ``[{fund_code, fund_name, overlap_pct}, ...]``
              sorted by ``overlap_pct`` descending (depth 2).
        """
        theme_id = f"theme:{theme_name}"
        result: dict[str, Any] = {
            "theme": theme_name,
            "industries": [],
            "stocks": [],
            "exposed_funds": [],
        }

        if not graph.has_node(theme_id):
            return result

        # Depth 1: industries connected via reversed IN_THEME edges
        industry_names: list[str] = []
        for ind_src, _, data in graph.in_edges(theme_id, data=True):
            edge = data.get("edge_data")
            if edge and edge.edge_type == KGEdgeType.IN_THEME:
                ind_node = graph.nodes[ind_src].get("data")
                ind_name = ind_node.name if ind_node else ind_src.replace("industry:sw_", "")
                industry_names.append(ind_name)
                result["industries"].append({
                    "industry_name": ind_name,
                    "relevance_weight": 1.0,
                })

        if max_depth >= 2:
            industry_set = set(industry_names)
            seen_stocks: set[str] = set()
            fund_matching: dict[str, float] = {}
            fund_info_map: dict[str, dict[str, str]] = {}

            for ind_name in industry_set:
                ind_id = f"industry:sw_{ind_name}"
                if not graph.has_node(ind_id):
                    continue

                # Reverse BELONGS_TO: stocks in this industry
                for stock_src, _, s_data in graph.in_edges(ind_id, data=True):
                    s_edge = s_data.get("edge_data")
                    if not s_edge or s_edge.edge_type != KGEdgeType.BELONGS_TO:
                        continue

                    if stock_src not in seen_stocks:
                        seen_stocks.add(stock_src)
                        stock_node = graph.nodes[stock_src].get("data")
                        result["stocks"].append({
                            "stock_code": stock_src.replace("stock:", ""),
                            "stock_name": stock_node.name if stock_node else "",
                            "industry": ind_name,
                        })

                    # Reverse HOLDS: funds holding this stock
                    for fund_src, _, h_data in graph.in_edges(stock_src, data=True):
                        h_edge = h_data.get("edge_data")
                        if not h_edge or h_edge.edge_type != KGEdgeType.HOLDS:
                            continue
                        if fund_src not in fund_matching:
                            fund_node = graph.nodes[fund_src].get("data")
                            fund_info_map[fund_src] = {
                                "code": fund_src.replace("fund:", ""),
                                "name": fund_node.name if fund_node else "",
                            }
                            fund_matching[fund_src] = 0.0
                        fund_matching[fund_src] += h_edge.weight or 0

            # Compute total holding weights per fund for normalized overlap_pct
            fund_totals: dict[str, float] = {}
            for fund_src in fund_matching:
                total = 0.0
                for _, _, h_data in graph.edges(fund_src, data=True):
                    h_edge = h_data.get("edge_data")
                    if h_edge and h_edge.edge_type == KGEdgeType.HOLDS:
                        total += h_edge.weight or 0
                fund_totals[fund_src] = total

            for fund_src, match_w in fund_matching.items():
                total_w = fund_totals.get(fund_src, 0) or 1
                overlap_pct = (match_w / total_w) * 100.0
                result["exposed_funds"].append({
                    "fund_code": fund_info_map[fund_src]["code"],
                    "fund_name": fund_info_map[fund_src]["name"],
                    "overlap_pct": round(overlap_pct, 2),
                })

            result["exposed_funds"].sort(key=lambda x: x["overlap_pct"], reverse=True)

        return result

    @staticmethod
    def cross_fund_overlap(graph: nx.DiGraph, fund_codes: list[str]) -> dict:
        """Find stocks held by multiple funds in the list.

        For each fund, collects all stocks reachable via HOLDS edges, then
        identifies stocks held by two or more funds.

        Args:
            graph: Knowledge graph built by :meth:`build_from_holdings`.
            fund_codes: List of fund codes to compare (e.g. ``["110011", "006123"]``).

        Returns:
            A dict with keys:
            - ``shared_stocks``: ``[{stock_code, stock_name, held_by: [fund_code, ...],
                total_weight_pct}, ...]`` sorted by ``total_weight_pct`` descending.
            - ``overlap_matrix``: ``{fund_code: {other_fund_code: overlap_pct}}``
              where ``overlap_pct`` = percentage of fund_code\'s holdings shared
              with other_fund_code (asymmetric).
        """
        result: dict[str, Any] = {"shared_stocks": [], "overlap_matrix": {}}

        fund_holdings: dict[str, set[str]] = {}
        fund_weights: dict[str, dict[str, float]] = {}

        for fund_code in fund_codes:
            fund_id = f"fund:{fund_code}"
            stocks: set[str] = set()
            weights: dict[str, float] = {}

            if graph.has_node(fund_id):
                for _, stock_dst, data in graph.edges(fund_id, data=True):
                    edge = data.get("edge_data")
                    if edge and edge.edge_type == KGEdgeType.HOLDS:
                        stocks.add(stock_dst)
                        weights[stock_dst] = edge.weight or 0

            fund_holdings[fund_code] = stocks
            fund_weights[fund_code] = weights

        # Find stocks held by 2+ funds
        all_stocks: set[str] = set()
        for stocks in fund_holdings.values():
            all_stocks.update(stocks)

        shared: list[dict[str, Any]] = []
        for stock_id in all_stocks:
            held_by = [
                fc for fc in fund_codes
                if stock_id in fund_holdings.get(fc, set())
            ]
            if len(held_by) >= 2:
                total_weight = sum(
                    fund_weights.get(fc, {}).get(stock_id, 0) for fc in held_by
                )
                stock_node = graph.nodes[stock_id].get("data") if graph.has_node(stock_id) else None
                shared.append({
                    "stock_code": stock_id.replace("stock:", ""),
                    "stock_name": stock_node.name if stock_node else "",
                    "held_by": held_by,
                    "total_weight_pct": round(total_weight, 2),
                })

        shared.sort(key=lambda x: x["total_weight_pct"], reverse=True)
        result["shared_stocks"] = shared

        # Build asymmetric overlap matrix
        matrix: dict[str, dict[str, float]] = {}
        for fc1 in fund_codes:
            matrix[fc1] = {}
            set1 = fund_holdings.get(fc1, set())
            for fc2 in fund_codes:
                if fc1 == fc2:
                    matrix[fc1][fc2] = 100.0
                    continue
                set2 = fund_holdings.get(fc2, set())
                if not set1:
                    matrix[fc1][fc2] = 0.0
                else:
                    overlap = round((len(set1 & set2) / len(set1)) * 100.0, 2)
                    matrix[fc1][fc2] = overlap
        result["overlap_matrix"] = matrix

        return result


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

        # Traverse: industry -> theme
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

        # Timeliness (default 1.0 - computed externally)
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

        # Get themes through industry -> theme edges
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

        # Direct: event -> stock -> fund (via HOLDS reverse)
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

        # Indirect: event -> industry -> fund (via EXPOSES reverse)
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
