"""Tests for Phase 2 Summarizer: research-style AI summary."""
import pytest

from src.news.schemas import NewsLayer, ScoredNews, ResearchSummary


@pytest.fixture
def sample_scored_news():
    """Create sample scored news items for summarization testing."""
    return [
        ScoredNews(
            title="贵州茅台一季报发布，净利润超预期20%",
            content="贵州茅台发布一季度报告，净利润同比增长20%，超出市场预期",
            date="2026-05-27",
            source="财联社",
            layer=NewsLayer.HEAVY_HOLDING,
            weight=0.8,
            fund_code="110011",
            relevance_score=0.85,
            holding_overlap=1.0,
            top10_hit=True,
        ),
        ScoredNews(
            title="央行宣布降息5个基点",
            content="中国人民银行宣布下调LPR 5个基点，货币政策进一步宽松",
            date="2026-05-27",
            source="央行",
            layer=NewsLayer.POLICY_MACRO,
            weight=0.3,
            fund_code="110011",
            relevance_score=0.55,
            industry_hit=True,
        ),
    ]


class TestSummarizer:
    """Test research-style summarization."""

    def test_summarize_rule_based_fallback(self, sample_scored_news):
        """Without LLM, summarizer should produce rule-based summaries."""
        from src.news.summarizer import Summarizer
        s = Summarizer()

        summaries = s.summarize_news(sample_scored_news, "110011", llm_client=None)

        assert len(summaries) == len(sample_scored_news)
        for summary in summaries:
            assert isinstance(summary, ResearchSummary)
            assert summary.fund_code == "110011"
            assert summary.what != ""
            assert summary.why_important != ""
            assert summary.source == "rule_based"

    def test_summarize_empty_news(self):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        summaries = s.summarize_news([], "110011", llm_client=None)

        assert summaries == []

    def test_summarize_includes_fund_impact(self, sample_scored_news):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        summaries = s.summarize_news(sample_scored_news, "110011", llm_client=None)

        for summary in summaries:
            assert summary.fund_impact != ""

    def test_summarize_includes_time_horizon(self, sample_scored_news):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        summaries = s.summarize_news(sample_scored_news, "110011", llm_client=None)

        for summary in summaries:
            assert summary.time_horizon in ("short", "medium", "long")

    def test_summarize_includes_suggested_action(self, sample_scored_news):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        summaries = s.summarize_news(sample_scored_news, "110011", llm_client=None)

        for summary in summaries:
            assert summary.suggested_action != ""

    def test_summarize_sorts_by_relevance(self, sample_scored_news):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        summaries = s.summarize_news(sample_scored_news, "110011", llm_client=None)

        # First summary should be about the higher-scored news (茅台)
        assert "茅台" in summaries[0].news_title

    def test_summarize_with_mock_llm(self, sample_scored_news):
        """Test that summarizer can use LLM when available."""
        from unittest.mock import MagicMock
        from src.news.summarizer import Summarizer
        s = Summarizer()

        mock_llm = MagicMock()
        mock_llm.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content='{"what": "测试", "why_important": "重要", '
                                               '"fund_impact": "正向", "affected_holdings": ["600519"], '
                                               '"time_horizon": "short", '
                                               '"risk_opportunity": "opportunity", '
                                               '"suggested_action": "加仓观察", '
                                               '"confidence": 0.85}'))
        ]

        summaries = s.summarize_news(sample_scored_news[:1], "110011", llm_client=mock_llm)

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.source == "llm"
        assert summary.confidence == 0.85
        assert summary.time_horizon == "short"
        assert "600519" in summary.affected_holdings

    def test_summarize_llm_fallback_on_error(self, sample_scored_news):
        """When LLM fails, fall back to rule-based."""
        from unittest.mock import MagicMock
        from src.news.summarizer import Summarizer
        s = Summarizer()

        mock_llm = MagicMock()
        mock_llm.chat.completions.create.side_effect = Exception("LLM error")

        summaries = s.summarize_news(sample_scored_news[:1], "110011", llm_client=mock_llm)

        assert len(summaries) == 1
        assert summaries[0].source == "rule_based"


class TestSummarizerRuleBased:
    """Test rule-based fallback summary quality."""

    def test_rule_based_uses_title_as_what(self):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        news = ScoredNews(
            title="茅台业绩超预期", content="业绩大增",
            layer=NewsLayer.HEAVY_HOLDING, weight=0.8,
            fund_code="110011", relevance_score=0.9,
        )

        summary = s._rule_based_summary(news, "110011")

        assert "茅台" in summary.what

    def test_rule_based_positive_sentiment(self):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        news = ScoredNews(
            title="茅台大涨", content="大涨5%",
            layer=NewsLayer.HEAVY_HOLDING, weight=0.8,
            fund_code="110011", relevance_score=0.9,
        )

        summary = s._rule_based_summary(news, "110011")

        assert summary.risk_opportunity in ("opportunity", "neutral", "risk")

    def test_rule_based_uses_layer_for_impact(self):
        from src.news.summarizer import Summarizer
        s = Summarizer()

        heavy_news = ScoredNews(
            title="茅台", layer=NewsLayer.HEAVY_HOLDING, weight=0.8,
            fund_code="110011", relevance_score=0.9,
        )
        macro_news = ScoredNews(
            title="降息", layer=NewsLayer.POLICY_MACRO, weight=0.3,
            fund_code="110011", relevance_score=0.4,
        )

        s1 = s._rule_based_summary(heavy_news, "110011")
        s2 = s._rule_based_summary(macro_news, "110011")

        # Heavy holding should have more specific impact
        assert len(s1.why_important) > 0
        assert len(s2.why_important) > 0
