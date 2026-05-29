"""Knowledge Graph — holdings context layer for AI-native research."""
from src.graph.schema import (
    KGNodeType, KGEdgeType,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
    KGEdge,
)
from src.graph.builder import KnowledgeGraphBuilder
from src.graph.industry_map import (
    INDUSTRY_THEME_MAP, THEME_KEYWORDS,
    get_themes_for_industry, get_keywords_for_theme,
    get_all_themes, get_all_industries,
)
from src.graph.enrichment import enrich_with_events
from src.graph.diff import GraphDiff
