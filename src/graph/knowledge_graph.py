"""KnowledgeGraph wrapper — cleaner interface around KnowledgeGraphBuilder.

Supports two input formats for multi-fund data:
    1. Single fund dict: ``{"code": "110011", "holdings": [...], "sectors": [...]}``
    2. Multi-fund mapping: ``{"110011": {...}, "006123": {...}}``

Handles holdings with either ``code/name`` or ``stock_code/stock_name`` keys.
"""
from __future__ import annotations

import networkx as nx
from src.graph.builder import KnowledgeGraphBuilder


class KnowledgeGraph:
    """Wrapper around KnowledgeGraphBuilder for cleaner interface."""

    def __init__(self, graph=None, builder=None):
        self._graph = graph
        self._builder = builder or KnowledgeGraphBuilder()

    @property
    def graph(self):
        return self._graph

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _normalize_holding(holding: dict) -> dict:
        """Map ``code→stock_code`` and ``name→stock_name`` if needed."""
        result = dict(holding)
        if "code" in result and "stock_code" not in result:
            result["stock_code"] = result.pop("code")
        if "name" in result and "stock_name" not in result:
            result["stock_name"] = result.pop("name")
        return result

    @classmethod
    def _normalize_fund_data(cls, fund_data: dict) -> list[dict]:
        """Convert any fund_data format into a list of single-fund dicts.

        Returns:
            List of dicts, each with ``code`` key and normalized holdings.
        """
        # Already a list?
        if isinstance(fund_data, list):
            normalized = []
            for item in fund_data:
                nd = dict(item)
                if "holdings" in nd:
                    nd["holdings"] = [cls._normalize_holding(h) for h in nd["holdings"]]
                normalized.append(nd)
            return normalized

        # Multi-fund mapping: {"110011": {...}, "006123": {...}}
        if hasattr(fund_data, "values"):
            vals = list(fund_data.values())
            if vals and all(isinstance(v, dict) for v in vals):
                return cls._normalize_fund_data(vals)

        # Single fund dict: {"code": "110011", "holdings": [...], ...}
        if isinstance(fund_data, dict) and "code" in fund_data:
            nd = dict(fund_data)
            if "holdings" in nd:
                nd["holdings"] = [cls._normalize_holding(h) for h in nd["holdings"]]
            return [nd]

        return []

    # --------------------------------------------------------------- lifecycle

    def build_from_holdings(self, fund_data: dict):
        """Build knowledge graph from fund holdings data.

        Accepts both single-fund dict and multi-fund mapping formats.
        """
        fund_dicts = self._normalize_fund_data(fund_data)

        if not fund_dicts:
            self._graph = nx.DiGraph()
            return self._graph

        # Build from the first fund
        self._graph = self._builder.build_from_holdings(fund_dicts[0])

        # Refresh with remaining funds if any
        if len(fund_dicts) > 1:
            self._graph = self._builder.refresh(self._graph, fund_dicts[1:])

        return self._graph

    def refresh(self, new_fund_data: dict):
        """Incrementally update graph with new fund data."""
        fund_dicts = self._normalize_fund_data(new_fund_data)

        if self._graph is None:
            if not fund_dicts:
                self._graph = nx.DiGraph()
                return self._graph
            self._graph = self._builder.build_from_holdings(fund_dicts[0])
            if len(fund_dicts) > 1:
                self._graph = self._builder.refresh(self._graph, fund_dicts[1:])
        else:
            self._graph = self._builder.refresh(self._graph, fund_dicts)

        return self._graph

    # --------------------------------------------------------------- serialize

    def save(self, path: str) -> None:
        if self._graph is not None:
            self._builder.save(self._graph, path)

    def load(self, path: str):
        self._graph = self._builder.load(path)
        return self._graph

    # ------------------------------------------------------------------- utils

    def cache_key(self, fund_codes: list[str]) -> str:
        return self._builder.cache_key(fund_codes)

    def diff(self, old_graph) -> dict:
        if self._graph is not None and old_graph is not None:
            d = self._builder.diff(old_graph, self._graph)
            return {
                "added_nodes": d.added_nodes,
                "removed_nodes": d.removed_nodes,
                "added_edges": d.added_edges,
                "removed_edges": d.removed_edges,
            }
        return {}
