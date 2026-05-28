"""Phase 2 News data models: SearchPlan, ClassifiedNews, ScoredNews, ResearchSummary, NewsLayer.

Also preserves EntityProfile and LLM_CONFIG for backward compatibility with Phase 1.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NewsLayer(str, Enum):
    """6-layer news classification hierarchy.

    Layer weights represent news relevance priority:
      FUND_DIRECT = 1.0  — Fund code/name matched directly
      HEAVY_HOLDING = 0.8 — Heavy holding stock (>=5% weight) mentioned
      INDUSTRY = 0.5 — Industry/sector news
      POLICY_MACRO = 0.3 — Policy or macro news
      OVERSEAS = 0.2 — Overseas market news
      BLACK_SWAN = variable — Black swan / risk events (magnitude-driven)
    """

    FUND_DIRECT = "fund_direct"
    HEAVY_HOLDING = "heavy_holding"
    INDUSTRY = "industry"
    POLICY_MACRO = "policy_macro"
    OVERSEAS = "overseas"
    BLACK_SWAN = "black_swan"


@dataclass
class SearchPlan:
    """Holdings-driven search plan extracted from KG for a single fund.

    Contains entities to query for targeted news retrieval.
    """

    fund_code: str = ""
    fund_name: str = ""
    stocks: list[str] = field(default_factory=list)       # Stock codes (weight >= 2%)
    stock_names: list[str] = field(default_factory=list)  # Stock names for text matching
    sectors: list[str] = field(default_factory=list)       # Industry/sector names
    themes: list[str] = field(default_factory=list)        # Investment themes
    events: list[str] = field(default_factory=list)        # Event type queries
    macro_queries: list[str] = field(default_factory=list) # Macro queries
    heavy_holdings: list[str] = field(default_factory=list) # Stocks with >=5% weight


@dataclass
class ClassifiedNews:
    """News item classified into a 6-layer hierarchy for a specific fund.

    Each news item may be classified for multiple funds independently.
    """

    title: str = ""
    content: str = ""
    date: str = ""
    source: str = ""
    url: str = ""

    # Classification
    layer: NewsLayer = NewsLayer.FUND_DIRECT
    weight: float = 0.0           # Layer weight (1.0, 0.8, 0.5, ...)
    fund_code: str = ""

    # Entity matching
    matched_entity: str = ""       # Which entity caused the match
    entity_type: str = ""          # Type: "stock", "industry", "theme"

    # Original data
    raw: dict[str, Any] | None = None


@dataclass
class ScoredNews:
    """News item with multi-factor relevance score and vector similarity.

    Extends ClassifiedNews with scoring fields for the pipeline.
    """

    title: str = ""
    content: str = ""
    date: str = ""
    source: str = ""
    url: str = ""

    # Classification (inherited from ClassifiedNews)
    layer: NewsLayer = NewsLayer.FUND_DIRECT
    weight: float = 0.0
    fund_code: str = ""

    # Multi-factor relevance sub-scores
    holding_overlap: float = 0.0    # KG: how many holdings mentioned
    top10_hit: bool = False         # Is a top-10 holding mentioned?
    industry_hit: bool = False      # KG: related industry?
    theme_hit: bool = False         # KG: related theme?
    timeliness: float = 1.0         # Exponential decay from publication date
    sentiment_severity: float = 0.5 # Polarity magnitude from sentiment

    # Combined scores
    relevance_score: float = 0.0    # Weighted multi-factor relevance
    vector_score: float = 0.0       # Cosine similarity score (from vector reranking)
    combined_score: float = 0.0     # relevance × 0.6 + cosine × 0.4


@dataclass
class ResearchSummary:
    """Research-style structured analysis of one news item for a fund.

    Produced by AI summarization (with rule-based fallback).
    Each field answers a specific question about the news impact.
    """

    fund_code: str = ""
    news_title: str = ""

    # Structured analysis fields
    what: str = ""                  # 什么发生了
    why_important: str = ""         # 为什么对这只基金重要
    fund_impact: str = ""           # 对基金净值/持仓的影响
    affected_holdings: list[str] = field(default_factory=list)  # 影响哪些重仓股
    time_horizon: str = "medium"    # short / medium / long
    risk_opportunity: str = "neutral"  # risk / opportunity / neutral
    suggested_action: str = ""      # 建议关注/操作

    # Metadata
    confidence: float = 0.5         # 0.0-1.0
    source: str = "llm"             # "llm" or "rule_based"


# ============================================================================
# Backward-compatible types preserved from Phase 1
# ============================================================================

@dataclass
class EntityProfile:
    """基金持仓实体画像 — preserved for backward compatibility with Phase 1."""
    fund_code: str = ""
    fund_name: str = ""
    stock_codes: list[str] = field(default_factory=list)
    stock_names: list[str] = field(default_factory=list)
    holdings: list[dict] = field(default_factory=list)
    sector_keywords: list[str] = field(default_factory=list)
    theme_keywords: list[str] = field(default_factory=list)
    updated_at: str | None = None


LLM_CONFIG: dict = {
    "api_url": os.environ.get(
        "FUND_NEWS_LLM_URL",
        "https://opencode.ai/zen/v1/chat/completions",
    ),
    "model": os.environ.get(
        "FUND_NEWS_LLM_MODEL",
        "deepseek-v4-flash-free",
    ),
    "api_key": os.environ.get(
        "FUND_NEWS_LLM_KEY",
        "",
    ),
    "max_tokens": 512,
    "temperature": 0.1,
    "timeout": 15,
}
