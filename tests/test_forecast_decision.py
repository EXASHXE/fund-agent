import unittest

from src.forecast.engine import build_trend_matrix


class ForecastDecisionTest(unittest.TestCase):
    def test_trend_matrix_uses_news_catalyst_and_score_delta(self):
        score = {
            "fund_code": "000001",
            "composite_score": 72,
            "score_delta": 8,
            "data_completeness": "A",
            "feature_matrix": {"sortino_ratio": 1.4, "annual_volatility": 18},
        }
        news_context = {
            "brief": {"trend": "bullish", "weighted_catalyst_score": 0.28},
            "news_evaluation": {"quality_score": 0.8},
        }

        trend = build_trend_matrix(score, news_context)

        self.assertEqual(trend["short_term"]["direction"], "up")
        self.assertGreaterEqual(trend["short_term"]["score"], 0.65)
        self.assertGreater(trend["short_term"]["confidence"], 0.7)
        self.assertTrue(any("新闻催化" in driver for driver in trend["drivers"]))


if __name__ == "__main__":
    unittest.main()
