"""Tests for the unified XIRR implementation (Phase 1.3).

Verifies:
  - The canonical xirr() function in src.tools.math.xirr
  - Delegation wrappers calc_xirr() and _calc_xirr() produce identical results
  - Edge cases: empty, single flow, zero return, irregular intervals, etc.
"""

from __future__ import annotations

from datetime import date
from math import isclose
import unittest

from src.tools.math.xirr import xirr
from src.tools.math.calc import calc_xirr, _calc_xirr


class TestXirrCanonical(unittest.TestCase):
    """Direct tests of the canonical xirr() function."""

    def test_positive_return(self):
        """Standard positive return: invest 10000 → 12000 after 1 year → ~20%."""
        result = xirr(
            [(date(2023, 1, 1), -10000.0)],
            current_value=12000.0,
            current_date=date(2024, 1, 1),
        )
        self.assertAlmostEqual(result, 0.2, places=4)

    def test_negative_return(self):
        """Negative return: invest 10000 → 8000 after 1 year → ~-20%."""
        result = xirr(
            [(date(2023, 1, 1), -10000.0)],
            current_value=8000.0,
            current_date=date(2024, 1, 1),
        )
        self.assertAlmostEqual(result, -0.2, places=4)

    def test_zero_return(self):
        """Flat return: invest 10000 → 10000 after 1 year → 0%."""
        result = xirr(
            [(date(2023, 1, 1), -10000.0)],
            current_value=10000.0,
            current_date=date(2024, 1, 1),
        )
        self.assertAlmostEqual(result, 0.0, places=4)

    def test_empty_cashflows(self):
        """Empty cashflows → 0.0."""
        result = xirr([], current_value=10000.0, current_date=date(2024, 1, 1))
        self.assertEqual(result, 0.0)

    def test_single_cashflow(self):
        """Single cashflow + terminal value = two data points → valid XIRR."""
        result = xirr(
            [(date(2024, 6, 15), -5000.0)],
            current_value=5500.0,
            current_date=date(2025, 6, 15),
        )
        # 5000 * (1+r)^1 = 5500 → r = 0.10
        self.assertAlmostEqual(result, 0.1, places=4)

    def test_irregular_date_intervals(self):
        """Multiple investments at irregular intervals."""
        result = xirr(
            [
                (date(2023, 1, 1), -10000.0),    # initial investment
                (date(2024, 6, 15), -5000.0),    # additional 6 months later
            ],
            current_value=18000.0,
            current_date=date(2024, 1, 1),
        )
        # Should converge to a positive rate (invested 15000, worth 18000)
        self.assertGreater(result, 0.0)
        self.assertLess(result, 0.5)

    def test_only_negative_flows(self):
        """Only outflows (no positive) → 0.0."""
        result = xirr(
            [(date(2023, 1, 1), -10000.0), (date(2024, 6, 1), -5000.0)],
            current_value=-1000.0,  # negative terminal value
            current_date=date(2024, 1, 1),
        )
        self.assertEqual(result, 0.0)

    def test_current_date_defaults_to_today(self):
        """When current_date is None, defaults to date.today()."""
        # Use a cashflow in the past; should not raise
        result = xirr(
            [(date(2020, 1, 1), -10000.0)],
            current_value=12000.0,
        )
        self.assertIsNotNone(result)

    def test_zero_current_value(self):
        """Zero terminal value → 0.0."""
        result = xirr(
            [(date(2023, 1, 1), -10000.0)],
            current_value=0.0,
            current_date=date(2024, 1, 1),
        )
        self.assertEqual(result, 0.0)


class TestXirrDelegation(unittest.TestCase):
    """Verify that calc_xirr and _calc_xirr produce identical results to xirr()."""

    def setUp(self):
        self.cashflows = [(date(2023, 1, 1), -10000.0)]
        self.current_value = 12000.0
        self.current_date = date(2025, 1, 1)

    def test_calc_xirr_matches_xirr(self):
        expected = xirr(self.cashflows, self.current_value, self.current_date)
        result = calc_xirr(self.cashflows, self.current_value, self.current_date)
        self.assertAlmostEqual(result, expected, places=10)

    def test_calc_xirr_matches_xirr_negative(self):
        cfs = [(date(2023, 3, 1), -20000.0)]
        cv = 15000.0
        cd = date(2024, 3, 1)
        expected = xirr(cfs, cv, cd)
        result = calc_xirr(cfs, cv, cd)
        self.assertAlmostEqual(result, expected, places=10)

    def test_calc_xirr_matches_xirr_multi_cashflow(self):
        cfs = [
            (date(2024, 1, 1), -5000.0),
            (date(2024, 7, 1), -3000.0),
            (date(2024, 10, 1), 500.0),  # dividend
        ]
        cv = 8500.0
        cd = date(2025, 1, 1)
        expected = xirr(cfs, cv, cd)
        result = calc_xirr(cfs, cv, cd)
        self.assertAlmostEqual(result, expected, places=10)

    def test_calc_xirr_empty(self):
        expected = xirr([], 0.0, date(2025, 1, 1))
        result = calc_xirr([], 0.0, date(2025, 1, 1))
        self.assertEqual(result, expected)

    def test_under_calc_xirr_matches_xirr(self):
        expected = xirr(self.cashflows, self.current_value, self.current_date)
        result = _calc_xirr(self.cashflows, self.current_value, self.current_date)
        self.assertAlmostEqual(result, expected, places=10)

    def test_under_calc_xirr_matches_xirr_negative(self):
        cfs = [(date(2023, 3, 1), -20000.0)]
        cv = 15000.0
        cd = date(2024, 3, 1)
        expected = xirr(cfs, cv, cd)
        result = _calc_xirr(cfs, cv, cd)
        self.assertAlmostEqual(result, expected, places=10)

    def test_under_calc_xirr_matches_xirr_multi_cashflow(self):
        cfs = [
            (date(2024, 1, 1), -5000.0),
            (date(2024, 7, 1), -3000.0),
            (date(2024, 10, 1), 500.0),
        ]
        cv = 8500.0
        cd = date(2025, 1, 1)
        expected = xirr(cfs, cv, cd)
        result = _calc_xirr(cfs, cv, cd)
        self.assertAlmostEqual(result, expected, places=10)

    def test_calc_xirr_and_under_calc_xirr_identical(self):
        """Both delegation wrappers produce the same result for equal inputs."""
        r1 = calc_xirr(self.cashflows, self.current_value, self.current_date)
        r2 = _calc_xirr(self.cashflows, self.current_value, self.current_date)
        self.assertAlmostEqual(r1, r2, places=10)

    def test_all_three_identical_on_edge_case(self):
        """Empty cashflows: all three return 0.0."""
        self.assertEqual(
            xirr([], 0.0, date(2025, 1, 1)),
            calc_xirr([], 0.0, date(2025, 1, 1)),
        )
        self.assertEqual(
            xirr([], 0.0, date(2025, 1, 1)),
            _calc_xirr([], 0.0, date(2025, 1, 1)),
        )


if __name__ == "__main__":
    unittest.main()
