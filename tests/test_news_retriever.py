"""Tests for Phase 2 Retriever: holdings-driven news retrieval."""
import pytest
from unittest.mock import patch, MagicMock

import networkx as nx

from src.graph.builder import KnowledgeGraphBuilder
from src.graph.schema import (
    FundNode, StockNode, IndustryNode, ThemeNode,
    KGNodeType, KGEdgeType, KGEdge,
)


@pytest.fixture
def sample_kg():
    """Build a sample knowledge graph for testing retriever."""
    kg = KnowledgeGraphBuilder()
    fund_data = {
        "code": "110011",
        "name": "易方达中小盘混合",
        "fund_type": "hybrid",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
            {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            {"stock_code": "002371", "stock_name": "北方华创", "weight": 3.1},
            {"stock_code": "000001", "stock_name": "平安银行", "weight": 1.5},
        ],
        "sectors": [
            {"industry": "食品饮料", "weight": 30.5},
            {"industry": "电子", "weight": 15.2},
        ],
    }
    graph = kg.build_from_holdings(fund_data)
    return graph, kg


class TestRetrieverSearchPlan:
    """Test SearchPlan generation from KG."""

    def test_build_search_plan_extracts_holdings(self, sample_kg):
        graph, kg_builder = sample_kg
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        plan = retriever.build_search_plan("110011", graph)

        assert plan.fund_code == "110011"
        assert "600519" in plan.stocks
        assert "000858" in plan.stocks
        assert "002371" in plan.stocks

    def test_build_search_plan_includes_themes(self, sample_kg):
        graph, kg_builder = sample_kg
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        plan = retriever.build_search_plan("110011", graph)

        assert len(plan.themes) > 0
        # Food & Beverage → consumer themes
        theme_names = [t for t in plan.themes]
        assert any("消费" in t or "白酒" in t or "半导体" in t or "电子" in t for t in theme_names)

    def test_build_search_plan_includes_macro_queries(self, sample_kg):
        graph, kg_builder = sample_kg
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        plan = retriever.build_search_plan("110011", graph)

        assert len(plan.macro_queries) > 0  # Default macro queries

    def test_build_search_plan_unknown_fund(self, sample_kg):
        graph, kg_builder = sample_kg
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        plan = retriever.build_search_plan("999999", graph)

        assert plan.fund_code == "999999"
        assert plan.stocks == []
        assert plan.themes == []

    def test_build_search_plan_identifies_heavy_holdings(self, sample_kg):
        graph, kg_builder = sample_kg
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        plan = retriever.build_search_plan("110011", graph, heavy_threshold=5.0)

        assert "600519" in plan.heavy_holdings
        assert "000858" in plan.heavy_holdings
        assert "002371" not in plan.heavy_holdings  # 3.1% < 5%


class TestRetrieverNewsRetrieval:
    """Test news retrieval methods."""

    def test_retrieve_stock_news_uses_akshare(self):
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.iterrows.return_value = iter([
            (0, {"新闻标题": "茅台大涨", "新闻内容": "贵州茅台涨5%",
                 "发布时间": "2026-05-27 10:00:00", "文章来源": "财联社"}),
        ])

        with patch("legacy.news.news_fetcher._cached_ak_call", return_value=mock_df):
            news = retriever.retrieve_stock_news("600519")

        assert len(news) >= 1
        if len(news) > 0:
            item = news[0]
            assert "title" in item
            assert "content" in item

    def test_retrieve_market_news_uses_market_sources(self):
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.iterrows.return_value = iter([
            (0, {"新闻标题": "央行降息", "新闻内容": "LPR下调5BP",
                 "发布时间": "2026-05-27", "文章来源": "央行"}),
        ])

        with patch("legacy.news.news_fetcher._cached_ak_call", return_value=mock_df):
            news = retriever.retrieve_market_news(["央行利率", "LPR"])

        assert isinstance(news, list)

    def test_retriever_handles_akshare_errors(self):
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        with patch("legacy.news.news_fetcher._cached_ak_call", side_effect=Exception("API error")):
            news = retriever.retrieve_stock_news("600519")

        assert news == []


class TestRetrieverIntegration:
    """Integration test: SearchPlan → retrieval."""

    def test_search_plan_drives_retrieval(self, sample_kg):
        graph, kg_builder = sample_kg
        from legacy.news.retriever import Retriever
        from legacy.news.schemas import SearchPlan
        retriever = Retriever()

        plan = retriever.build_search_plan("110011", graph)
        assert plan.fund_code == "110011"
        assert len(plan.stocks) >= 2

        # Plan should be usable for retrieval
        # Verify heavy holdings (>=5% weight)
        assert "600519" in plan.heavy_holdings

    def test_retriever_with_search_plan(self, sample_kg):
        graph, kg_builder = sample_kg
        from legacy.news.retriever import Retriever
        retriever = Retriever()

        plan = retriever.build_search_plan("110011", graph)

        mock_df = MagicMock()
        mock_df.empty = True  # Empty result

        with patch("legacy.news.news_fetcher._cached_ak_call", return_value=mock_df):
            all_news = []
            for stock in plan.stocks:
                news = retriever.retrieve_stock_news(stock)
                all_news.extend(news)

        # Should not crash even with empty results
        assert isinstance(all_news, list)
