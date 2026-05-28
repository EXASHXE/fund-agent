"""Tests for Phase 2 Scorer: multi-factor relevance scoring + vector reranking."""
import pytest
import networkx as nx
import math

from src.kg.graph import KnowledgeGraphBuilder
from src.kg.schema import KGEdgeType
from src.news.schemas import NewsLayer, ScoredNews, ClassifiedNews
from src.vectorstore.search import cosine_similarity


@pytest.fixture
def sample_kg():
    """Build a sample KG for scoring tests."""
    kg = KnowledgeGraphBuilder()
    fund_data = {
        "code": "110011",
        "name": "易方达中小盘混合",
        "fund_type": "hybrid",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "weight": 9.5},
            {"stock_code": "000858", "stock_name": "五粮液", "weight": 7.2},
            {"stock_code": "002371", "stock_name": "北方华创", "weight": 3.1},
        ],
        "sectors": [
            {"industry": "食品饮料", "weight": 30.5},
            {"industry": "电子", "weight": 15.2},
        ],
    }
    graph = kg.build_from_holdings(fund_data)
    return graph, kg


def make_classified(title="test", layer=NewsLayer.HEAVY_HOLDING, weight=0.8,
                    fund_code="110011", matched_entity="600519", entity_type="stock",
                    date="2026-05-27"):
    """Helper to create a ClassifiedNews instance."""
    return ClassifiedNews(
        title=title,
        content="test content",
        date=date,
        source="test",
        layer=layer,
        weight=weight,
        fund_code=fund_code,
        matched_entity=matched_entity,
        entity_type=entity_type,
    )


class TestScorerRelevance:
    """Test multi-factor relevance scoring."""

    def test_score_relevance_holding_overlap(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        classified = [make_classified(title="贵州茅台大涨", matched_entity="600519")]
        result = scorer.score_relevance(classified, "110011", graph)

        assert len(result) == 1
        assert result[0].holding_overlap > 0
        assert result[0].top10_hit is True

    def test_score_relevance_industry_hit(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        classified = [make_classified(title="食品饮料景气", matched_entity="食品饮料",
                                       entity_type="industry", layer=NewsLayer.INDUSTRY)]
        result = scorer.score_relevance(classified, "110011", graph)

        assert len(result) == 1
        assert result[0].industry_hit is True

    def test_score_relevance_theme_hit(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        classified = [make_classified(title="芯片行业突破", matched_entity="电子",
                                       entity_type="industry", layer=NewsLayer.INDUSTRY)]
        result = scorer.score_relevance(classified, "110011", graph)

        assert len(result) == 1
        # 电子 industry maps to 半导体 theme → theme_hit should be True
        assert result[0].theme_hit is True

    def test_score_relevance_calculates_combined(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        classified = [make_classified(title="贵州茅台年报")]
        result = scorer.score_relevance(classified, "110011", graph)

        assert len(result) == 1
        assert 0 <= result[0].relevance_score <= 1.0

    def test_score_relevance_unknown_fund(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        classified = [make_classified(fund_code="999999")]
        result = scorer.score_relevance(classified, "999999", graph)

        assert len(result) == 1
        # No holding overlap for unknown fund
        assert result[0].holding_overlap == 0

    def test_score_relevance_timeliness_decay(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        # Recent news
        classified_recent = [make_classified(title="茅台", date="2026-05-27")]
        result_recent = scorer.score_relevance(classified_recent, "110011", graph)

        # Old news (30 days ago)
        classified_old = [make_classified(title="茅台", date="2026-04-27")]
        result_old = scorer.score_relevance(classified_old, "110011", graph)

        assert result_recent[0].timeliness >= result_old[0].timeliness

    def test_score_relevance_multiple_items(self, sample_kg):
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        classified = [
            make_classified(title="贵州茅台大涨", matched_entity="600519"),
            make_classified(title="央行降息", layer=NewsLayer.POLICY_MACRO,
                          matched_entity="macro", entity_type="macro"),
        ]
        result = scorer.score_relevance(classified, "110011", graph)

        assert len(result) == 2
        # Holding-related news should score higher than policy
        assert result[0].relevance_score > result[1].relevance_score


class TestScorerVectorReranking:
    """Test vector-based reranking."""

    def test_rerank_without_embedding_pipeline_uses_default(self, sample_kg):
        """When no embedding pipeline, scores should remain unchanged."""
        graph, kg_builder = sample_kg
        from src.news.scorer import Scorer
        scorer = Scorer()

        classified = [make_classified(title="贵州茅台年报")]
        scored = scorer.score_relevance(classified, "110011", graph)

        reranked = scorer.rerank_with_vectors(scored, "110011", embedding_pipeline=None)

        assert len(reranked) == len(scored)
        for r in reranked:
            assert r.vector_score == 0.5  # Default when no pipeline

    def test_rerank_combined_score_formula(self, sample_kg):
        """Combined score = relevance * 0.6 + cosine * 0.4."""
        from src.news.scorer import Scorer

        scored = [
            ScoredNews(
                title="test", layer=NewsLayer.HEAVY_HOLDING,
                weight=0.8, fund_code="110011",
                relevance_score=1.0, vector_score=0.0,
            ),
            ScoredNews(
                title="test2", layer=NewsLayer.HEAVY_HOLDING,
                weight=0.8, fund_code="110011",
                relevance_score=0.0, vector_score=1.0,
            ),
        ]

        scorer = Scorer()
        result = scorer.rerank_with_vectors(scored, "110011", embedding_pipeline=None)

        # First: 1.0 * 0.6 + 0.5 * 0.4 = 0.8
        assert abs(result[0].combined_score - 0.8) < 0.01
        # Second: 0.0 * 0.6 + 0.5 * 0.4 = 0.2
        assert abs(result[1].combined_score - 0.2) < 0.01

    def test_rerank_sorts_by_combined_score(self, sample_kg):
        from src.news.scorer import Scorer
        scorer = Scorer()

        scored = [
            ScoredNews(title="low", layer=NewsLayer.HEAVY_HOLDING, weight=0.8,
                      fund_code="110011", relevance_score=0.3),
            ScoredNews(title="high", layer=NewsLayer.HEAVY_HOLDING, weight=0.8,
                      fund_code="110011", relevance_score=0.9),
            ScoredNews(title="mid", layer=NewsLayer.HEAVY_HOLDING, weight=0.8,
                      fund_code="110011", relevance_score=0.5),
        ]

        reranked = scorer.rerank_with_vectors(scored, "110011", embedding_pipeline=None)

        assert reranked[0].title == "high"
        assert reranked[-1].title == "low"

    def test_rerank_top_k(self, sample_kg):
        from src.news.scorer import Scorer
        scorer = Scorer()

        scored = [
            ScoredNews(title=f"item_{i}", layer=NewsLayer.HEAVY_HOLDING,
                      weight=0.8, fund_code="110011",
                      relevance_score=0.1 * (i + 1))
            for i in range(30)
        ]

        reranked = scorer.rerank_with_vectors(scored, "110011",
                                                embedding_pipeline=None, top_k=20)

        assert len(reranked) == 20
