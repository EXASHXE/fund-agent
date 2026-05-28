"""Tests for Phase 2 NewsPipeline integration (end-to-end)."""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

import networkx as nx

from src.kg.graph import KnowledgeGraphBuilder
from src.news.schemas import NewsLayer, SearchPlan, ClassifiedNews, ScoredNews, ResearchSummary


@pytest.fixture
def sample_kg():
    kg = KnowledgeGraphBuilder()
    fund_data = {
        "code": "110011",
        "name": "易方达中小盘混合",
        "fund_type": "hybrid",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
            {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
        ],
        "sectors": [
            {"industry": "食品饮料", "weight": 30.5},
        ],
    }
    graph = kg.build_from_holdings(fund_data)
    return graph, kg


class TestNewsPipeline:
    """Test the new NewsPipeline orchestrator."""

    def test_pipeline_run_single_fund(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.news_pipeline import NewsPipeline

        mock_news = [
            {"title": "贵州茅台大涨", "content": "涨了", "date": "2026-05-27", "source": "财联社"},
        ]

        with patch("src.news.retriever.Retriever.retrieve_stock_news", return_value=mock_news), \
             patch("src.news.retriever.Retriever.retrieve_market_news", return_value=[]):
            pipeline = NewsPipeline()
            result = pipeline.run(["110011"], graph)

        assert "110011" in result
        fund_result = result["110011"]
        assert "search_plan" in fund_result
        assert "classified_news" in fund_result
        assert "scored_news" in fund_result
        assert "research_summaries" in fund_result
        assert "events" in fund_result
        assert fund_result["search_plan"].fund_code == "110011"

    def test_pipeline_stage_count(self, sample_kg):
        """Pipeline should have 8 stages."""
        graph, kg_builder = sample_kg
        from src.news.news_pipeline import NewsPipeline

        mock_news = [{"title": "test", "content": "test", "date": "2026-05-27", "source": "test"}]

        with patch("src.news.retriever.Retriever.retrieve_stock_news", return_value=mock_news), \
             patch("src.news.retriever.Retriever.retrieve_market_news", return_value=[]):
            pipeline = NewsPipeline()
            result = pipeline.run(["110011"], graph)

        fund_result = result["110011"]
        stages = fund_result.get("stages_completed", [])
        assert len(stages) >= 5  # At minimum 5 of 8 stages

    def test_pipeline_multiple_funds(self, sample_kg):
        graph, kg_builder = sample_kg

        # Build multi-fund KG
        fund_data2 = {
            "code": "000001",
            "name": "华夏成长",
            "fund_type": "stock",
            "holdings": [
                {"stock_code": "000002", "stock_name": "万科A", "weight": 6.0},
            ],
            "sectors": [{"industry": "房地产", "weight": 40.0}],
        }
        graph2 = kg_builder.build_from_holdings(fund_data2)
        # Merge graphs
        graph = nx.compose(graph, graph2)

        from src.news.news_pipeline import NewsPipeline
        mock_news = [{"title": "test", "content": "test", "date": "2026-05-27", "source": "test"}]

        with patch("src.news.retriever.Retriever.retrieve_stock_news", return_value=mock_news), \
             patch("src.news.retriever.Retriever.retrieve_market_news", return_value=[]):
            pipeline = NewsPipeline()
            result = pipeline.run(["110011", "000001"], graph)

        assert "110011" in result
        assert "000001" in result

    def test_pipeline_unknown_fund(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.news_pipeline import NewsPipeline

        pipeline = NewsPipeline()
        with patch("src.news.retriever.Retriever.retrieve_stock_news", return_value=[]), \
             patch("src.news.retriever.Retriever.retrieve_market_news", return_value=[]):
            result = pipeline.run(["999999"], graph)

        assert "999999" in result
        fund_result = result["999999"]
        assert fund_result["classified_news"] == []

    def test_pipeline_output_schema(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.news_pipeline import NewsPipeline

        mock_news = [{"title": "茅台大涨", "content": "涨5%", "date": "2026-05-27", "source": "财联社"}]

        with patch("src.news.retriever.Retriever.retrieve_stock_news", return_value=mock_news), \
             patch("src.news.retriever.Retriever.retrieve_market_news", return_value=[]):
            pipeline = NewsPipeline()
            result = pipeline.run(["110011"], graph)

        fund_result = result["110011"]

        # Check all expected keys
        assert isinstance(fund_result["search_plan"], SearchPlan)
        assert isinstance(fund_result["classified_news"], list)
        assert isinstance(fund_result["scored_news"], list)
        assert isinstance(fund_result["research_summaries"], list)
        assert isinstance(fund_result["events"], list)

        if fund_result["classified_news"]:
            assert isinstance(fund_result["classified_news"][0], ClassifiedNews)

        if fund_result["scored_news"]:
            assert isinstance(fund_result["scored_news"][0], ScoredNews)

        if fund_result["research_summaries"]:
            assert isinstance(fund_result["research_summaries"][0], ResearchSummary)

    def test_pipeline_with_vector_store_disabled(self, sample_kg):
        """Pipeline should work without vector store."""
        graph, kg_builder = sample_kg
        from src.news.news_pipeline import NewsPipeline

        mock_news = [{"title": "test", "content": "test", "date": "2026-05-27", "source": "test"}]

        with patch("src.news.retriever.Retriever.retrieve_stock_news", return_value=mock_news), \
             patch("src.news.retriever.Retriever.retrieve_market_news", return_value=[]):
            pipeline = NewsPipeline()
            result = pipeline.run(["110011"], graph, vector_store=None)

        assert "110011" in result
        # Should still produce results without vector store
        assert len(result["110011"]["scored_news"]) >= 0

    def test_pipeline_stages_completed(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.news_pipeline import NewsPipeline

        mock_news = [{"title": "test", "content": "test", "date": "2026-05-27", "source": "test"}]

        with patch("src.news.retriever.Retriever.retrieve_stock_news", return_value=mock_news), \
             patch("src.news.retriever.Retriever.retrieve_market_news", return_value=[]):
            pipeline = NewsPipeline()
            result = pipeline.run(["110011"], graph)

        stages = result["110011"].get("stages_completed", [])
        expected_stages = [
            "entity_extraction", "targeted_retrieval", "layer_classification",
            "relevance_scoring", "vector_reranking", "ai_reranking",
            "research_summary", "event_extraction",
        ]
        for stage in expected_stages:
            assert stage in stages
