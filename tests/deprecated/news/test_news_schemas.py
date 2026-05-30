"""Tests for Phase 2 news data models."""
import pytest
from dataclasses import asdict


class TestNewsLayer:
    """Test NewsLayer enum with 6 layers."""

    def test_news_layer_has_six_layers(self):
        from legacy.news.schemas import NewsLayer
        assert len(NewsLayer) == 6
        assert NewsLayer.FUND_DIRECT.value == "fund_direct"
        assert NewsLayer.HEAVY_HOLDING.value == "heavy_holding"
        assert NewsLayer.INDUSTRY.value == "industry"
        assert NewsLayer.POLICY_MACRO.value == "policy_macro"
        assert NewsLayer.OVERSEAS.value == "overseas"
        assert NewsLayer.BLACK_SWAN.value == "black_swan"

    def test_news_layer_is_hashable(self):
        from legacy.news.schemas import NewsLayer
        d = {NewsLayer.FUND_DIRECT: "direct", NewsLayer.HEAVY_HOLDING: "holding"}
        assert d[NewsLayer.FUND_DIRECT] == "direct"


class TestSearchPlan:
    """Test SearchPlan dataclass."""

    def test_search_plan_creation(self):
        from legacy.news.schemas import SearchPlan
        plan = SearchPlan(
            fund_code="110011",
            fund_name="易方达中小盘",
            stocks=["600519", "000858"],
            sectors=["食品饮料"],
            themes=["消费", "白酒"],
            events=[],
            macro_queries=["央行利率"],
        )
        assert plan.fund_code == "110011"
        assert plan.fund_name == "易方达中小盘"
        assert len(plan.stocks) == 2
        assert "消费" in plan.themes

    def test_search_plan_defaults(self):
        from legacy.news.schemas import SearchPlan
        plan = SearchPlan()
        assert plan.fund_code == ""
        assert plan.stocks == []
        assert plan.sectors == []
        assert plan.themes == []
        assert plan.events == []
        assert plan.macro_queries == []

    def test_search_plan_to_dict(self):
        from legacy.news.schemas import SearchPlan
        plan = SearchPlan(fund_code="001", stocks=["002", "003"], themes=["AI"])
        d = asdict(plan)
        assert d["fund_code"] == "001"
        assert d["stocks"] == ["002", "003"]


class TestClassifiedNews:
    """Test ClassifiedNews dataclass."""

    def test_classified_news_creation(self):
        from legacy.news.schemas import ClassifiedNews, NewsLayer
        news = ClassifiedNews(
            title="茅台大涨",
            content="贵州茅台今日上涨5%",
            layer=NewsLayer.HEAVY_HOLDING,
            weight=0.8,
            fund_code="110011",
            source="财联社",
            date="2026-05-27",
        )
        assert news.layer == NewsLayer.HEAVY_HOLDING
        assert news.weight == 0.8
        assert news.fund_code == "110011"

    def test_classified_news_defaults(self):
        from legacy.news.schemas import ClassifiedNews, NewsLayer
        news = ClassifiedNews()
        assert news.layer == NewsLayer.FUND_DIRECT
        assert news.weight == 0.0
        assert news.fund_code == ""
        assert news.title == ""
        assert news.matched_entity == ""

    def test_classified_news_extra_fields(self):
        from legacy.news.schemas import ClassifiedNews, NewsLayer
        news = ClassifiedNews(
            title="test",
            layer=NewsLayer.FUND_DIRECT,
            weight=1.0,
            fund_code="001",
            date="2026-05-27",
            matched_entity="600519",
            entity_type="stock",
            url="http://example.com",
            source="财联社",
            raw={"key": "val"},
        )
        assert news.matched_entity == "600519"
        assert news.entity_type == "stock"
        assert news.url == "http://example.com"
        assert news.raw == {"key": "val"}


class TestScoredNews:
    """Test ScoredNews dataclass."""

    def test_scored_news_creation(self):
        from legacy.news.schemas import ScoredNews, NewsLayer
        news = ScoredNews(
            title="茅台大涨",
            content="贵州茅台今日上涨5%",
            layer=NewsLayer.HEAVY_HOLDING,
            weight=0.8,
            fund_code="110011",
            relevance_score=0.75,
            vector_score=0.65,
            combined_score=0.71,
        )
        assert news.relevance_score == 0.75
        assert news.vector_score == 0.65
        assert abs(news.combined_score - 0.71) < 0.01

    def test_scored_news_defaults(self):
        from legacy.news.schemas import ScoredNews
        news = ScoredNews()
        assert news.relevance_score == 0.0
        assert news.vector_score == 0.0
        assert news.combined_score == 0.0
        assert news.timeliness == 1.0
        assert news.sentiment_severity == 0.5

    def test_scored_news_scoring_factors(self):
        from legacy.news.schemas import ScoredNews, NewsLayer
        news = ScoredNews(
            title="test",
            layer=NewsLayer.INDUSTRY,
            weight=0.5,
            fund_code="001",
            holding_overlap=0.8,
            top10_hit=True,
            industry_hit=True,
            theme_hit=False,
            timeliness=0.9,
            sentiment_severity=0.7,
        )
        assert news.holding_overlap == 0.8
        assert news.top10_hit is True
        assert news.industry_hit is True
        assert news.theme_hit is False


class TestResearchSummary:
    """Test ResearchSummary dataclass."""

    def test_research_summary_creation(self):
        from legacy.news.schemas import ResearchSummary
        summary = ResearchSummary(
            fund_code="110011",
            news_title="茅台大涨5%",
            what="贵州茅台今日上涨5%，成交额创年内新高",
            why_important="茅台是基金第一重仓，权重9.5%",
            fund_impact="直接正向拉动净值约0.5%",
            affected_holdings=["600519"],
            time_horizon="short",
            risk_opportunity="opportunity",
            suggested_action="持有观察，关注后续量能",
        )
        assert summary.fund_code == "110011"
        assert summary.what is not None
        assert summary.why_important is not None
        assert summary.affected_holdings == ["600519"]
        assert summary.time_horizon == "short"
        assert summary.risk_opportunity == "opportunity"

    def test_research_summary_defaults(self):
        from legacy.news.schemas import ResearchSummary
        summary = ResearchSummary()
        assert summary.fund_code == ""
        assert summary.what == ""
        assert summary.why_important == ""
        assert summary.affected_holdings == []
        assert summary.time_horizon == "medium"
        assert summary.risk_opportunity == "neutral"

    def test_research_summary_rule_based(self):
        from legacy.news.schemas import ResearchSummary
        summary = ResearchSummary(
            fund_code="001",
            news_title="测试",
            what="突发事件",
            why_important="影响持仓",
            fund_impact="偏负面",
            affected_holdings=["002"],
            risk_opportunity="risk",
            suggested_action="减仓观察",
            source="rule_based",
        )
        assert summary.source == "rule_based"
        assert summary.risk_opportunity == "risk"


class TestNewsSchemasIntegration:
    """Test integration between schema types."""

    def test_classified_to_scored_conversion_support(self):
        from legacy.news.schemas import ClassifiedNews, ScoredNews, NewsLayer
        classified = ClassifiedNews(
            title="test",
            layer=NewsLayer.INDUSTRY,
            weight=0.5,
            fund_code="001",
            content="test content",
            date="2026-05-27",
            matched_entity="白酒",
            entity_type="industry",
        )
        scored = ScoredNews(
            title=classified.title,
            content=classified.content,
            layer=classified.layer,
            weight=classified.weight,
            fund_code=classified.fund_code,
            date=classified.date,
            relevance_score=0.6,
        )
        assert scored.layer == classified.layer
        assert scored.fund_code == classified.fund_code

    def test_search_plan_feeds_retriever(self):
        from legacy.news.schemas import SearchPlan
        plan = SearchPlan(
            fund_code="110011",
            stocks=["600519", "000858"],
            themes=["消费"],
            macro_queries=["美联储利率", "LPR调整"],
        )
        # Verify plan can generate retrieval queries
        assert len(plan.stocks) + len(plan.macro_queries) >= 2
        # Plan should have enough data to drive retrieval
        assert plan.fund_code != ""
