"""Knowledge Graph module: build, query, and enrich fund research graph."""
from src.kg.schema import (
    KGNodeType, KGEdgeType, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
)
from src.kg.industry_map import get_themes_for_industry, get_keywords_for_theme, get_all_themes, get_all_industries
from src.kg.graph import KnowledgeGraphBuilder
from src.kg.enrichment import enrich_with_events

__all__ = [
    "KnowledgeGraphBuilder",
    "KGNodeType", "KGEdgeType", "KGEdge",
    "FundNode", "StockNode", "IndustryNode", "ThemeNode", "EventNode", "MacroFactorNode",
    "get_themes_for_industry", "get_keywords_for_theme", "get_all_themes", "get_all_industries",
    "enrich_with_events",
]