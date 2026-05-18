import unittest

from src.recommend.engine import (
    compute_fund_similarity,
    filter_by_correlation,
    rank_recommendations,
)


class RecommendEngineTest(unittest.TestCase):
    def test_similarity_uses_theme_style_and_return_risk(self):
        target = {
            "name": "华宝纳斯达克精选股票(QDII)A",
            "type": "QDII",
            "theme": "美股科技",
            "style_tags": ["growth", "overseas"],
            "return_3m": 8.0,
            "annual_volatility": 22.0,
            "max_drawdown": -18.0,
        }
        similar = {
            "name": "纳斯达克科技指数(QDII)",
            "type": "QDII",
            "theme": "美股科技",
            "style_tags": ["growth", "overseas"],
            "return_3m": 7.0,
            "annual_volatility": 23.0,
            "max_drawdown": -19.0,
        }
        different = {
            "name": "中短债债券基金",
            "type": "债券型",
            "theme": "债券固收",
            "style_tags": ["defensive"],
            "return_3m": 1.0,
            "annual_volatility": 3.0,
            "max_drawdown": -2.0,
        }

        self.assertGreater(
            compute_fund_similarity(target, similar)["composite"],
            compute_fund_similarity(target, different)["composite"],
        )


    def test_filter_by_correlation_excludes_holdings_and_near_duplicates(self):
        holdings = [{
            "code": "017436",
            "name": "华宝纳斯达克精选股票(QDII)A",
            "type": "QDII",
            "theme": "美股科技",
            "style_tags": ["growth", "overseas"],
            "return_3m": 8.0,
        }]
        candidates = [
            {"code": "017436", "name": "已持有基金", "theme": "美股科技", "style_tags": ["growth", "overseas"]},
            {"code": "123456", "name": "纳斯达克科技指数", "theme": "美股科技", "style_tags": ["growth", "overseas"], "return_3m": 8.0},
            {"code": "654321", "name": "新能源车电池", "theme": "新能源", "style_tags": ["growth"], "return_3m": 5.0},
        ]

        filtered = filter_by_correlation(candidates, {"017436"}, holdings, max_similarity=0.90)

        self.assertEqual([c["code"] for c in filtered], ["654321"])
        self.assertGreater(filtered[0]["max_similarity"], 0)


    def test_rank_recommendations_limits_same_theme_when_alternatives_exist(self):
        candidates = []
        for idx in range(5):
            candidates.append({
                "code": f"10000{idx}",
                "name": f"科技基金{idx}",
                "theme": "美股科技",
                "return_1m": 10 - idx,
                "return_3m": 15 - idx,
                "return_6m": 20 - idx,
                "max_similarity": 0.2,
            })
        for idx, theme in enumerate(["新能源", "医药医疗", "能源商品"]):
            candidates.append({
                "code": f"20000{idx}",
                "name": f"{theme}基金",
                "theme": theme,
                "return_1m": 3,
                "return_3m": 5,
                "return_6m": 8,
                "max_similarity": 0.3,
            })

        ranked = rank_recommendations(candidates, {"科技": 1.0}, top_n=5, max_theme_ratio=0.40)

        self.assertEqual(len(ranked), 5)
        self.assertLessEqual(sum(1 for c in ranked if c["theme"] == "美股科技"), 2)


if __name__ == "__main__":
    unittest.main()
