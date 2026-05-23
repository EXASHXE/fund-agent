import unittest

from src.news.evaluator import evaluate_news_result, filter_relevant_catalysts
from src.news.schemas import EntityProfile


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

    def test_evaluation_warns_when_news_covers_only_one_of_multiple_holdings(self):
        profile = EntityProfile(
            fund_code="378006",
            fund_name="全球新兴市场",
            stock_names=["腾讯", "阿里巴巴", "台积电", "三星电子"],
            holdings=[
                {"stock_name": "腾讯", "weight": 0.08},
                {"stock_name": "阿里巴巴", "weight": 0.07},
                {"stock_name": "台积电", "weight": 0.06},
                {"stock_name": "三星电子", "weight": 0.05},
            ],
        )
        news_item = {
            "news_list": [
                {"title": "腾讯连续回购", "content": "", "source": "财联社", "date": "2026-05-22"},
                {"title": "腾讯再度回购", "content": "", "source": "财联社", "date": "2026-05-21"},
            ],
            "catalyst_news": [],
        }
        evaluation = evaluate_news_result(news_item, as_of="2026-05-22", entity_profile=profile)
        self.assertEqual(evaluation["holding_coverage_count"], 1)
        self.assertIn("覆盖偏窄", evaluation["coverage_warning"])


if __name__ == "__main__":
    unittest.main()
