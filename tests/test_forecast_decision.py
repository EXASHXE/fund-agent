import unittest

from src.decision.engine import build_operation_advice
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

    def test_operation_advice_adds_when_high_score_uptrend_and_underweight(self):
        score = {"fund_code": "000001", "composite_score": 76, "data_completeness": "A"}
        trend = {"short_term": {"direction": "up", "score": 0.72, "confidence": 0.8}}
        position = {
            "current_weight": 0.08,
            "current_value": 800,
            "total_value": 10000,
            "pending_amount": 0,
            "is_qdii": False,
            "dca_enabled": True,
        }

        advice = build_operation_advice(score, trend, position)

        self.assertEqual(advice["action"], "buy")
        self.assertGreater(advice["adjust_amount"], 0)
        self.assertGreater(advice["target_weight"], position["current_weight"])

    def test_operation_advice_waits_when_qdii_pending_is_high(self):
        score = {"fund_code": "017436", "composite_score": 78, "data_completeness": "A"}
        trend = {"short_term": {"direction": "up", "score": 0.72, "confidence": 0.8}}
        position = {
            "current_weight": 0.12,
            "current_value": 1200,
            "total_value": 10000,
            "pending_amount": 1000,
            "is_qdii": True,
            "dca_enabled": True,
        }

        advice = build_operation_advice(score, trend, position)

        self.assertEqual(advice["action"], "hold_wait")
        self.assertEqual(advice["adjust_amount"], 0)
        self.assertTrue(any("pending" in trigger.lower() for trigger in advice["triggers"]))


if __name__ == "__main__":
    unittest.main()
