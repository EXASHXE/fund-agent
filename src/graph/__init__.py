"""Knowledge Graph — holdings context layer for AI-native research.
Re-exports from src.kg for plan.txt architectural compliance (graph/ directory).
"""
from src.kg.schema import (
    KGNodeType, KGEdgeType,
    FundNode, StockNode, IndustryNode, ThemeNode, EventNode, MacroFactorNode,
    KGEdge,
)
from src.kg.graph import KnowledgeGraphBuilder
from src.kg.industry_map import (
    INDUSTRY_THEME_MAP, THEME_KEYWORDS,
    get_themes_for_industry, get_keywords_for_theme,
    get_all_themes, get_all_industries,
)
from src.kg.enrichment import enrich_with_events
from src.kg.diff import GraphDiff
