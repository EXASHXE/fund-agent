"""Test PositionScoreCalculator: position risk scoring with HHI, diversification, and risk factors."""
import networkx as nx
import pytest

from src.analysis.scoring.types import ScoreComponent


@pytest.fixture
def diversified_fund_data():
    """Fund data with diversified holdings."""
    return {
        "code": "110011",
        "name": "均衡配置基金",
        "fund_type": "混合型",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "industry": "食品饮料", "weight": 10.0},
            {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 8.0},
            {"stock_code": "000333", "stock_name": "美的集团", "industry": "家用电器", "weight": 8.0},
            {"stock_code": "600036", "stock_name": "招商银行", "industry": "银行", "weight": 7.0},
            {"stock_code": "300750", "stock_name": "宁德时代", "industry": "电力设备", "weight": 6.0},
            {"stock_code": "002415", "stock_name": "海康威视", "industry": "计算机", "weight": 5.0},
            {"stock_code": "600276", "stock_name": "恒瑞医药", "industry": "医药生物", "weight": 5.0},
        ],
    }


@pytest.fixture
def concentrated_fund_data():
    """Fund data with concentrated holdings (high HHI)."""
    return {
        "code": "000001",
        "name": "集中持仓基金",
        "fund_type": "股票型",
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "industry": "食品饮料", "weight": 35.0},
            {"stock_code": "000858", "stock_name": "五粮液", "industry": "食品饮料", "weight": 30.0},
            {"stock_code": "000568", "stock_name": "泸州老窖", "industry": "食品饮料", "weight": 25.0},
        ],
    }


class TestPositionScoreCompute:
    """Core position score computation."""

    def test_returns_score_component(self, diversified_fund_data):
        """Should return a valid ScoreComponent."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        result = calc.compute(diversified_fund_data, nx.DiGraph())

        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100
        assert isinstance(result.detail, dict)
        assert 0 <= result.confidence <= 1.0

    def test_empty_holdings_fallback(self):
        """Empty holdings returns default score with low confidence."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        result = calc.compute({"code": "110011"}, nx.DiGraph())

        assert result.score == 50.0
        assert result.confidence <= 0.3

    def test_diversified_scores_higher_than_concentrated(self, diversified_fund_data, concentrated_fund_data):
        """Diversified holdings should score higher than concentrated ones."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        div_result = calc.compute(diversified_fund_data, nx.DiGraph())
        conc_result = calc.compute(concentrated_fund_data, nx.DiGraph())

        assert div_result.score > conc_result.score

    def test_hhi_in_detail(self, diversified_fund_data):
        """Detail should include HHI concentration metric."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        result = calc.compute(diversified_fund_data, nx.DiGraph())

        assert "hhi" in result.detail or "concentration_risk" in result.detail

    def test_weights_sum_to_one(self, diversified_fund_data):
        """Sub-factor weights should sum to 1.0."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        result = calc.compute(diversified_fund_data, nx.DiGraph())

        weight_sum = sum(result.weights.values())
        assert abs(weight_sum - 1.0) < 0.01, f"weights sum to {weight_sum}"

    def test_five_sub_factors(self, diversified_fund_data):
        """Should include all 5 sub-factors: concentration, style, industry, single_name, overseas."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        result = calc.compute(diversified_fund_data, nx.DiGraph())

        expected_factors = {"concentration", "style_drift", "industry_exposure", "single_name_risk", "overseas"}
        detail_keys = set(result.detail.keys())
        assert expected_factors.issubset(detail_keys), f"missing: {expected_factors - detail_keys}"

    def test_high_concentration_lowers_score(self, diversified_fund_data, concentrated_fund_data):
        """Concentrated fund should have lower concentration sub-score."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        div = calc.compute(diversified_fund_data, nx.DiGraph())
        conc = calc.compute(concentrated_fund_data, nx.DiGraph())

        div_conc = div.detail.get("concentration", 50)
        conc_conc = conc.detail.get("concentration", 50)
        assert div_conc > conc_conc, f"diversified:{div_conc} <= concentrated:{conc_conc}"

    def test_multi_industry_scores_higher_industry_exposure(self, diversified_fund_data, concentrated_fund_data):
        """Multi-industry fund should have higher industry_exposure score."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        div = calc.compute(diversified_fund_data, nx.DiGraph())
        conc = calc.compute(concentrated_fund_data, nx.DiGraph())

        assert div.detail["industry_exposure"] > conc.detail["industry_exposure"]

    def test_single_name_risk_penalizes_high_weight(self, diversified_fund_data, concentrated_fund_data):
        """Funds with high single-stock weights should have lower single_name_risk scores."""
        from src.analysis.scoring.position import PositionScoreCalculator

        calc = PositionScoreCalculator()
        div = calc.compute(diversified_fund_data, nx.DiGraph())
        conc = calc.compute(concentrated_fund_data, nx.DiGraph())

        assert div.detail["single_name_risk"] > conc.detail["single_name_risk"]
