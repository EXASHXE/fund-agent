"""Tests for src.tools.scoring.helpers and src.tools.calendar.dates (Phase 1.4).

Verifies all scoring threshold functions, regime weights, confidence computation,
completeness assessment, and date utility functions.

All tests validate numerical correctness with known inputs/outputs.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest import TestCase, main

import pandas as pd

from src.tools.scoring.helpers import (
    score_sharpe,
    score_sortino_from_ratio,
    score_drawdown,
    score_volatility,
    score_alpha,
    regime_weights,
    compute_confidence,
    score_level,
    assess_completeness,
)
from src.tools.calendar.dates import (
    is_business_day,
    next_business_day,
    next_dca_date,
    to_date,
)


# ====================================================================
# Scoring threshold helpers (src.tools.scoring.helpers)
# ====================================================================

class TestScoreSharpe(TestCase):
    """score_sharpe(sharpe: float) -> 0-100 score."""

    def test_sharpe_above_2(self):
        """sharpe > 2.0 -> 90.0."""
        for v in [2.01, 3.0, 10.0]:
            self.assertEqual(score_sharpe(v), 90.0, f"sharpe={v}")

    def test_sharpe_between_1_5_and_2(self):
        """1.5 < sharpe <= 2.0 -> 80.0."""
        for v in [1.51, 1.8, 2.0]:
            self.assertEqual(score_sharpe(v), 80.0, f"sharpe={v}")

    def test_sharpe_between_1_and_1_5(self):
        """1.0 < sharpe <= 1.5 -> 70.0."""
        for v in [1.01, 1.25, 1.5]:
            self.assertEqual(score_sharpe(v), 70.0, f"sharpe={v}")

    def test_sharpe_between_0_5_and_1(self):
        """0.5 < sharpe <= 1.0 -> 60.0."""
        for v in [0.51, 0.75, 1.0]:
            self.assertEqual(score_sharpe(v), 60.0, f"sharpe={v}")

    def test_sharpe_between_0_and_0_5(self):
        """0.0 < sharpe <= 0.5 -> 50.0."""
        for v in [0.01, 0.25, 0.5]:
            self.assertEqual(score_sharpe(v), 50.0, f"sharpe={v}")

    def test_sharpe_zero_or_negative(self):
        """sharpe <= 0.0 -> 40.0."""
        for v in [0.0, -0.5, -1.0]:
            self.assertEqual(score_sharpe(v), 40.0, f"sharpe={v}")

    def test_sharpe_boundary_values(self):
        """Exactly at each threshold boundary."""
        self.assertEqual(score_sharpe(2.0), 80.0)
        self.assertEqual(score_sharpe(1.5), 70.0)
        self.assertEqual(score_sharpe(1.0), 60.0)
        self.assertEqual(score_sharpe(0.5), 50.0)
        self.assertEqual(score_sharpe(0.0), 40.0)


class TestScoreSortinoFromRatio(TestCase):
    """score_sortino_from_ratio(sortino: float) -> 0-100 score."""

    def test_sortino_above_2(self):
        """sortino > 2.0 -> 90.0."""
        self.assertEqual(score_sortino_from_ratio(3.0), 90.0)

    def test_sortino_between_1_5_and_2(self):
        """1.5 < sortino <= 2.0 -> 80.0."""
        self.assertEqual(score_sortino_from_ratio(1.8), 80.0)

    def test_sortino_between_1_and_1_5(self):
        """1.0 < sortino <= 1.5 -> 70.0."""
        self.assertEqual(score_sortino_from_ratio(1.25), 70.0)

    def test_sortino_between_0_5_and_1(self):
        """0.5 < sortino <= 1.0 -> 60.0."""
        self.assertEqual(score_sortino_from_ratio(0.75), 60.0)

    def test_sortino_between_0_and_0_5(self):
        """0.0 < sortino <= 0.5 -> 50.0."""
        self.assertEqual(score_sortino_from_ratio(0.25), 50.0)

    def test_sortino_zero_or_negative(self):
        """sortino <= 0.0 -> 40.0."""
        for v in [0.0, -0.1, -2.0]:
            self.assertEqual(score_sortino_from_ratio(v), 40.0, f"sortino={v}")


class TestScoreDrawdown(TestCase):
    """score_drawdown(dd: float) -> 0-100 score (lower drawdown = higher score)."""

    def test_drawdown_very_low(self):
        """dd < 10 -> 90.0."""
        for v in [0, 5, 9.9]:
            self.assertEqual(score_drawdown(v), 90.0, f"dd={v}")

    def test_drawdown_low(self):
        """10 <= dd < 15 -> 80.0."""
        for v in [10, 12, 14.9]:
            self.assertEqual(score_drawdown(v), 80.0, f"dd={v}")

    def test_drawdown_medium(self):
        """15 <= dd < 20 -> 70.0."""
        for v in [15, 17, 19.9]:
            self.assertEqual(score_drawdown(v), 70.0, f"dd={v}")

    def test_drawdown_medium_high(self):
        """20 <= dd < 25 -> 60.0."""
        for v in [20, 22, 24.9]:
            self.assertEqual(score_drawdown(v), 60.0, f"dd={v}")

    def test_drawdown_high(self):
        """25 <= dd < 30 -> 50.0."""
        for v in [25, 27, 29.9]:
            self.assertEqual(score_drawdown(v), 50.0, f"dd={v}")

    def test_drawdown_very_high(self):
        """dd >= 30 -> 40.0."""
        for v in [30, 35, 50]:
            self.assertEqual(score_drawdown(v), 40.0, f"dd={v}")


class TestScoreVolatility(TestCase):
    """score_volatility(vol: float) -> 0-100 score (lower vol = higher score)."""

    def test_vol_low(self):
        """vol < 10 -> 80.0."""
        for v in [0, 5, 9.9]:
            self.assertEqual(score_volatility(v), 80.0, f"vol={v}")

    def test_vol_medium_low(self):
        """10 <= vol < 15 -> 70.0."""
        for v in [10, 12, 14.9]:
            self.assertEqual(score_volatility(v), 70.0, f"vol={v}")

    def test_vol_medium(self):
        """15 <= vol < 20 -> 60.0."""
        for v in [15, 17, 19.9]:
            self.assertEqual(score_volatility(v), 60.0, f"vol={v}")

    def test_vol_medium_high(self):
        """20 <= vol < 25 -> 50.0."""
        for v in [20, 22, 24.9]:
            self.assertEqual(score_volatility(v), 50.0, f"vol={v}")

    def test_vol_high(self):
        """vol >= 25 -> 40.0."""
        for v in [25, 30, 50]:
            self.assertEqual(score_volatility(v), 40.0, f"vol={v}")


class TestScoreAlpha(TestCase):
    """score_alpha(alpha: float) -> 0-100 score."""

    def test_alpha_very_high(self):
        """alpha > 0.15 -> 90.0."""
        for v in [0.16, 0.5, 1.0]:
            self.assertEqual(score_alpha(v), 90.0, f"alpha={v}")

    def test_alpha_high(self):
        """0.08 < alpha <= 0.15 -> 80.0."""
        for v in [0.09, 0.12, 0.15]:
            self.assertEqual(score_alpha(v), 80.0, f"alpha={v}")

    def test_alpha_medium(self):
        """0.03 < alpha <= 0.08 -> 70.0."""
        for v in [0.04, 0.06, 0.08]:
            self.assertEqual(score_alpha(v), 70.0, f"alpha={v}")

    def test_alpha_positive_low(self):
        """0.0 < alpha <= 0.03 -> 60.0."""
        for v in [0.01, 0.02, 0.03]:
            self.assertEqual(score_alpha(v), 60.0, f"alpha={v}")

    def test_alpha_slightly_negative(self):
        """-0.05 < alpha <= 0.0 -> 50.0."""
        for v in [-0.01, -0.03, 0.0]:
            self.assertEqual(score_alpha(v), 50.0, f"alpha={v}")

    def test_alpha_very_negative(self):
        """alpha <= -0.05 -> 40.0."""
        for v in [-0.05, -0.1, -1.0]:
            self.assertEqual(score_alpha(v), 40.0, f"alpha={v}")


# ====================================================================
# Regime weights and confidence
# ====================================================================

class TestRegimeWeights(TestCase):
    """regime_weights(regime, metrics) -> dict of metric->weight."""

    def test_default_regime_weights(self):
        """Normal regime -> standard base weights."""
        metrics = {"sharpe": 70, "sortino": 65, "alpha": 55}
        result = regime_weights("normal", metrics)
        self.assertAlmostEqual(result["sharpe"], 0.25)
        self.assertAlmostEqual(result["sortino"], 0.20)
        self.assertAlmostEqual(result["alpha"], 0.15)

    def test_high_volatility_weights(self):
        """High volatility regime -> higher drawdown/vol weights."""
        metrics = {"sharpe": 70, "max_drawdown": 60, "volatility": 65, "hhi": 50}
        result = regime_weights("high_volatility", metrics)
        self.assertAlmostEqual(result["max_drawdown"], 0.25)
        self.assertAlmostEqual(result["volatility"], 0.25)
        self.assertAlmostEqual(result["sharpe"], 0.15)

    def test_crisis_weights(self):
        """Crisis regime -> highest drawdown/vol weights."""
        metrics = {"sharpe": 70, "sortino": 65, "max_drawdown": 60, "volatility": 65, "hhi": 50}
        result = regime_weights("crisis", metrics)
        self.assertAlmostEqual(result["max_drawdown"], 0.30)
        self.assertAlmostEqual(result["volatility"], 0.30)
        self.assertAlmostEqual(result["hhi"], 0.15)
        self.assertAlmostEqual(result["sharpe"], 0.10)

    def test_regime_weights_filters_unavailable_metrics(self):
        """Only metrics present in the dict are included."""
        metrics = {"sharpe": 70, "volatility": 65}
        result = regime_weights("normal", metrics)
        expected_keys = {"sharpe", "volatility"}
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertNotIn("sortino", result)
        self.assertNotIn("alpha", result)

    def test_regime_weights_empty_metrics(self):
        """Empty metrics -> empty dict."""
        result = regime_weights("normal", {})
        self.assertEqual(result, {})

    def test_regime_weights_with_enum_value(self):
        """Regime as object with .value attribute."""
        class FakeRegime:
            value = "crisis"
        result = regime_weights(FakeRegime(), {"sharpe": 70, "max_drawdown": 60})
        self.assertAlmostEqual(result["max_drawdown"], 0.30)


class TestComputeConfidence(TestCase):
    """compute_confidence(completeness, metrics) -> float."""

    def test_confidence_a_complete(self):
        """A completeness, all metrics != 50 -> high confidence."""
        metrics = {"sharpe": 80, "sortino": 75, "alpha": 70}
        result = compute_confidence("A", metrics)
        self.assertEqual(result, 0.92)

    def test_confidence_d_incomplete(self):
        """D completeness, all metrics = 50 -> low confidence."""
        metrics = {"sharpe": 50, "sortino": 50}
        result = compute_confidence("D", metrics)
        self.assertEqual(result, 0.12)

    def test_confidence_partial_coverage(self):
        """B completeness, half metrics computed -> moderate confidence."""
        metrics = {"sharpe": 80, "sortino": 50, "alpha": 50, "max_drawdown": 70}
        result = compute_confidence("B", metrics)
        self.assertEqual(result, 0.61)

    def test_confidence_unknown_completeness(self):
        """Unknown completeness -> base=0.50."""
        result = compute_confidence("X", {"sharpe": 80})
        self.assertEqual(result, 0.50)

    def test_confidence_single_metric(self):
        """Single metric dict works correctly."""
        metrics = {"sharpe": 80}
        result = compute_confidence("A", metrics)
        self.assertEqual(result, 0.92)


class TestScoreLevel(TestCase):
    """score_level(composite) -> Literal["green", "yellow", "orange", "red"]."""

    def test_green(self):
        """>= 75 -> green."""
        for v in [75, 80, 100]:
            self.assertEqual(score_level(v), "green", f"composite={v}")

    def test_yellow(self):
        """50 <= composite < 75 -> yellow."""
        for v in [50, 60, 74]:
            self.assertEqual(score_level(v), "yellow", f"composite={v}")

    def test_orange(self):
        """30 <= composite < 50 -> orange."""
        for v in [30, 40, 49]:
            self.assertEqual(score_level(v), "orange", f"composite={v}")

    def test_red(self):
        """< 30 -> red."""
        for v in [0, 20, 29]:
            self.assertEqual(score_level(v), "red", f"composite={v}")

    def test_level_boundaries(self):
        """Exactly at boundary thresholds."""
        self.assertEqual(score_level(75), "green")
        self.assertEqual(score_level(74), "yellow")
        self.assertEqual(score_level(50), "yellow")
        self.assertEqual(score_level(49), "orange")
        self.assertEqual(score_level(30), "orange")
        self.assertEqual(score_level(29), "red")


class TestAssessCompleteness(TestCase):
    """assess_completeness(basic, perf, nav, holdings, sectors) -> str."""

    def test_completeness_a(self):
        """All data present -> A."""
        result = assess_completeness(
            basic={"name": "Test Fund"},
            perf={"return": 10.0},
            nav=pd.DataFrame({"日增长率": [0.1] * 100}),
            holdings=pd.DataFrame({"占净值比例": ["5%"]}),
            sectors=pd.DataFrame({"行业": ["金融"]}),
        )
        self.assertEqual(result, "A")

    def test_completeness_b_with_perf(self):
        """Basic + nav + perf, no holdings/sectors -> B."""
        result = assess_completeness(
            basic={"name": "Test Fund"},
            perf={"return": 10.0},
            nav=pd.DataFrame({"日增长率": [0.1] * 100}),
            holdings=pd.DataFrame(),
            sectors=None,
        )
        self.assertEqual(result, "B")

    def test_completeness_c(self):
        """Basic + nav only (no perf, no holdings/sectors) -> C."""
        result = assess_completeness(
            basic={"name": "Test Fund"},
            perf=None,
            nav=pd.DataFrame({"日增长率": [0.1] * 100}),
            holdings=pd.DataFrame(),
            sectors=None,
        )
        self.assertEqual(result, "C")

    def test_completeness_d_no_basic(self):
        """No basic data -> D."""
        result = assess_completeness(
            basic=None,
            perf=None,
            nav=pd.DataFrame({"日增长率": [0.1] * 100}),
            holdings=None,
            sectors=None,
        )
        self.assertEqual(result, "D")

    def test_completeness_d_no_nav(self):
        """No NAV or too short NAV -> D."""
        result = assess_completeness(
            basic={"name": "Test Fund"},
            perf=None,
            nav=pd.DataFrame(),
            holdings=None,
            sectors=None,
        )
        self.assertEqual(result, "D")

    def test_completeness_d_short_nav(self):
        """NAV with <= 30 records -> D."""
        result = assess_completeness(
            basic={"name": "Test Fund"},
            perf=None,
            nav=pd.DataFrame({"日增长率": [0.1] * 20}),
            holdings=None,
            sectors=None,
        )
        self.assertEqual(result, "D")

    def test_completeness_b_with_holdings(self):
        """Basic + nav + holdings/sectors (no perf) -> B (enhanced_ok path)."""
        result = assess_completeness(
            basic={"name": "Test Fund"},
            perf=None,
            nav=pd.DataFrame({"日增长率": [0.1] * 100}),
            holdings=pd.DataFrame({"占净值比例": ["5%"]}),
            sectors=pd.DataFrame({"行业": ["金融"]}),
        )
        self.assertEqual(result, "B")

    def test_completeness_basic_with_error(self):
        """Basic has 'error' key -> D (not considered valid)."""
        result = assess_completeness(
            basic={"error": "not found"},
            perf=None,
            nav=pd.DataFrame({"日增长率": [0.1] * 100}),
            holdings=None,
            sectors=None,
        )
        self.assertEqual(result, "D")


# ====================================================================
# Calendar date utilities (src.tools.calendar.dates)
# ====================================================================

class TestIsBusinessDay(TestCase):
    """is_business_day(d: date) -> bool."""

    def test_monday_is_business_day(self):
        """Monday -> True."""
        d = date(2024, 1, 8)
        self.assertTrue(is_business_day(d))

    def test_friday_is_business_day(self):
        """Friday -> True."""
        d = date(2024, 1, 12)
        self.assertTrue(is_business_day(d))

    def test_saturday_is_not_business_day(self):
        """Saturday -> False."""
        d = date(2024, 1, 13)
        self.assertFalse(is_business_day(d))

    def test_sunday_is_not_business_day(self):
        """Sunday -> False."""
        d = date(2024, 1, 14)
        self.assertFalse(is_business_day(d))

    def test_wednesday_is_business_day(self):
        """Wednesday -> True."""
        d = date(2024, 1, 10)
        self.assertTrue(is_business_day(d))


class TestNextBusinessDay(TestCase):
    """next_business_day(d: date) -> date."""

    def test_friday_to_monday(self):
        """Friday -> next Monday (skip weekend)."""
        d = date(2024, 1, 12)
        result = next_business_day(d)
        self.assertEqual(result, date(2024, 1, 15))

    def test_saturday_to_monday(self):
        """Saturday -> next Monday."""
        d = date(2024, 1, 13)
        result = next_business_day(d)
        self.assertEqual(result, date(2024, 1, 15))

    def test_sunday_to_monday(self):
        """Sunday -> next Monday."""
        d = date(2024, 1, 14)
        result = next_business_day(d)
        self.assertEqual(result, date(2024, 1, 15))

    def test_thursday_to_friday(self):
        """Thursday -> Friday (no weekend skip)."""
        d = date(2024, 1, 11)
        result = next_business_day(d)
        self.assertEqual(result, date(2024, 1, 12))

    def test_monday_to_tuesday(self):
        """Monday -> Tuesday (no weekend skip)."""
        d = date(2024, 1, 8)
        result = next_business_day(d)
        self.assertEqual(result, date(2024, 1, 9))


class TestNextDcaDate(TestCase):
    """next_dca_date(current, frequency, day_of_week) -> date."""

    def test_daily_dca(self):
        """Daily: next day, skipping weekend."""
        d = date(2024, 1, 12)
        result = next_dca_date(d, "daily")
        self.assertEqual(result, date(2024, 1, 15))

    def test_daily_midweek(self):
        """Daily midweek: next day is business day."""
        d = date(2024, 1, 9)
        result = next_dca_date(d, "daily")
        self.assertEqual(result, date(2024, 1, 10))

    def test_weekly_monday(self):
        """Weekly on Monday."""
        d = date(2024, 1, 8)
        result = next_dca_date(d, "weekly", day_of_week="mon")
        self.assertEqual(result, date(2024, 1, 15))

    def test_weekly_friday(self):
        """Weekly on Friday."""
        d = date(2024, 1, 8)
        result = next_dca_date(d, "weekly", day_of_week="fri")
        self.assertEqual(result, date(2024, 1, 19))

    def test_weekly_no_day(self):
        """Weekly without day_of_week: +7 days from current."""
        d = date(2024, 1, 8)
        result = next_dca_date(d, "weekly")
        self.assertEqual(result, date(2024, 1, 15))

    def test_biweekly(self):
        """Biweekly: +14 days."""
        d = date(2024, 1, 8)
        result = next_dca_date(d, "biweekly")
        self.assertEqual(result, date(2024, 1, 22))

    def test_biweekly_landing_on_weekend(self):
        """Biweekly landing on Saturday -> move to Monday."""
        d = date(2024, 1, 12)
        result = next_dca_date(d, "biweekly")
        self.assertEqual(result, date(2024, 1, 26))

    def test_monthly(self):
        """Monthly: +30 days."""
        d = date(2024, 1, 15)
        result = next_dca_date(d, "monthly")
        self.assertEqual(result, date(2024, 2, 14))

    def test_monthly_landing_on_weekend(self):
        """Monthly landing on Sunday -> move to Monday."""
        d = date(2023, 12, 15)
        result = next_dca_date(d, "monthly")
        self.assertEqual(result, date(2024, 1, 15))

    def test_unknown_frequency(self):
        """Unknown frequency -> +7 days (default)."""
        d = date(2024, 1, 8)
        result = next_dca_date(d, "fortnightly")
        self.assertEqual(result, date(2024, 1, 15))


class TestToDate(TestCase):
    """to_date(d) -> Optional[date]."""

    def test_to_date_from_date(self):
        """date input -> same date."""
        d = date(2024, 1, 15)
        result = to_date(d)
        self.assertEqual(result, d)
        self.assertIsInstance(result, date)

    def test_to_date_from_datetime(self):
        """datetime input -> returns datetime as-is (isinstance check)."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = to_date(dt)
        self.assertEqual(result, dt)
        self.assertIsInstance(result, datetime)

    def test_to_date_from_iso_string(self):
        """ISO string -> date."""
        result = to_date("2024-01-15")
        self.assertEqual(result, date(2024, 1, 15))

    def test_to_date_from_string_with_time(self):
        """String with time portion -> date (truncated)."""
        result = to_date("2024-01-15T10:30:00")
        self.assertEqual(result, date(2024, 1, 15))

    def test_to_date_none(self):
        """None -> None."""
        result = to_date(None)
        self.assertIsNone(result)

    def test_to_date_invalid_string(self):
        """Unparseable string -> None."""
        result = to_date("not-a-date")
        self.assertIsNone(result)

    def test_to_date_empty_string(self):
        """Empty string -> None."""
        result = to_date("")
        self.assertIsNone(result)


if __name__ == "__main__":
    main()
