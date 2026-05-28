"""Test FundamentalScoreCalculator: fundamental analysis scoring with KG exposure and event aggregation."""
import networkx as nx
import pytest

from src.analysis.scoring.types import ScoreComponent
from src.kg.graph import KnowledgeGraphBuilder


@pytest.fixture
def kg_builder():
    return KnowledgeGraphBuilder()


@pytest.fixture
def fund_data_with_holdings():
    """Fund data with holdings and sectors for KG building."""
    return {
        "code": "110011",
        "name": "测试混合基金",
        "fund_type": "混合型",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "sector": "食品饮料", "industry": "食品饮料", "weight": 15.0},
            {"stock_code": "000858", "stock_name": "五粮液", "sector": "食品饮料", "industry": "食品饮料", "weight": 10.0},
            {"stock_code": "000333", "stock_name": "美的集团", "sector": "家用电器", "industry": "家用电器", "weight": 8.0},
        ],
        "sectors": [
            {"industry": "食品饮料", "sw_code": "801120", "weight": 25.0},
            {"industry": "家用电器", "sw_code": "801200", "weight": 8.0},
        ],
    }


@pytest.fixture
def graph_with_exposure(fund_data_with_holdings, kg_builder):
    """Build KG from fund holdings."""
    return kg_builder.build_from_holdings(fund_data_with_holdings)


class TestFundamentalScoreCompute:
    """Core fundamental score computation."""

    def test_returns_score_component(self, graph_with_exposure, fund_data_with_holdings):
        """Should return a valid ScoreComponent."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        result = calc.compute(fund_data_with_holdings, graph_with_exposure, [])

        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100
        assert isinstance(result.detail, dict)
        assert 0 <= result.confidence <= 1.0

    def test_empty_fund_data_fallback(self):
        """Empty fund data returns default score with low confidence."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        result = calc.compute({}, nx.DiGraph(), [])

        assert result.score == 50.0
        assert result.confidence <= 0.3

    def test_kg_exposure_contributes_to_score(self, graph_with_exposure, fund_data_with_holdings):
        """Fund with multiple industry/themes gets higher score from diversification."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        result = calc.compute(fund_data_with_holdings, graph_with_exposure, [])

        assert result.score > 50.0
        # Should have industry/themes in detail
        assert "industries" in result.detail or "exposure" in result.detail

    def test_positive_events_improve_score(self, graph_with_exposure, fund_data_with_holdings):
        """Positive events should increase the fundamental score."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        no_events = calc.compute(fund_data_with_holdings, graph_with_exposure, [])
        positive_events = [
            {"type": "earnings_surprise", "polarity": 0.8, "magnitude": 0.7},
            {"type": "tech_breakthrough", "polarity": 0.7, "magnitude": 0.6},
        ]
        with_events = calc.compute(fund_data_with_holdings, graph_with_exposure, positive_events)

        assert with_events.score >= no_events.score

    def test_negative_events_decrease_score(self, graph_with_exposure, fund_data_with_holdings):
        """Negative events should decrease the fundamental score."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        baseline = calc.compute(fund_data_with_holdings, graph_with_exposure, [])
        negative_events = [
            {"type": "earnings_miss", "polarity": -0.7, "magnitude": 0.8},
            {"type": "rate_change", "polarity": -0.5, "magnitude": 0.6},
        ]
        with_events = calc.compute(fund_data_with_holdings, graph_with_exposure, negative_events)

        assert with_events.score < baseline.score

    def test_detail_contains_diversity_metrics(self, graph_with_exposure, fund_data_with_holdings):
        """Detail dict should include industry/themes diversity info."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        result = calc.compute(fund_data_with_holdings, graph_with_exposure, [])

        assert "industries" in result.detail
        assert "themes" in result.detail
        assert result.detail["industries"] >= 1  # at least one industry

    def test_no_kg_but_with_events_still_computable(self):
        """Events alone should produce a meaningful score even without KG."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        events = [
            {"type": "earnings_surprise", "polarity": 0.6, "magnitude": 0.5},
        ]
        result = calc.compute({"code": "110011"}, nx.DiGraph(), events)

        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100

    def test_llm_client_acceptance(self, graph_with_exposure, fund_data_with_holdings):
        """Should accept llm_client parameter without error (stub/no-op)."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        result = calc.compute(fund_data_with_holdings, graph_with_exposure, [], llm_client=None)

        assert isinstance(result, ScoreComponent)

    def test_confidence_increases_with_exposure_data(self, graph_with_exposure, fund_data_with_holdings):
        """More KG data should yield higher confidence."""
        from src.analysis.scoring.fundamental import FundamentalScoreCalculator

        calc = FundamentalScoreCalculator()
        no_kg = calc.compute({"code": "110011"}, nx.DiGraph(), [])
        with_kg = calc.compute(fund_data_with_holdings, graph_with_exposure, [])

        assert with_kg.confidence > no_kg.confidence
