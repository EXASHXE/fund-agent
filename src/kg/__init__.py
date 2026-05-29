# DEPRECATED — use src.graph instead.
# This module is kept as a backward-compat re-export shim.
import warnings
warnings.warn(
    "src.kg is deprecated, use src.graph instead",
    DeprecationWarning,
    stacklevel=2,
)

from src.graph.schema import (
    KGNodeType, KGEdgeType, KGEdge,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
)
from src.graph.industry_map import get_themes_for_industry, get_keywords_for_theme, get_all_themes, get_all_industries
from src.graph.builder import KnowledgeGraphBuilder
from src.graph.enrichment import enrich_with_events
from src.graph.diff import GraphDiff

__all__ = [
    "KnowledgeGraphBuilder",
    "GraphDiff",
    "KGNodeType", "KGEdgeType", "KGEdge",
    "FundNode", "StockNode", "IndustryNode", "ThemeNode", "EventNode", "MacroFactorNode",
    "get_themes_for_industry", "get_keywords_for_theme", "get_all_themes", "get_all_industries",
    "enrich_with_events",
]
