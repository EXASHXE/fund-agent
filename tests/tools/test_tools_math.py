"""Tests for src.tools.math.calc (Phase 1.4).

Verifies compute_hhi, _parse_weight_pct, _find_closest_nav, _match_nav,
compute_portfolio (NOT calc_xirr/_calc_xirr -- those are in test_tools_xirr.py).
"""

from __future__ import annotations

from datetime import date, timedelta
import unittest

import pandas as pd

from src.tools.math.calc import (
    compute_hhi,
    _parse_weight_pct,
    _find_closest_nav,
    _match_nav,
    compute_portfolio,
)


class TestComputeHhi(unittest.TestCase):
    """compute_hhi(holdings_df)"""

    def test_compute_hhi_basic(self):
        """Known weights -> known HHI.

        Equal weights (10%% each) for 10 stocks -> HHI = 10 * (10^2) = 1000.
        """
        data = {"占净值比例": ["10.0%"] * 10}
        df = pd.DataFrame(data)
        result = compute_hhi(df)
        self.assertAlmostEqual(result, 1000.0, places=2)

    def test_compute_hhi_concentrated(self):
        """Concentrated holdings -> higher HHI.

        One stock at 50%%, rest at 5%% each -> HHI = 2500 + 9*25 = 2725.
        """
        ratios = ["50.0%"] + ["5.0%"] * 9
        data = {"占净值比例": ratios}
        df = pd.DataFrame(data)
        result = compute_hhi(df)
        expected = 50.0**2 + 9 * (5.0**2)
        self.assertAlmostEqual(result, expected, places=2)

    def test_compute_hhi_empty(self):
        """Empty DataFrame -> None."""
        result = compute_hhi(pd.DataFrame())
        self.assertIsNone(result)

    def test_compute_hhi_none(self):
        """None input -> None."""
        result = compute_hhi(None)
        self.assertIsNone(result)

    def test_compute_hhi_no_weight_column(self):
        """DataFrame without any recognized weight column -> 0.0."""
        df = pd.DataFrame({"其他列": ["10.0%"] * 10})
        result = compute_hhi(df)
        self.assertEqual(result, 0.0)

    def test_compute_hhi_mixed_weight_columns(self):
        """Recognizes alternative weight column names."""
        data = {"持仓占比": ["20.0%", "20.0%", "20.0%", "20.0%", "20.0%"]}
        df = pd.DataFrame(data)
        result = compute_hhi(df)
        self.assertAlmostEqual(result, 2000.0, places=2)

    def test_compute_hhi_top_10_only(self):
        """Only top 10 rows are considered."""
        ratios = ["1.0%"] * 20
        df = pd.DataFrame({"占净值比例": ratios})
        result = compute_hhi(df)
        self.assertAlmostEqual(result, 10.0, places=2)

    def test_compute_hhi_rounding(self):
        """Result is rounded to 2 decimal places."""
        data = {"占净值比例": ["33.33%"] * 3}
        df = pd.DataFrame(data)
        result = compute_hhi(df)
        # HHI = sum of (w_i)^2 for i in 0..min(9, len-1)
        # 33.33^2 + 33.33^2 + 33.33^2 = 3 * 1110.8889 = 3332.6667
        self.assertAlmostEqual(result, 3 * 33.33**2, places=2)

    def test_compute_hhi_with_weight_below_one(self):
        """Weight <= 1 is multiplied by 100 before squaring."""
        data = {"占净值比例": [0.1, 0.1]}
        df = pd.DataFrame(data)
        result = compute_hhi(df)
        # _parse_weight_pct: 0.1 <= 1 -> 0.1 * 100 = 10.0
        # HHI = 10^2 + 10^2 = 200
        self.assertAlmostEqual(result, 200.0, places=2)


class TestParseWeightPct(unittest.TestCase):
    """_parse_weight_pct(value)"""

    def test_parse_weight_pct_basic(self):
        """"6.23%%" -> 6.23."""
        self.assertEqual(_parse_weight_pct("6.23%"), 6.23)

    def test_parse_weight_pct_no_percent(self):
        """"10.5" -> 10.5."""
        self.assertEqual(_parse_weight_pct("10.5"), 10.5)

    def test_parse_weight_pct_non_numeric(self):
        """Invalid string -> None."""
        self.assertIsNone(_parse_weight_pct("N/A"))

    def test_parse_weight_pct_nan_string(self):
        """"nan" -> None."""
        self.assertIsNone(_parse_weight_pct("nan"))

    def test_parse_weight_pct_none_string(self):
        """"none" -> None."""
        self.assertIsNone(_parse_weight_pct("none"))

    def test_parse_weight_pct_null_string(self):
        """"null" -> None."""
        self.assertIsNone(_parse_weight_pct("null"))

    def test_parse_weight_pct_none_value(self):
        """None -> None."""
        self.assertIsNone(_parse_weight_pct(None))

    def test_parse_weight_pct_empty_string(self):
        """Empty string -> None."""
        self.assertIsNone(_parse_weight_pct(""))

    def test_parse_weight_pct_whitespace(self):
        """Whitespace-only -> None."""
        self.assertIsNone(_parse_weight_pct("   "))

    def test_parse_weight_pct_float_below_one(self):
        """Value <= 1 is multiplied by 100."""
        result = _parse_weight_pct(0.05)
        self.assertEqual(result, 5.0)

    def test_parse_weight_pct_float_above_one(self):
        """Value > 1 is kept as-is."""
        result = _parse_weight_pct(5.5)
        self.assertEqual(result, 5.5)

    def test_parse_weight_pct_integer(self):
        """Integer input works."""
        result = _parse_weight_pct(10)
        self.assertEqual(result, 10.0)


class TestFindClosestNav(unittest.TestCase):
    """_find_closest_nav(nav_records, target_date, max_window=5)"""

    def setUp(self):
        self.base = date(2024, 1, 1)
        self.records = [
            {"date": self.base - timedelta(days=1), "nav": 1.0},
            {"date": self.base, "nav": 1.05},
            {"date": self.base + timedelta(days=1), "nav": 1.10},
            {"date": self.base + timedelta(days=2), "nav": 1.15},
        ]

    def test_find_closest_nav_exact_match(self):
        """Exact date match returns correct NAV."""
        result = _find_closest_nav(self.records, self.base)
        self.assertEqual(result, 1.05)

    def test_find_closest_nav_forward_lookup(self):
        """Date between NAV records finds nearest."""
        target = self.base + timedelta(days=3)
        result = _find_closest_nav(self.records, target)
        self.assertEqual(result, 1.15)

    def test_find_closest_nav_backward_lookup(self):
        """Date before any record but within window -> closest."""
        target = self.base - timedelta(days=3)
        result = _find_closest_nav(self.records, target)
        self.assertEqual(result, 1.0)

    def test_find_closest_nav_outside_window(self):
        """Date outside max_window -> None."""
        target = self.base + timedelta(days=10)
        result = _find_closest_nav(self.records, target, max_window=5)
        self.assertIsNone(result)

    def test_find_closest_nav_empty_records(self):
        """Empty nav_records -> None."""
        result = _find_closest_nav([], self.base)
        self.assertIsNone(result)

    def test_find_closest_nav_none_target(self):
        """None target_date -> None."""
        result = _find_closest_nav(self.records, None)
        self.assertIsNone(result)

    def test_find_closest_nav_exact_with_offset(self):
        """Exact match with max_window=0 only returns exact."""
        result = _find_closest_nav(self.records, self.base, max_window=0)
        self.assertEqual(result, 1.05)

    def test_find_closest_nav_forward_preferred(self):
        """Forward match (diff >= 0) preferred over backward match."""
        records = [
            {"date": self.base - timedelta(days=1), "nav": 1.0},
            {"date": self.base + timedelta(days=1), "nav": 1.10},
        ]
        target = self.base
        result = _find_closest_nav(records, target)
        self.assertEqual(result, 1.10)

    def test_find_closest_nav_string_date(self):
        """Date as string works."""
        records = [{"date": "2024-01-01", "nav": 1.05}]
        result = _find_closest_nav(records, date(2024, 1, 1))
        self.assertEqual(result, 1.05)

    def test_find_closest_nav_zero_nav_excluded(self):
        """Records with nav=0 are excluded (falsy check)."""
        records = [
            {"date": self.base, "nav": 0},
            {"date": self.base + timedelta(days=1), "nav": 1.10},
        ]
        result = _find_closest_nav(records, self.base + timedelta(days=1))
        self.assertEqual(result, 1.10)


class TestMatchNav(unittest.TestCase):
    """_match_nav(nav_map, target, today=None)"""

    def setUp(self):
        self.base = date(2024, 1, 1)
        self.nav_map = {
            self.base: 1.05,
            self.base + timedelta(days=1): 1.10,
            self.base + timedelta(days=3): 1.20,
        }

    def test_match_nav_exact_match(self):
        """Exact date in map returns correct NAV."""
        result = _match_nav(self.nav_map, self.base)
        self.assertEqual(result, 1.05)

    def test_match_nav_forward_lookup(self):
        """Date not in map -> forward search up to 5 days."""
        target = self.base + timedelta(days=2)
        result = _match_nav(self.nav_map, target)
        self.assertEqual(result, 1.20)

    def test_match_nav_backward_lookup(self):
        """Forward search fails -> backward search finds closest (base+3d = 1.20)."""
        target = self.base + timedelta(days=4)
        result = _match_nav(self.nav_map, target)
        self.assertEqual(result, 1.20)

    def test_match_nav_no_match(self):
        """No match within windows -> None."""
        target = self.base + timedelta(days=10)
        result = _match_nav(self.nav_map, target)
        self.assertIsNone(result)

    def test_match_nav_empty_map(self):
        """Empty nav_map -> None."""
        result = _match_nav({}, self.base)
        self.assertIsNone(result)

    def test_match_nav_with_today_nearby(self):
        """When target is within 3 days of today, forward-only is ok."""
        target = self.base + timedelta(days=1)
        result = _match_nav(self.nav_map, target, today=self.base + timedelta(days=2))
        self.assertEqual(result, 1.10)

    def test_match_nav_with_today_prevents_backward(self):
        """When target is within 3 days of today, returns None instead of backward."""
        target = self.base + timedelta(days=5)
        today = self.base + timedelta(days=6)
        result = _match_nav(self.nav_map, target, today=today)
        self.assertIsNone(result)


class TestComputePortfolio(unittest.TestCase):
    """compute_portfolio(fund_results)"""

    def test_compute_portfolio_basic(self):
        """Known fund results -> verify aggregation."""
        fund_results = {
            "fund_a": {
                "total_cost": 10000.0,
                "current_asset": 12000.0,
                "pending_amount": 500.0,
                "calibrations_rejected": [],
            },
            "fund_b": {
                "total_cost": 5000.0,
                "current_asset": 4500.0,
                "pending_amount": 0.0,
                "calibrations_rejected": [],
            },
        }
        result = compute_portfolio(fund_results)
        self.assertEqual(result["total_cost"], 15000.0)
        self.assertEqual(result["total_asset"], 16500.0)
        self.assertEqual(result["total_profit"], 1500.0)
        self.assertEqual(result["total_pending"], 500.0)
        self.assertEqual(result["fund_count"], 2)
        self.assertEqual(result["total_return_pct"], 10.0)
        self.assertEqual(result["calibration_errors"], [])

    def test_compute_portfolio_empty(self):
        """Empty fund_results -> zero-valued summary."""
        result = compute_portfolio({})
        self.assertEqual(result["total_cost"], 0.0)
        self.assertEqual(result["total_asset"], 0.0)
        self.assertEqual(result["total_profit"], 0.0)
        self.assertEqual(result["total_pending"], 0.0)
        self.assertEqual(result["fund_count"], 0)
        self.assertEqual(result["total_return_pct"], 0.0)

    def test_compute_portfolio_calibration_errors(self):
        """Funds with calibrations_rejected appear in errors."""
        fund_results = {
            "fund_a": {
                "total_cost": 10000.0,
                "current_asset": 12000.0,
                "pending_amount": 0.0,
                "calibrations_rejected": [{"date": "2024-01-01", "reason": "price gap"}],
            },
        }
        result = compute_portfolio(fund_results)
        self.assertEqual(len(result["calibration_errors"]), 1)
        self.assertEqual(result["calibration_errors"][0]["code"], "fund_a")

    def test_compute_portfolio_zero_cost(self):
        """Zero total_cost -> total_return_pct = 0.0."""
        fund_results = {
            "fund_a": {
                "total_cost": 0.0,
                "current_asset": 100.0,
                "pending_amount": 0.0,
                "calibrations_rejected": [],
            },
        }
        result = compute_portfolio(fund_results)
        self.assertEqual(result["total_return_pct"], 0.0)

    def test_compute_portfolio_rounding(self):
        """Values are rounded to 2 decimal places."""
        fund_results = {
            "fund_a": {
                "total_cost": 10000.1234,
                "current_asset": 12345.6789,
                "pending_amount": 5.6789,
                "calibrations_rejected": [],
            },
        }
        result = compute_portfolio(fund_results)
        self.assertEqual(result["total_cost"], 10000.12)
        self.assertEqual(result["total_asset"], 12345.68)
        self.assertEqual(result["total_pending"], 5.68)


if __name__ == "__main__":
    unittest.main()
