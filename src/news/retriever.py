"""Phase 2 Retriever: Holdings-driven news retrieval.
 
Uses KG to generate SearchPlan, then fetches news via existing AKShare functions.
"""
from __future__ import annotations

from datetime import date, timedelta

import networkx as nx

from src.news.schemas import SearchPlan, NewsLayer
from src.kg.schema import KGEdgeType
from src.kg.industry_map import get_keywords_for_theme

# Default macro queries for all funds
_DEFAULT_MACRO_QUERIES = [
    "央行利率", "LPR", "美联储", "FOMC",
    "GDP", "CPI", "PMI", "政策",
]


class Retriever:
    """Holdings-driven news retrieval engine.

    Replaces keyword-based search with KG-driven targeted retrieval.
    Uses existing AKShare news_fetcher functions as data source.
    """

    def build_search_plan(
        self,
        fund_code: str,
        graph: nx.DiGraph,
        heavy_threshold: float = 5.0,
    ) -> SearchPlan:
        """Build a targeted search plan from KG for a fund.

        Extracts: stocks, sectors, themes, macro queries from KG.
        Only includes stocks with weight >= 2% for retrieval budget.

        Args:
            fund_code: Fund code (e.g. "110011").
            graph: NetworkX DiGraph from KnowledgeGraphBuilder.
            heavy_threshold: Weight percentage threshold for heavy holdings.

        Returns:
            SearchPlan with stocks, sectors, themes, and macro queries.
        """
        fund_id = f"fund:{fund_code}"

        plan = SearchPlan(fund_code=fund_code)

        if not graph.has_node(fund_id):
            return plan

        plan.macro_queries = list(_DEFAULT_MACRO_QUERIES)

        # Extract fund name from KG
        fund_data = graph.nodes[fund_id].get("data")
        if fund_data:
            plan.fund_name = getattr(fund_data, "name", "")

        # Extract holdings and sector edges from KG
        stocks_with_weights = []
        stock_names = []
        sectors = set()
        seen_themes = set()

        for _, dst, edge_data in graph.edges(fund_id, data=True):
            edge = edge_data.get("edge_data")
            if not edge:
                continue

            if edge.edge_type == KGEdgeType.HOLDS:
                stock_code = dst.replace("stock:", "")
                weight = edge.weight or 0
                stocks_with_weights.append((stock_code, weight))
                # Extract stock name from KG node
                stock_node = graph.nodes[dst].get("data")
                if stock_node:
                    name = getattr(stock_node, "name", "")
                    if name and name not in stock_names:
                        stock_names.append(name)

            elif edge.edge_type == KGEdgeType.EXPOSES:
                sector_name = dst.replace("industry:sw_", "")
                sectors.add(sector_name)

                # Traverse industry → theme
                for _, theme_dst, _ in graph.edges(dst, data=True):
                    theme_name = theme_dst.replace("theme:", "")
                    if theme_name not in seen_themes:
                        seen_themes.add(theme_name)
                        plan.themes.append(theme_name)

        # Filter stocks: weight >= 2% for search budget
        plan.stocks = [code for code, w in stocks_with_weights if w >= 2.0]
        plan.stock_names = stock_names
        # Heavy holdings: weight >= threshold%
        plan.heavy_holdings = [code for code, w in stocks_with_weights if w >= heavy_threshold]
        plan.sectors = list(sectors)

        # Add theme keywords as additional search terms
        for theme in seen_themes:
            keywords = get_keywords_for_theme(theme)
            plan.macro_queries.extend(kw for kw in keywords if kw not in plan.macro_queries)

        return plan

    def retrieve_stock_news(
        self,
        stock_code: str,
        days: int = 30,
    ) -> list[dict]:
        """Retrieve news for a specific stock via AKShare.

        Args:
            stock_code: Stock code (e.g. "600519").
            days: Lookback days.

        Returns:
            List of raw news dicts with title, content, date, source.
        """
        from src.news.shared_fetch import cached_ak_call

        try:
            df = cached_ak_call("stock_news_em", symbol=stock_code)
        except Exception:
            return []

        if df is None or getattr(df, "empty", True):
            return []

        news_items = []
        cutoff = date.today() - timedelta(days=days)

        for _, row in df.iterrows():
            title = self._pick_row_field(row, ["新闻标题", "标题", "title"])
            content = self._pick_row_field(row, ["新闻内容", "内容", "content"])
            date_str = self._pick_row_field(row, ["发布时间", "时间", "date"])
            source = self._pick_row_field(row, ["文章来源", "来源", "source"])

            if not title and not content:
                continue

            # Parse date
            try:
                from datetime import datetime
                for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"]:
                    try:
                        raw_date = str(date_str).strip()[:len(fmt)]
                        news_date = datetime.strptime(raw_date, fmt).date()
                        if news_date < cutoff:
                            continue
                        date_str = news_date.isoformat()
                        break
                    except (ValueError, IndexError):
                        continue
            except Exception:
                pass

            news_items.append({
                "title": title or content[:80],
                "content": (content or "")[:500],
                "date": date_str,
                "source": source or "AKShare",
                "stock_code": stock_code,
            })

        return news_items

    def retrieve_market_news(
        self,
        queries: list[str],
        days: int = 30,
    ) -> list[dict]:
        """Retrieve market-wide news for macro/sector queries.

        Uses AKShare market news endpoints with keyword filtering.

        Args:
            queries: List of search queries/keywords.
            days: Lookback days.

        Returns:
            List of raw news dicts.
        """
        from src.news.shared_fetch import cached_ak_call, fetch_sina_roll_news_df

        news_items = []
        seen_titles = set()

        # Try CLS (财联社) telegraph
        try:
            df = cached_ak_call("stock_telegraph_cls")
            news_items.extend(self._extract_from_df(df, queries, days, seen_titles, "财联社"))
        except Exception:
            pass

        # Try Sina roll news
        try:
            df = fetch_sina_roll_news_df(pages=3)
            news_items.extend(self._extract_from_df(df, queries, days, seen_titles, "新浪财经"))
        except Exception:
            pass

        # Try CLS category
        for symbol in ["全部", "重点"]:
            try:
                df = cached_ak_call("stock_info_global_cls", symbol=symbol)
                news_items.extend(self._extract_from_df(df, queries, days, seen_titles, f"财联社:{symbol}"))
            except Exception:
                pass

        return news_items

    def _extract_from_df(
        self,
        df,
        queries: list[str],
        days: int,
        seen_titles: set,
        default_source: str,
    ) -> list[dict]:
        """Extract news items from a DataFrame matching queries."""
        if df is None or getattr(df, "empty", True):
            return []

        from datetime import datetime

        cutoff = date.today() - timedelta(days=days)
        items = []

        for _, row in df.iterrows():
            title = self._pick_row_field(row, ["新闻标题", "标题", "title", "内容标题"])
            content = self._pick_row_field(row, ["新闻内容", "内容", "summary", "摘要"])
            source = self._pick_row_field(row, ["文章来源", "来源", "source"]) or default_source

            text = f"{title} {content}"

            # Keyword matching
            matched = any(q in text for q in queries) if queries else True
            if not matched:
                continue

            # Dedup by title
            if title in seen_titles:
                continue
            seen_titles.add(title)

            # Parse date
            date_raw = self._pick_row_field(row, ["发布时间", "时间", "date", "datetime"])
            date_str = ""
            if date_raw:
                try:
                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y%m%d"]:
                        try:
                            raw = str(date_raw).strip()[:len(fmt)]
                            news_date = datetime.strptime(raw, fmt).date()
                            if news_date < cutoff:
                                continue
                            date_str = news_date.isoformat()
                            break
                        except (ValueError, IndexError):
                            continue
                except Exception:
                    pass

            items.append({
                "title": title or content[:80],
                "content": (content or "")[:500],
                "date": date_str,
                "source": source,
            })

        return items

    @staticmethod
    def _pick_row_field(row, names: list[str]) -> str:
        """Pick first non-empty field from row by multiple possible names."""
        for name in names:
            val = row.get(name) if hasattr(row, "get") else getattr(row, name, None)
            if val is not None:
                s = str(val).strip()
                if s and s.lower() != "nan":
                    return s
        return ""
