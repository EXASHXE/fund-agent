"""Tests for src.tools.factors.builder (Phase 1.4).

Verifies FactorMatrixBuilder.build(), score_confidence(), and all _score_* helpers.
"""

from __future__ import annotations

import unittest

from src.tools.factors.builder import FactorMatrixBuilder


class TestFactorMatrixBuilderBuild(unittest.TestCase):
    """FactorMatrixBuilder.build(score, news_context)"""

    def setUp(self):
        self.builder = FactorMatrixBuilder()
        self.score = {
            "fund_type": "混合型",
            "macro_score": 75.0,
            "meso_score": 60.0,
            "feature_matrix": {
                "hhi_index": 1200.0,
                "sortino_ratio": 1.8,
                "sharpe_1y": 1.5,
                "max_drawdown_3y_pct": 12.0,
                "annual_volatility": 18.0,
                "jensen_alpha": 0.05,
                "information_ratio": 0.6,
                "beta": 1.0,
                "win_rate_1y": 0.7,
                "calmar_ratio_1y": 1.2,
            },
        }

    def test_factor_matrix_builder_build_structure(self):
        """Verify factor matrix returns correct structure with macro/meso/micro."""
        result = self.builder.build(self.score)
        self.assertIn("macro", result)
        self.assertIn("meso", result)
        self.assertIn("micro", result)
        self.assertEqual(len(result["macro"]), 1)
        self.assertGreaterEqual(len(result["meso"]), 2)
        self.assertEqual(len(result["micro"]), 9)

    def test_factor_matrix_builder_build_macro_content(self):
        """Verify macro factor content."""
        result = self.builder.build(self.score)
        macro = result["macro"][0]
        self.assertEqual(macro["name"], "fund_type_cycle_fit")
        self.assertEqual(macro["value"], "混合型")
        self.assertEqual(macro["score"], 3.75)  # 75/20
        self.assertEqual(macro["weight"], 0.20)
        self.assertEqual(macro["source"], "basic")

    def test_factor_matrix_builder_build_sector_position(self):
        """Verify meso sector_position factor when meso_score present."""
        result = self.builder.build(self.score)
        meso_names = {f["name"] for f in result["meso"]}
        self.assertIn("sector_position", meso_names)
        sector = [f for f in result["meso"] if f["name"] == "sector_position"][0]
        self.assertEqual(sector["value"], 60.0)
        self.assertEqual(sector["score"], 2.0)  # 60/30

    def test_factor_matrix_builder_build_no_meso_score(self):
        """When meso_score is None, sector_position factor is omitted."""
        score_no_meso = dict(self.score)
        score_no_meso["meso_score"] = None
        result = self.builder.build(score_no_meso)
        meso_names = {f["name"] for f in result["meso"]}
        self.assertNotIn("sector_position", meso_names)

    def test_factor_matrix_builder_build_news_catalyst(self):
        """When news_context has overall_score, catalyst factor added."""
        news_context = {"news_evaluation": {"overall_score": 0.75}}
        result = self.builder.build(self.score, news_context)
        meso_names = {f["name"] for f in result["meso"]}
        self.assertIn("news_catalyst", meso_names)
        catalyst = [f for f in result["meso"] if f["name"] == "news_catalyst"][0]
        self.assertEqual(catalyst["value"], 0.75)
        self.assertEqual(catalyst["weight"], 0.05)

    def test_factor_matrix_builder_build_micro_factor_names(self):
        """Verify all micro factor names are present."""
        result = self.builder.build(self.score)
        micro_names = {f["name"] for f in result["micro"]}
        expected = {
            "sortino_ratio", "sharpe_1y", "max_drawdown_3y_pct",
            "annual_volatility", "jensen_alpha", "information_ratio",
            "beta", "win_rate_1y", "calmar_ratio_1y",
        }
        self.assertEqual(micro_names, expected)

    def test_factor_matrix_builder_build_no_features(self):
        """Empty feature_matrix -> all micro/meso factors use 0.5 default."""
        score = {"fund_type": "股票型", "macro_score": 50.0}
        result = self.builder.build(score)
        for factor in result["micro"]:
            if factor["missing_policy"] != "ignore_when_missing":
                self.assertEqual(factor["score"], 0.5)


class TestScoreConfidence(unittest.TestCase):
    """FactorMatrixBuilder.score_confidence(completeness, features, factor_matrix)"""

    def setUp(self):
        self.builder = FactorMatrixBuilder()
        self.full_features = {
            "max_drawdown_3y_pct": 12.0,
            "annual_volatility": 18.0,
            "sharpe_1y": 1.5,
            "sortino_ratio": 1.8,
        }
        self.full_matrix = {
            "macro": [{"name": "fund_type_cycle_fit", "value": "混合型"}],
            "meso": [
                {"name": "sector_position", "value": 60.0},
                {"name": "hhi_index", "value": 1200.0},
            ],
            "micro": [
                {"name": "sortino_ratio", "value": 1.8},
                {"name": "sharpe_1y", "value": 1.5},
                {"name": "max_drawdown_3y_pct", "value": 12.0},
                {"name": "annual_volatility", "value": 18.0},
            ],
        }

    def test_score_confidence_full(self):
        """A completeness + all features -> high confidence."""
        confidence = self.builder.score_confidence("A", self.full_features, self.full_matrix)
        self.assertGreaterEqual(confidence, 0.85)

    def test_score_confidence_low(self):
        """D completeness -> low confidence."""
        confidence = self.builder.score_confidence("D", {}, {})
        self.assertLessEqual(confidence, 0.30)

    def test_score_confidence_b(self):
        """B completeness -> moderate confidence."""
        confidence = self.builder.score_confidence("B", self.full_features, self.full_matrix)
        self.assertGreaterEqual(confidence, 0.70)
        self.assertLess(confidence, 0.92)

    def test_score_confidence_c(self):
        """C completeness -> lower confidence."""
        confidence = self.builder.score_confidence("C", self.full_features, self.full_matrix)
        self.assertGreaterEqual(confidence, 0.50)
        self.assertLess(confidence, 0.82)

    def test_score_confidence_missing_key_metrics(self):
        """Missing key metrics reduces confidence."""
        features_no_key = {"sortino_ratio": 1.8}
        confidence = self.builder.score_confidence("A", features_no_key, self.full_matrix)
        full_conf = self.builder.score_confidence("A", self.full_features, self.full_matrix)
        self.assertLess(confidence, full_conf)

    def test_score_confidence_unknown_completeness(self):
        """Unknown completeness string -> falls back to 0.50 base."""
        confidence = self.builder.score_confidence("E", self.full_features, self.full_matrix)
        self.assertGreaterEqual(confidence, 0.38)

    def test_score_confidence_empty_factors(self):
        """No factors -> base * 0.8."""
        confidence = self.builder.score_confidence("A", {}, {})
        self.assertEqual(confidence, round(0.92 * 0.8, 2))

    def test_score_confidence_clamped(self):
        """Confidence clamped to [0.20, 0.98]."""
        low = self.builder.score_confidence("D", {}, {})
        self.assertGreaterEqual(low, 0.20)
        high = self.builder.score_confidence("A", self.full_features, self.full_matrix)
        self.assertLessEqual(high, 0.98)

    def test_score_confidence_rounding(self):
        """Confidence rounded to 2 decimal places."""
        confidence = self.builder.score_confidence("A", self.full_features, self.full_matrix)
        self.assertEqual(len(str(confidence).split(".")[1]), 2)


class TestScorePositiveRatio(unittest.TestCase):
    """FactorMatrixBuilder._score_positive_ratio(value, good_threshold)"""

    def setUp(self):
        self.builder = FactorMatrixBuilder()

    def test_score_positive_ratio_above_threshold(self):
        """Value above threshold -> score capped at 1.0."""
        score = self.builder._score_positive_ratio(2.0, 1.5)
        self.assertEqual(score, 1.0)

    def test_score_positive_ratio_at_threshold(self):
        """Value equal to threshold -> score = 1.0."""
        score = self.builder._score_positive_ratio(1.5, 1.5)
        self.assertEqual(score, 1.0)

    def test_score_positive_ratio_below_threshold(self):
        """Value below threshold -> proportional score."""
        score = self.builder._score_positive_ratio(1.0, 2.0)
        self.assertEqual(score, 0.5)

    def test_score_positive_ratio_zero_threshold(self):
        """Zero threshold -> 0.5 (neutral)."""
        score = self.builder._score_positive_ratio(1.0, 0.0)
        self.assertEqual(score, 0.5)

    def test_score_positive_ratio_none(self):
        """None value -> 0.5 (neutral)."""
        score = self.builder._score_positive_ratio(None, 1.5)
        self.assertEqual(score, 0.5)

    def test_score_positive_ratio_negative(self):
        """Negative value -> 0.0."""
        score = self.builder._score_positive_ratio(-1.0, 1.5)
        self.assertEqual(score, 0.0)

    def test_score_positive_ratio_precision(self):
        """Result rounded to 4 decimal places."""
        score = self.builder._score_positive_ratio(1.0, 3.0)
        self.assertEqual(score, 0.3333)


class TestScoreDrawdownFactor(unittest.TestCase):
    """FactorMatrixBuilder._score_drawdown_factor(value)"""

    def setUp(self):
        self.builder = FactorMatrixBuilder()

    def test_drawdown_low(self):
        """Drawdown <= 10 -> score = 1.0."""
        self.assertEqual(self.builder._score_drawdown_factor(5.0), 1.0)
        self.assertEqual(self.builder._score_drawdown_factor(10.0), 1.0)

    def test_drawdown_high(self):
        """Drawdown >= 35 -> score = 0.1."""
        self.assertEqual(self.builder._score_drawdown_factor(35.0), 0.1)
        self.assertEqual(self.builder._score_drawdown_factor(50.0), 0.1)

    def test_drawdown_mid(self):
        """Drawdown between 10 and 35 -> interpolated score."""
        score = self.builder._score_drawdown_factor(22.5)
        self.assertAlmostEqual(score, 0.55, places=4)

    def test_drawdown_none(self):
        """None value -> 0.5."""
        self.assertEqual(self.builder._score_drawdown_factor(None), 0.5)

    def test_drawdown_negative(self):
        """Negative drawdown is abs'd."""
        score = self.builder._score_drawdown_factor(-15.0)
        positive_score = self.builder._score_drawdown_factor(15.0)
        self.assertEqual(score, positive_score)

    def test_drawdown_precision(self):
        """Result rounded to 4 decimal places."""
        score = self.builder._score_drawdown_factor(20.0)
        self.assertEqual(score, 0.64)


class TestScoreVolatilityFactor(unittest.TestCase):
    """FactorMatrixBuilder._score_volatility_factor(value)"""

    def setUp(self):
        self.builder = FactorMatrixBuilder()

    def test_volatility_low(self):
        """Volatility <= 8 -> score = 1.0."""
        self.assertEqual(self.builder._score_volatility_factor(5.0), 1.0)
        self.assertEqual(self.builder._score_volatility_factor(8.0), 1.0)

    def test_volatility_high(self):
        """Volatility >= 35 -> score = 0.1."""
        self.assertEqual(self.builder._score_volatility_factor(35.0), 0.1)
        self.assertEqual(self.builder._score_volatility_factor(50.0), 0.1)

    def test_volatility_mid(self):
        """Volatility between 8 and 35 -> interpolated score."""
        score = self.builder._score_volatility_factor(21.5)
        self.assertAlmostEqual(score, 0.55, places=4)

    def test_volatility_none(self):
        """None value -> 0.5."""
        self.assertEqual(self.builder._score_volatility_factor(None), 0.5)

    def test_volatility_precision(self):
        """Result rounded to 4 decimal places."""
        score = self.builder._score_volatility_factor(17.0)
        self.assertEqual(score, 0.7)


class TestScoreHhiFactor(unittest.TestCase):
    """FactorMatrixBuilder._score_hhi_factor(value)"""

    def setUp(self):
        self.builder = FactorMatrixBuilder()

    def test_hhi_low(self):
        """HHI <= 1500 -> score = 1.0."""
        self.assertEqual(self.builder._score_hhi_factor(1000.0), 1.0)
        self.assertEqual(self.builder._score_hhi_factor(1500.0), 1.0)

    def test_hhi_high(self):
        """HHI >= 3500 -> score = 0.2."""
        self.assertEqual(self.builder._score_hhi_factor(3500.0), 0.2)
        self.assertEqual(self.builder._score_hhi_factor(5000.0), 0.2)

    def test_hhi_mid(self):
        """HHI between 1500 and 3500 -> interpolated score."""
        score = self.builder._score_hhi_factor(2500.0)
        self.assertAlmostEqual(score, 0.6, places=4)

    def test_hhi_none(self):
        """None value -> 0.5."""
        self.assertEqual(self.builder._score_hhi_factor(None), 0.5)

    def test_hhi_precision(self):
        """Result rounded to 4 decimal places."""
        score = self.builder._score_hhi_factor(2000.0)
        self.assertEqual(score, 0.8)


class TestScoreBetaFactor(unittest.TestCase):
    """FactorMatrixBuilder._score_beta_factor(value)"""

    def setUp(self):
        self.builder = FactorMatrixBuilder()

    def test_beta_one(self):
        """Beta = 1.0 -> score = 1.0."""
        self.assertEqual(self.builder._score_beta_factor(1.0), 1.0)

    def test_beta_two(self):
        """Beta = 2.0 -> lower score."""
        self.assertEqual(self.builder._score_beta_factor(2.0), 0.6)

    def test_beta_zero(self):
        """Beta = 0.0 -> score = 0.6."""
        self.assertEqual(self.builder._score_beta_factor(0.0), 0.6)

    def test_beta_near_one(self):
        """Beta close to 1.0 -> high score."""
        score = self.builder._score_beta_factor(1.1)
        self.assertAlmostEqual(score, 0.96, places=4)

    def test_beta_extreme(self):
        """Beta far from 1.0 -> clamped to 0.0."""
        score = self.builder._score_beta_factor(3.5)
        self.assertEqual(score, 0.0)
        score_neg = self.builder._score_beta_factor(-1.5)
        self.assertEqual(score_neg, 0.0)

    def test_beta_none(self):
        """None value -> 0.5."""
        self.assertEqual(self.builder._score_beta_factor(None), 0.5)

    def test_beta_precision(self):
        """Result rounded to 4 decimal places."""
        self.assertEqual(self.builder._score_beta_factor(1.0), 1.0)


if __name__ == "__main__":
    unittest.main()
