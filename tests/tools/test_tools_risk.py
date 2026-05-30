"""Tests for src.tools.risk.metrics (Phase 1.4).

Verifies sortino_ratio, compute_perf_from_nav, compute_correlations, stress_test.
"""

from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from src.tools.risk.metrics import (
    sortino_ratio,
    compute_perf_from_nav,
    compute_correlations,
    stress_test,
    _fund_exposure_text,
    _infer_risk_scenarios,
)


class TestSortinoRatio(unittest.TestCase):
    """sortino_ratio(daily_returns, mar_annual)"""

    def test_sortino_ratio_basic(self):
        """Known daily returns -> known Sortino, verify against manual calculation.

        If all returns = 0.001 (0.1%% daily) and MAR = 0.025 annual:
          mar_daily = (1.025)**(1/252) - 1 ~ 9.78e-5
          excess = 0.001 - 9.78e-5 = 0.000902
          downside = min(excess, 0) -> all zero since excess > 0
          downside_dev = 0 -> sortino = 0
        """
        returns = [0.001] * 252
        result = sortino_ratio(returns, mar_annual=0.025)
        # All returns above MAR -> no downside -> Sortino = 0
        self.assertEqual(result, 0.0)

    def test_sortino_ratio_with_downside(self):
        """Mix of positive and negative returns produces nonzero Sortino."""
        returns = [0.002] * 100 + [-0.01] * 100 + [0.003] * 52
        result = sortino_ratio(returns, mar_annual=0.025)
        self.assertLess(result, 0.0)
        self.assertIsInstance(result, float)

    def test_sortino_ratio_custom_mar(self):
        """Different MAR values produce different results."""
        returns = [0.001] * 100 + [-0.005] * 100 + [0.002] * 52
        result_low = sortino_ratio(returns, mar_annual=0.01)
        result_high = sortino_ratio(returns, mar_annual=0.10)
        self.assertGreaterEqual(result_low, result_high)

    def test_sortino_ratio_no_downside(self):
        """All positive returns -> Sortino = 0 (no downside deviation)."""
        returns = [0.01] * 252
        result = sortino_ratio(returns, mar_annual=0.025)
        self.assertEqual(result, 0.0)

    def test_sortino_ratio_empty_list(self):
        """Empty daily_returns -> 0.0."""
        self.assertEqual(sortino_ratio([], mar_annual=0.025), 0.0)

    def test_sortino_ratio_none(self):
        """None daily_returns -> 0.0."""
        self.assertEqual(sortino_ratio(None, mar_annual=0.025), 0.0)

    def test_sortino_ratio_too_few_points(self):
        """Fewer than 20 returns -> 0.0."""
        self.assertEqual(sortino_ratio([0.001] * 19, mar_annual=0.025), 0.0)

    def test_sortino_ratio_default_mar(self):
        """When mar_annual is None, uses QUANT_CONFIG default (0.025)."""
        returns = [0.001] * 252
        result = sortino_ratio(returns)
        self.assertEqual(result, 0.0)

    def test_sortino_ratio_precision(self):
        """Result is rounded to 4 decimal places."""
        returns = [0.001] * 200 + [-0.02] * 52
        result = sortino_ratio(returns, mar_annual=0.025)
        str_repr = str(result)
        if "." in str_repr:
            decimals = len(str_repr.split(".")[1])
            self.assertLessEqual(decimals, 4)


class TestComputePerfFromNav(unittest.TestCase):
    """compute_perf_from_nav(nav_df)"""

    def setUp(self):
        np.random.seed(42)
        n = 500
        daily_returns = np.random.normal(0.0005, 0.01, n).tolist()
        self.nav_df = pd.DataFrame({"日增长率": daily_returns})

    def test_compute_perf_from_nav_basic(self):
        """Known NAV series -> verify dict structure with 近1年 and 近3年."""
        result = compute_perf_from_nav(self.nav_df)
        self.assertIn("近1年", result)
        self.assertIn("近3年", result)
        for period in ["近1年", "近3年"]:
            self.assertIn("annual_volatility", result[period])
            self.assertIn("sharpe_ratio", result[period])
            self.assertIn("max_drawdown", result[period])
            for key in ["annual_volatility", "sharpe_ratio", "max_drawdown"]:
                val = result[period][key]
                self.assertIsInstance(val, (int, float))

    def test_compute_perf_from_nav_single_point(self):
        """Single NAV point -> empty result dict."""
        single_df = pd.DataFrame({"日增长率": [0.5]})
        result = compute_perf_from_nav(single_df)
        self.assertEqual(result, {"近1年": {}, "近3年": {}})

    def test_compute_perf_from_nav_fewer_than_30(self):
        """Fewer than 30 returns -> empty result dict."""
        short_df = pd.DataFrame({"日增长率": [0.1] * 29})
        result = compute_perf_from_nav(short_df)
        self.assertEqual(result, {"近1年": {}, "近3年": {}})

    def test_compute_perf_from_nav_none(self):
        """None NAV -> empty result dict."""
        result = compute_perf_from_nav(None)
        self.assertEqual(result, {"近1年": {}, "近3年": {}})

    def test_compute_perf_from_nav_empty_df(self):
        """Empty DataFrame -> empty result dict."""
        result = compute_perf_from_nav(pd.DataFrame())
        self.assertEqual(result, {"近1年": {}, "近3年": {}})

    def test_compute_perf_from_nav_missing_column(self):
        """DataFrame without 日增长率 -> empty result dict."""
        df = pd.DataFrame({"wrong_col": [1, 2, 3]})
        result = compute_perf_from_nav(df)
        self.assertEqual(result, {"近1年": {}, "近3年": {}})

    def test_compute_perf_from_nav_less_than_252_days(self):
        """Between 30 and 252 returns: 近1年 vol from all data, 近1年 dd = 0."""
        df = pd.DataFrame({"日增长率": [0.001] * 100})
        result = compute_perf_from_nav(df)
        self.assertIn("近1年", result)
        self.assertIn("近3年", result)
        self.assertEqual(result["近1年"]["max_drawdown"], 0.0)

    def test_compute_perf_from_nav_all_positive_returns(self):
        """Identical returns (std=0) -> Sharpe undefined, returns 0.0."""
        df = pd.DataFrame({"日增长率": [0.1] * 300})
        result = compute_perf_from_nav(df)
        sharpe_1y = result["近1年"]["sharpe_ratio"]
        self.assertEqual(sharpe_1y, 0.0)


class TestComputeCorrelations(unittest.TestCase):
    """compute_correlations(funds_data)"""

    def test_compute_correlations_basic(self):
        """Two funds with known NAV -> verify correlation DataFrame structure."""
        np.random.seed(42)
        n = 100
        fund_a = pd.DataFrame({"日增长率": np.random.normal(0.001, 0.01, n).tolist()})
        fund_b = pd.DataFrame({"日增长率": np.random.normal(0.001, 0.01, n).tolist()})
        funds_data = {
            "fund_a": {"nav": fund_a},
            "fund_b": {"nav": fund_b},
        }
        result = compute_correlations(funds_data)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn("fund_a", result.columns)
        self.assertIn("fund_b", result.columns)
        self.assertEqual(result.shape, (2, 2))
        self.assertAlmostEqual(result.loc["fund_a", "fund_a"], 1.0)

    def test_compute_correlations_single_fund(self):
        """Only one fund -> empty DataFrame."""
        fund_data = {
            "fund_a": {"nav": pd.DataFrame({"日增长率": [0.1] * 50})},
        }
        result = compute_correlations(fund_data)
        self.assertTrue(result.empty)

    def test_compute_correlations_no_funds(self):
        """Empty funds_data -> empty DataFrame."""
        result = compute_correlations({})
        self.assertTrue(result.empty)

    def test_compute_correlations_no_nav_data(self):
        """Funds without NAV data -> empty DataFrame."""
        funds_data = {
            "fund_a": {},
            "fund_b": {},
        }
        result = compute_correlations(funds_data)
        self.assertTrue(result.empty)

    def test_compute_correlations_too_few_returns(self):
        """Funds with fewer than 30 returns -> empty correlation."""
        fund_a = pd.DataFrame({"日增长率": [0.1] * 10})
        fund_b = pd.DataFrame({"日增长率": [0.2] * 10})
        funds_data = {
            "fund_a": {"nav": fund_a},
            "fund_b": {"nav": fund_b},
        }
        result = compute_correlations(funds_data)
        self.assertTrue(result.empty)


class TestStressTest(unittest.TestCase):
    """stress_test(funds_data) and helpers"""

    def test_stress_test_basic(self):
        """Mock funds data -> verify scenario structure."""
        funds_data = {
            "110011": {
                "basic": {"name": "易方达中小盘混合", "fund_type": "混合型"},
                "holdings": pd.DataFrame({"占净值比例": ["5.0%"], "股票名称": ["贵州茅台"]}),
                "sectors": pd.DataFrame(),
            }
        }
        results = stress_test(funds_data)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for item in results:
            self.assertIn("scenario_id", item)
            self.assertIn("scenario_desc", item)
            self.assertIn("fund_code", item)
            self.assertIn("fund_name", item)
            self.assertIn("estimated_drawdown_pct", item)
            self.assertIn("risk_driver", item)
            self.assertIn("agent_review_required", item)
            self.assertIn("agent_instruction", item)
            self.assertTrue(item["agent_review_required"])
            self.assertIsInstance(item["estimated_drawdown_pct"], (int, float))

    def test_stress_test_empty_funds(self):
        """Empty funds_data -> empty list."""
        results = stress_test({})
        self.assertEqual(results, [])

    def test_stress_test_fund_without_basic(self):
        """Fund without basic info -> still generates scenarios."""
        funds_data = {
            "123456": {
                "holdings": pd.DataFrame(),
            }
        }
        results = stress_test(funds_data)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["fund_code"], "123456")

    def test_stress_test_semiconductor_keyword(self):
        """Fund with semiconductor keywords -> R_SEMI scenario."""
        funds_data = {
            "001234": {
                "basic": {"name": "半导体ETF", "fund_type": "股票型"},
            }
        }
        results = stress_test(funds_data)
        scenario_ids = {r["scenario_id"] for r in results}
        self.assertIn("R_SEMI", scenario_ids)
        semi = [r for r in results if r["scenario_id"] == "R_SEMI"]
        self.assertEqual(semi[0]["estimated_drawdown_pct"], -10.0)

    def test_stress_test_default_scenario(self):
        """Fund with no matching keywords -> R_MARKET default."""
        results = _infer_risk_scenarios("随机基金名称", "混合型", "无关键词文本")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "R_MARKET")
        self.assertEqual(results[0]["seed_drawdown"], -6.0)

    def test_infer_risk_scenarios_multiple_matches(self):
        """Fund matching multiple keyword groups -> multiple scenarios."""
        text = "半导体 AI 新能源 消费"
        results = _infer_risk_scenarios("全能基金", "混合型", text)
        ids = {r["id"] for r in results}
        self.assertIn("R_SEMI", ids)
        self.assertIn("R_AI", ids)
        self.assertIn("R_EV", ids)
        self.assertIn("R_CONSUMER", ids)

    def test_fund_exposure_text_empty(self):
        """Empty fund dict -> empty string."""
        result = _fund_exposure_text({})
        self.assertIsInstance(result, str)

    def test_fund_exposure_text_with_basic(self):
        """Fund with basic info -> contributions from basic values."""
        fund = {"basic": {"name": "测试基金", "fund_type": "股票型"}}
        result = _fund_exposure_text(fund)
        self.assertIn("测试基金", result)
        self.assertIn("股票型", result)

    def test_fund_exposure_text_with_holdings_dataframe(self):
        """Fund with holdings DataFrame -> contributions from holdings."""
        fund = {
            "holdings": pd.DataFrame({"股票名称": ["贵州茅台"], "占净值比例": ["5.0%"]}),
        }
        result = _fund_exposure_text(fund)
        self.assertIn("贵州茅台", result)


if __name__ == "__main__":
    unittest.main()
