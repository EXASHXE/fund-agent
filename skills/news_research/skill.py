"""News Research Skill — holdings-driven news pipeline orchestration.

Uses ToolRegistry for tool access. No direct network calls.
All classification and scoring logic is rule-based.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.schemas import EvidenceItem


@dataclass
class NewsResearchInput:
    """Typed input for news research.

    Attributes:
        fund_codes: List of fund codes to research.
        kg_graph: NetworkX DiGraph from KnowledgeGraph (optional, for
            retrieving holdings per fund).
        date_range: Optional (start_date, end_date) ISO date strings.
    """
    fund_codes: list[str]
    kg_graph: Any  # nx.DiGraph, optional
    date_range: tuple[str, str] | None = None


@dataclass
class NewsResearchOutput:
    """Typed output from news research.

    Attributes:
        per_fund_news: Dict mapping fund_code -> list of classified news dicts.
        key_events: List of significant events extracted across all funds.
        coverage_report: Dict with coverage statistics (total, per source,
            date range, etc.).
    """
    per_fund_news: dict[str, list[dict]]
    key_events: list[dict]
    coverage_report: dict[str, Any]


# News classification categories
_NEWS_CATEGORIES = {
    "earnings": ["业绩", "财报", "营收", "净利润", "盈利", "亏损"],
    "regulation": ["监管", "政策", "法规", "合规", "处罚", "调查"],
    "industry_trend": ["行业", "趋势", "市场", "景气", "周期"],
    "product": ["产品", "研发", "创新", "上市", "发布", "推出"],
    "management": ["管理层", "高管", "人事", "任命", "离职"],
    "macro": ["宏观", "经济", "GDP", "CPI", "利率", "央行", "通胀"],
    "event": ["事件", "黑天鹅", "风险", "危机", "事故"],
}

_NEWS_SOURCE_WEIGHTS = {
    "finnhub": 0.9,
    "tavily": 0.7,
    "akshare": 0.8,
    "reuters": 0.9,
    "bloomberg": 0.9,
    "xinhua": 0.85,
    "default": 0.6,
}


class NewsResearchSkill:
    """Holdings-driven news research orchestration.

    Pipeline:
        1. For each fund, retrieve stock holdings from KG graph.
        2. Search for news via tool registry (search_news tool).
        3. Classify news items into categories.
        4. Score relevance based on holding exposure.
        5. Summarize key events.
        6. Generate coverage report.

    Expected tools:
        - "search_news": search_news(symbols, date_range) -> list[dict]
        - "kg.holdings": kg_holdings(fund_code, graph) -> list[str] of stock codes
    """

    def __init__(self, tool_registry: Any):
        self.tools = tool_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, input_data: NewsResearchInput) -> NewsResearchOutput:
        """Execute news research for the given fund codes.

        Pipeline:
            1. Resolve holdings per fund from KG graph or tool.
            2. Build search plan (symbols + date range).
            3. Retrieve news via tool registry.
            4. Classify, score, and summarize.
            5. Assemble coverage report.
        """
        fund_codes = input_data.fund_codes
        kg_graph = input_data.kg_graph
        date_range = input_data.date_range

        if not fund_codes:
            return NewsResearchOutput(
                per_fund_news={},
                key_events=[],
                coverage_report={
                    "total_news": 0,
                    "funds_covered": 0,
                    "sources": {},
                    "date_range": date_range or ("N/A", "N/A"),
                    "status": "empty_fund_list",
                },
            )

        # ---- Step 1: Resolve holdings per fund ---------------------------
        per_fund_symbols = self._resolve_holdings(fund_codes, kg_graph)

        # ---- Step 2 & 3: Search and retrieve news ------------------------
        all_news = self._search_news(per_fund_symbols, date_range)

        # ---- Step 4: Classify, score, and organize -----------------------
        per_fund_news: dict[str, list[dict]] = {}
        all_classified: list[dict] = []

        for fund_code, symbols in per_fund_symbols.items():
            fund_news = all_news.get(fund_code, [])
            classified = []
            for item in fund_news:
                classified_item = self._classify_news(item)
                classified_item["relevance_score"] = self._score_relevance(
                    item, symbols
                )
                classified.append(classified_item)
            # Sort by relevance descending, take top 20
            classified.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            per_fund_news[fund_code] = classified[:20]
            all_classified.extend(classified)

        # ---- Step 5: Extract key events ----------------------------------
        key_events = self._extract_key_events(all_classified)

        # ---- Step 6: Coverage report -------------------------------------
        coverage_report = self._build_coverage_report(
            per_fund_news=per_fund_news,
            all_classified=all_classified,
            date_range=date_range,
        )

        return NewsResearchOutput(
            per_fund_news=per_fund_news,
            key_events=key_events,
            coverage_report=coverage_report,
        )

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _resolve_holdings(
        self, fund_codes: list[str], kg_graph: Any
    ) -> dict[str, list[str]]:
        """Resolve stock holdings per fund using KG graph or tool."""
        per_fund: dict[str, list[str]] = {}

        for code in fund_codes:
            symbols: list[str] = []
            # Try tool first
            try:
                result = self.tools.invoke(
                    "kg.holdings", fund_code=code, graph=kg_graph
                )
                if isinstance(result, list):
                    symbols = result
            except (KeyError, TypeError, ValueError):
                pass

            # Fallback: traverse KG graph directly if provided
            if not symbols and kg_graph is not None:
                try:
                    fund_node = f"fund:{code}"
                    if kg_graph.has_node(fund_node):
                        for neighbor in kg_graph.successors(fund_node):
                            if isinstance(neighbor, str) and neighbor.startswith("stock:"):
                                symbols.append(neighbor.replace("stock:", ""))
                except Exception:
                    pass

            per_fund[code] = symbols if symbols else []

        return per_fund

    def _search_news(
        self,
        per_fund_symbols: dict[str, list[str]],
        date_range: tuple[str, str] | None,
    ) -> dict[str, list[dict]]:
        """Search news for each fund's holdings via tool registry."""
        all_news: dict[str, list[dict]] = {}

        for fund_code, symbols in per_fund_symbols.items():
            news_items: list[dict] = []
            if not symbols:
                all_news[fund_code] = []
                continue

            try:
                result = self.tools.invoke(
                    "search_news",
                    symbols=symbols,
                    date_range=date_range,
                )
                if isinstance(result, list):
                    news_items = result
                elif isinstance(result, dict):
                    # May return dict with per-symbol keys
                    for symbol_items in result.values():
                        if isinstance(symbol_items, list):
                            news_items.extend(symbol_items)
            except (KeyError, TypeError, ValueError):
                pass

            # Deduplicate by URL or title
            seen: set[str] = set()
            unique: list[dict] = []
            for item in news_items:
                key = item.get("url") or item.get("title", "")
                if key and key not in seen:
                    seen.add(key)
                    unique.append(item)
            all_news[fund_code] = unique

        return all_news

    # ------------------------------------------------------------------
    # Classification + scoring logic (pure rule-based)
    # ------------------------------------------------------------------

    def _classify_news(self, news_item: dict) -> dict:
        """Classify a news item into categories using keyword matching."""
        text = (
            f"{news_item.get('title', '')} "
            f"{news_item.get('description', '')} "
            f"{news_item.get('summary', '')}"
        ).lower()

        matched_categories: list[str] = []
        for category, keywords in _NEWS_CATEGORIES.items():
            if any(kw in text for kw in keywords):
                matched_categories.append(category)

        if not matched_categories:
            matched_categories.append("general")

        return {
            **news_item,
            "categories": matched_categories,
            "primary_category": matched_categories[0],
            "classified_at": datetime.now().isoformat(),
        }

    def _score_relevance(self, news_item: dict, holdings: list[str]) -> float:
        """Score news relevance based on holding symbol match and source weight.

        Returns a score in [0, 1]:
        - 0.5 base for any news with relevant holdings
        - +0.3 if title mentions a holding directly
        - +0.2 if description mentions a holding
        - Weighted by source reliability
        """
        text = (
            f"{news_item.get('title', '')} "
            f"{news_item.get('description', '')}"
        ).lower()

        score = 0.0
        matched_symbols = []

        for symbol in holdings:
            sym_lower = symbol.lower()
            if sym_lower in text:
                matched_symbols.append(symbol)

        if matched_symbols:
            score = 0.5  # base relevance
            title = news_item.get("title", "").lower()
            desc = news_item.get("description", "").lower()
            for sym in matched_symbols:
                if sym.lower() in title:
                    score += 0.3
                elif sym.lower() in desc:
                    score += 0.2

        # Source weight
        source = (news_item.get("source") or "default").lower()
        source_weight = _NEWS_SOURCE_WEIGHTS.get(source, _NEWS_SOURCE_WEIGHTS["default"])
        score *= source_weight

        return min(1.0, score)

    def _extract_key_events(self, all_classified: list[dict]) -> list[dict]:
        """Extract key significant events from all classified news.

        Events are determined by:
        - High relevance score (>0.6)
        - Negative or positive category signals
        - Unique event clusters
        """
        key_events = []

        for item in all_classified:
            relevance = item.get("relevance_score", 0)
            if relevance < 0.6:
                continue

            categories = item.get("categories", [])
            if "event" in categories or "regulation" in categories:
                key_events.append({
                    "event_id": str(uuid.uuid4()),
                    "title": item.get("title", ""),
                    "source": item.get("source", ""),
                    "date": item.get("date", item.get("published_at", "")),
                    "categories": categories,
                    "relevance_score": relevance,
                    "holding_symbols": item.get("related_symbols", []),
                    "description": item.get("description", ""),
                })

        # Deduplicate by title similarity (exact match for now)
        seen_titles: set[str] = set()
        unique_events: list[dict] = []
        for ev in key_events:
            title_key = ev["title"].strip().lower()[:80]
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_events.append(ev)

        return unique_events[:10]  # Top 10 key events

    def _build_coverage_report(
        self,
        per_fund_news: dict[str, list[dict]],
        all_classified: list[dict],
        date_range: tuple[str, str] | None,
    ) -> dict[str, Any]:
        """Build coverage report with statistics."""
        source_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        total = 0

        for item in all_classified:
            total += 1
            source = item.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

            for cat in item.get("categories", []):
                category_counts[cat] = category_counts.get(cat, 0) + 1

        funds_with_news = sum(
            1 for news_list in per_fund_news.values() if news_list
        )

        return {
            "total_news": total,
            "funds_covered": len(per_fund_news),
            "funds_with_news": funds_with_news,
            "sources": dict(sorted(source_counts.items(), key=lambda x: x[1], reverse=True)),
            "categories": dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True)),
            "date_range": date_range or ("N/A", "N/A"),
            "status": (
                "ok" if total > 0
                else "no_news_found"
            ),
        }
