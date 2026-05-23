import unittest

from src.news.evaluator import evaluate_news_result, filter_relevant_catalysts


class NewsEvaluatorTest(unittest.TestCase):
    def test_evaluate_news_result_scores_relevance_freshness_and_negative_density(self):
        news_item = {
            "news_list": [
                {"source": "财联社", "date": "2026-05-22"},
                {"source": "财新", "date": "2026-05-21"},
                {"source": "财联社", "date": "2026-05-16"},
            ],
            "catalyst_news": [
                {"catalyst": {"relevance": 0.8, "weighted_score": 0.32}},
                {"catalyst": {"relevance": 0.6, "weighted_score": -0.42}},
                {"catalyst": {"relevance": 0.1, "weighted_score": -0.5}},
            ],
        }

        evaluation = evaluate_news_result(news_item, as_of="2026-05-22")

        self.assertGreater(evaluation["quality_score"], 0.5)
        self.assertEqual(evaluation["relevant_news_count"], 2)
        self.assertEqual(evaluation["high_impact_negative_count"], 1)
        self.assertGreater(evaluation["negative_density"], 0)
        self.assertIn("freshness_score", evaluation)

    def test_filter_relevant_catalysts_removes_low_relevance_items(self):
        catalysts = [
            {"title": "高相关", "catalyst": {"relevance": 0.5}},
            {"title": "低相关", "catalyst": {"relevance": 0.1}},
        ]

        filtered = filter_relevant_catalysts(catalysts, min_relevance=0.2)

        self.assertEqual([item["title"] for item in filtered], ["高相关"])

    def test_evaluate_news_result_computes_overall_score(self):
        news_item = {
            "news_list": [
                {"source": "证券时报", "date": "2026-05-22"},
            ],
            "catalyst_news": [
                {"catalyst": {"relevance": 0.7, "weighted_score": 0.5}},
                {"catalyst": {"relevance": 0.4, "weighted_score": -0.2}},
                {"catalyst": {"relevance": 0.1, "weighted_score": 0.9}},  # low relevance, filtered out
            ],
        }

        evaluation = evaluate_news_result(news_item, as_of="2026-05-22")
        self.assertEqual(evaluation["overall_score"], 0.15)


if __name__ == "__main__":
    unittest.main()
