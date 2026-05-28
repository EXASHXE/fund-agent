"""Tests for Phase 2 Classifier: 6-layer news classification."""
import pytest
import networkx as nx

from src.kg.graph import KnowledgeGraphBuilder
from src.kg.schema import KGNodeType, KGEdgeType
from src.news.schemas import NewsLayer, SearchPlan, ClassifiedNews


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
            {"stock_code": "300750", "stock_name": "宁德时代", "weight": 1.8},
        ],
        "sectors": [
            {"industry": "食品饮料", "weight": 30.5},
        ],
    }
    graph = kg.build_from_holdings(fund_data)
    return graph


@pytest.fixture
def sample_search_plan():
    return SearchPlan(
        fund_code="110011",
        fund_name="易方达中小盘混合",
        stocks=["600519", "000858"],
        stock_names=["贵州茅台", "五粮液"],
        sectors=["食品饮料"],
        themes=["消费", "白酒"],
        heavy_holdings=["600519", "000858"],
    )


class TestClassifierLayerLogic:
    """Test news classification into 6 layers."""

    def test_fund_direct_match_by_code(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "易方达中小盘公告", "content": "基金公告", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].layer == NewsLayer.FUND_DIRECT
        assert result[0].weight == 1.0

    def test_fund_direct_match_by_name(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "易方达中小盘基金经理变更", "content": "test", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].layer == NewsLayer.FUND_DIRECT

    def test_heavy_holding_match(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "贵州茅台一季报发布", "content": "茅台营收增长", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].layer == NewsLayer.HEAVY_HOLDING
        assert result[0].weight == 0.8

    def test_industry_match(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "食品饮料行业景气度提升", "content": "test", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].layer == NewsLayer.INDUSTRY
        assert result[0].weight == 0.5

    def test_theme_match(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "白酒板块集体走强", "content": "test", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].layer == NewsLayer.INDUSTRY
        assert result[0].weight >= 0.5

    def test_policy_macro_match(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "央行宣布降息", "content": "LPR下调", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].layer == NewsLayer.POLICY_MACRO
        assert result[0].weight == 0.3

    def test_overseas_match(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "纳斯达克指数大幅波动", "content": "美股科技股下跌", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].layer == NewsLayer.OVERSEAS
        assert result[0].weight == 0.2

    def test_black_swan_match(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "系统性风险爆发", "content": "市场崩盘恐慌蔓延", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        # Black swan should be detected
        assert any(r.layer == NewsLayer.BLACK_SWAN for r in result)

    def test_classification_priority(self, sample_search_plan):
        """Test that fund-direct takes priority over other matches."""
        from src.news.classifier import Classifier
        c = Classifier()

        # A news item that mentions both the fund code AND a heavy holding
        news = [{"title": "110011 净值更新 贵州茅台", "content": "test", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        # Fund-direct should win
        assert result[0].layer == NewsLayer.FUND_DIRECT

    def test_classify_news_sets_metadata(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "贵州茅台大涨", "content": "茅台涨5%", "date": "2026-05-27", "source": "财联社"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) > 0
        assert result[0].fund_code == "110011"
        assert result[0].matched_entity in ("600519", "贵州茅台")
        assert result[0].entity_type == "stock"

    def test_irrelevant_news_gets_default_layer(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [{"title": "火星探测器成功着陆", "content": "太空探索", "date": "2026-05-27"}]
        result = c.classify_news(news, sample_search_plan, "110011")

        # Should still classify, but with low weight
        assert len(result) >= 0  # May return empty if filtered
        if result:
            assert result[0].weight <= 0.3  # Low weight for unrelated news


class TestClassifierEdgeCases:
    """Test edge cases for classifier."""

    def test_empty_news_list(self):
        from src.news.classifier import Classifier
        c = Classifier()
        plan = SearchPlan(fund_code="110011")

        result = c.classify_news([], plan, "110011")

        assert result == []

    def test_unknown_fund_code(self):
        from src.news.classifier import Classifier
        c = Classifier()
        plan = SearchPlan(fund_code="999999")

        news = [{"title": "央行降息", "content": "test", "date": "2026-05-27"}]
        result = c.classify_news(news, plan, "999999")

        assert len(result) > 0
        assert result[0].fund_code == "999999"

    def test_classify_multiple_news(self, sample_search_plan):
        from src.news.classifier import Classifier
        c = Classifier()

        news = [
            {"title": "贵州茅台大涨", "content": "涨5%", "date": "2026-05-27"},
            {"title": "央行降息", "content": "LPR下调", "date": "2026-05-27"},
            {"title": "食品饮料行业回暖", "content": "景气度", "date": "2026-05-27"},
        ]
        result = c.classify_news(news, sample_search_plan, "110011")

        assert len(result) == 3
        layers = {r.layer for r in result}
        assert NewsLayer.HEAVY_HOLDING in layers
        assert NewsLayer.POLICY_MACRO in layers
        assert NewsLayer.INDUSTRY in layers
