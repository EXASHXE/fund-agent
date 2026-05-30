"""Tests for src.tools.portfolio.builder (Phase 1.4).

Verifies build_portfolio_risk_matrix, portfolio_summary, _infer_exposure_cluster.
"""

from __future__ import annotations

import unittest

import pandas as pd

from src.tools.portfolio.builder import (
    build_portfolio_risk_matrix,
    portfolio_summary,
    _infer_exposure_cluster,
)


class TestInferExposureCluster(unittest.TestCase):
    """_infer_exposure_cluster(candidate)"""

    def test_cluster_defensive_income(self):
        """Bond/fixed-income keywords -> defensive_income."""
        for kw in ["债", "固收", "货币", "短债"]:
            result = _infer_exposure_cluster({"name": f"{kw}基金", "type": "", "theme": ""})
            self.assertEqual(result, "defensive_income", f"Keyword '{kw}' failed")

    def test_cluster_value_dividend(self):
        """Value/dividend keywords -> value_dividend."""
        for kw in ["红利", "价值", "银行", "低波", "股息"]:
            result = _infer_exposure_cluster({"name": f"{kw}ETF", "type": "", "theme": ""})
            self.assertEqual(result, "value_dividend", f"Keyword '{kw}' failed")

    def test_cluster_overseas(self):
        """Overseas keywords -> overseas."""
        for kw in ["QDII", "纳斯达克", "标普", "海外", "全球", "新兴市场"]:
            result = _infer_exposure_cluster({"name": f"{kw}主题", "type": "", "theme": ""})
            self.assertEqual(result, "overseas", f"Keyword '{kw}' failed")

    def test_cluster_healthcare(self):
        """Healthcare keywords -> healthcare."""
        for kw in ["医药", "医疗", "创新药", "生物"]:
            result = _infer_exposure_cluster({"name": f"{kw}基金", "type": "", "theme": ""})
            self.assertEqual(result, "healthcare", f"Keyword '{kw}' failed")

    def test_cluster_growth_manufacturing(self):
        """Tech/growth keywords -> growth_manufacturing."""
        for kw in ["半导体", "芯片", "新能源", "电池", "光伏", "储能", "AI", "人工智能", "科技"]:
            result = _infer_exposure_cluster({"name": f"{kw}ETF", "type": "", "theme": ""})
            self.assertEqual(result, "growth_manufacturing", f"Keyword '{kw}' failed")

    def test_cluster_commodity(self):
        """Commodity keywords -> commodity."""
        for kw in ["黄金", "石油", "原油", "商品", "能源"]:
            result = _infer_exposure_cluster({"name": f"{kw}基金", "type": "", "theme": ""})
            self.assertEqual(result, "commodity", f"Keyword '{kw}' failed")

    def test_cluster_broad_beta(self):
        """Broad index keywords -> broad_beta."""
        for kw in ["沪深300", "中证500", "中证1000", "上证50", "宽基"]:
            result = _infer_exposure_cluster({"name": f"{kw}指数", "type": "", "theme": ""})
            self.assertEqual(result, "broad_beta", f"Keyword '{kw}' failed")

    def test_cluster_balanced_other(self):
        """No matching keywords -> balanced_other."""
        result = _infer_exposure_cluster({"name": "灵活配置混合", "type": "混合型", "theme": "灵活"})
        self.assertEqual(result, "balanced_other")

    def test_cluster_from_theme_field(self):
        """Keywords matched from theme field."""
        result = _infer_exposure_cluster({"name": "某基金", "type": "", "theme": "半导体主题"})
        self.assertEqual(result, "growth_manufacturing")

    def test_cluster_from_type_field(self):
        """Keywords matched from type field."""
        result = _infer_exposure_cluster({"name": "某基金", "type": "货币基金", "theme": ""})
        self.assertEqual(result, "defensive_income")


class TestBuildPortfolioRiskMatrix(unittest.TestCase):
    """build_portfolio_risk_matrix(holdings_data, scores, correlations)"""

    def test_build_portfolio_risk_matrix_basic(self):
        """Mock holdings + scores -> verify structure."""
        holdings_data = {
            "funds": [
                {"code": "fund_a", "name": "沪深300指数", "value": 60000.0},
                {"code": "fund_b", "name": "半导体ETF", "value": 40000.0},
            ],
            "total_value": 100000.0,
        }
        scores = [
            {"fund_code": "fund_a", "fund_type": "指数型", "theme": "宽基"},
            {"fund_code": "fund_b", "fund_type": "股票型", "theme": "半导体"},
        ]
        result = build_portfolio_risk_matrix(holdings_data, scores)
        self.assertIn("cluster_exposures", result)
        self.assertIn("fund_clusters", result)
        self.assertIn("marginal_risk", result)
        self.assertIn("warnings", result)
        self.assertEqual(result["fund_clusters"]["fund_a"], "broad_beta")
        self.assertEqual(result["fund_clusters"]["fund_b"], "growth_manufacturing")
        self.assertAlmostEqual(result["cluster_exposures"]["broad_beta"], 0.6)
        self.assertAlmostEqual(result["cluster_exposures"]["growth_manufacturing"], 0.4)
        self.assertIn("fund_a", result["marginal_risk"])
        self.assertIn("fund_b", result["marginal_risk"])

    def test_build_portfolio_risk_matrix_with_correlations(self):
        """Correlation matrix adds correlation_load and risk_score adjustments."""
        holdings_data = {
            "funds": [
                {"code": "fund_a", "name": "沪深300指数", "value": 50000.0},
                {"code": "fund_b", "name": "中证500指数", "value": 50000.0},
            ],
            "total_value": 100000.0,
        }
        scores = [
            {"fund_code": "fund_a", "fund_type": "指数型", "theme": "宽基"},
            {"fund_code": "fund_b", "fund_type": "指数型", "theme": "宽基"},
        ]
        corr_df = pd.DataFrame(
            {"fund_a": [1.0, 0.9], "fund_b": [0.9, 1.0]},
            index=["fund_a", "fund_b"],
        )
        result = build_portfolio_risk_matrix(holdings_data, scores, correlations=corr_df)
        self.assertGreater(result["marginal_risk"]["fund_a"]["correlation_load"], 0.0)
        self.assertGreater(result["marginal_risk"]["fund_b"]["correlation_load"], 0.0)
        self.assertTrue(any("高相关" in w for w in result["warnings"]))

    def test_build_portfolio_risk_matrix_high_exposure_warning(self):
        """Fund cluster > 50%% exposure -> warning."""
        holdings_data = {
            "funds": [
                {"code": "fund_a", "name": "沪深300指数", "value": 80000.0},
                {"code": "fund_b", "name": "灵活配置混合", "value": 20000.0},
            ],
            "total_value": 100000.0,
        }
        scores = [
            {"fund_code": "fund_a", "fund_type": "指数型", "theme": "宽基"},
            {"fund_code": "fund_b", "fund_type": "混合型", "theme": "灵活"},
        ]
        result = build_portfolio_risk_matrix(holdings_data, scores)
        self.assertTrue(any("暴露" in w for w in result["warnings"]))

    def test_build_portfolio_risk_matrix_empty_holdings(self):
        """No holdings -> empty clusters and marginal_risk."""
        result = build_portfolio_risk_matrix({}, [])
        self.assertEqual(result["cluster_exposures"], {})
        self.assertEqual(result["fund_clusters"], {})
        self.assertEqual(result["marginal_risk"], {})

    def test_build_portfolio_risk_matrix_no_scores_match(self):
        """Scores don't match any fund codes -> still works."""
        holdings_data = {
            "funds": [
                {"code": "fund_a", "name": "沪深300指数", "value": 100000.0},
            ],
            "total_value": 100000.0,
        }
        result = build_portfolio_risk_matrix(holdings_data, [])
        self.assertIn("fund_a", result["marginal_risk"])

    def test_build_portfolio_risk_matrix_no_total_value(self):
        """No total_value in holdings_data -> weights are 0.0."""
        holdings_data = {
            "funds": [
                {"code": "fund_a", "name": "沪深300指数", "value": 100000.0},
            ],
        }
        result = build_portfolio_risk_matrix(holdings_data, [])
        self.assertEqual(result["marginal_risk"]["fund_a"]["position_weight"], 0.0)


class TestPortfolioSummary(unittest.TestCase):
    """portfolio_summary(holding_analyses)"""

    def test_portfolio_summary_basic(self):
        """Mock holdings -> verify totals."""
        holdings = [
            {
                "fund_code": "fund_a",
                "fund_name": "沪深300指数",
                "current_value": 12000.0,
                "total_cost": 10000.0,
                "profit": 2000.0,
                "return_pct": 20.0,
                "day_profit": 100.0,
                "week_profit": 300.0,
                "week_return_pct": 2.5,
                "day_return_pct": 0.83,
                "annual_return": 15.0,
                "avg_cost": 1.5,
                "pending_amount": 500.0,
            },
            {
                "fund_code": "fund_b",
                "fund_name": "半导体ETF",
                "current_value": 8000.0,
                "total_cost": 10000.0,
                "profit": -2000.0,
                "return_pct": -20.0,
                "day_profit": -50.0,
                "week_profit": -100.0,
                "week_return_pct": -1.2,
                "day_return_pct": -0.62,
                "annual_return": -10.0,
                "avg_cost": 2.0,
                "pending_amount": 0.0,
            },
        ]
        result = portfolio_summary(holdings)
        self.assertEqual(result["total_value"], 20000.0)
        self.assertEqual(result["total_cost"], 20000.0)
        self.assertEqual(result["total_profit"], 0.0)
        self.assertEqual(result["total_pending"], 500.0)
        self.assertEqual(result["total_return_pct"], 0.0)
        self.assertEqual(result["fund_count"], 2)
        self.assertIn("funds", result)
        self.assertEqual(len(result["funds"]), 2)
        self.assertIn("by_fund", result)
        self.assertIn("fund_a", result["by_fund"])
        self.assertIn("fund_b", result["by_fund"])

    def test_portfolio_summary_dca_enabled(self):
        """Fund with dca_enabled -> dca_status = 启用中."""
        holdings = [
            {
                "fund_code": "fund_a",
                "fund_name": "沪深300指数",
                "current_value": 10000.0,
                "total_cost": 10000.0,
                "profit": 0.0,
                "return_pct": 0.0,
                "day_profit": 0.0,
                "week_profit": 0.0,
                "week_return_pct": 0.0,
                "day_return_pct": 0.0,
                "annual_return": 0.0,
                "avg_cost": 0.0,
                "pending_amount": 0.0,
                "dca_enabled": True,
            },
        ]
        result = portfolio_summary(holdings)
        self.assertEqual(result["funds"][0]["dca_status"], "启用中")

    def test_portfolio_summary_dca_records(self):
        """Fund with dca_records -> dca_status = 启用中."""
        holdings = [
            {
                "fund_code": "fund_a",
                "fund_name": "沪深300指数",
                "current_value": 10000.0,
                "total_cost": 10000.0,
                "profit": 0.0,
                "return_pct": 0.0,
                "day_profit": 0.0,
                "week_profit": 0.0,
                "week_return_pct": 0.0,
                "day_return_pct": 0.0,
                "annual_return": 0.0,
                "avg_cost": 0.0,
                "pending_amount": 0.0,
                "dca_records": [{"date": "2024-01-01", "amount": 1000}],
            },
        ]
        result = portfolio_summary(holdings)
        self.assertEqual(result["funds"][0]["dca_status"], "启用中")

    def test_portfolio_summary_no_dca(self):
        """Fund without DCA -> dca_status = 未设置."""
        holdings = [
            {
                "fund_code": "fund_a",
                "fund_name": "沪深300指数",
                "current_value": 10000.0,
                "total_cost": 10000.0,
                "profit": 0.0,
                "return_pct": 0.0,
                "day_profit": 0.0,
                "week_profit": 0.0,
                "week_return_pct": 0.0,
                "day_return_pct": 0.0,
                "annual_return": 0.0,
                "avg_cost": 0.0,
                "pending_amount": 0.0,
            },
        ]
        result = portfolio_summary(holdings)
        self.assertEqual(result["funds"][0]["dca_status"], "未设置")

    def test_portfolio_summary_empty_list(self):
        """Empty holdings -> zero values."""
        result = portfolio_summary([])
        self.assertEqual(result["total_value"], 0.0)
        self.assertEqual(result["total_cost"], 0.0)
        self.assertEqual(result["total_profit"], 0.0)
        self.assertEqual(result["total_pending"], 0.0)
        self.assertEqual(result["fund_count"], 0)
        self.assertEqual(result["funds"], [])

    def test_portfolio_summary_day_return_pct(self):
        """total_day_return_pct = total_day_profit / prev_total_value."""
        holdings = [
            {
                "fund_code": "fund_a",
                "fund_name": "Test Fund",
                "current_value": 10100.0,
                "total_cost": 10000.0,
                "profit": 100.0,
                "return_pct": 1.0,
                "day_profit": 100.0,
                "week_profit": 0.0,
                "week_return_pct": 0.0,
                "day_return_pct": 0.99,
                "annual_return": 10.0,
                "avg_cost": 1.0,
                "pending_amount": 0,
            },
        ]
        result = portfolio_summary(holdings)
        self.assertEqual(result["total_day_return_pct"], 1.0)

    def test_portfolio_summary_zero_prev_value(self):
        """When prev_total_value is 0, total_day_return_pct = 0.0."""
        holdings = [
            {
                "fund_code": "fund_a",
                "fund_name": "Test Fund",
                "current_value": 100.0,
                "total_cost": 100.0,
                "profit": 0.0,
                "return_pct": 0.0,
                "day_profit": 100.0,
                "week_profit": 0.0,
                "week_return_pct": 0.0,
                "day_return_pct": 0.0,
                "annual_return": 0.0,
                "avg_cost": 0.0,
                "pending_amount": 0,
            },
        ]
        result = portfolio_summary(holdings)
        self.assertEqual(result["total_day_return_pct"], 0.0)

    def test_portfolio_summary_zero_cost(self):
        """Zero total_cost -> total_return_pct = 0.0."""
        holdings = [
            {
                "fund_code": "fund_a",
                "fund_name": "Test Fund",
                "current_value": 10000.0,
                "total_cost": 0.0,
                "profit": 10000.0,
                "return_pct": 0.0,
                "day_profit": 0.0,
                "week_profit": 0.0,
                "week_return_pct": 0.0,
                "day_return_pct": 0.0,
                "annual_return": 0.0,
                "avg_cost": 0.0,
                "pending_amount": 0,
            },
        ]
        result = portfolio_summary(holdings)
        self.assertEqual(result["total_return_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
