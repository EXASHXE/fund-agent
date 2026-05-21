import unittest

from src.recommend.engine import (
    compute_fund_similarity,
    filter_by_correlation,
    infer_exposure_cluster,
    rank_recommendations,
    rank_recommendations_with_portfolio,
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


    def test_rank_recommendations_limits_growth_manufacturing_cluster(self):
        growth_candidates = [
            {
                "code": f"30000{idx}",
                "name": name,
                "theme": theme,
                "return_1m": 12 - idx,
                "return_3m": 18 - idx,
                "return_6m": 25 - idx,
                "max_similarity": 0.1,
            }
            for idx, (name, theme) in enumerate([
                ("半导体芯片基金", "半导体"),
                ("新能源电池基金", "新能源"),
                ("人工智能科技基金", "美股科技"),
                ("光伏储能基金", "新能源"),
            ])
        ]
        diversifiers = [
            {"code": "400001", "name": "中短债债券基金", "theme": "债券固收", "return_1m": 2, "return_3m": 3, "return_6m": 5, "max_similarity": 0.1},
            {"code": "400002", "name": "红利低波基金", "theme": "红利价值", "return_1m": 2, "return_3m": 4, "return_6m": 6, "max_similarity": 0.1},
            {"code": "400003", "name": "黄金商品基金", "theme": "能源商品", "return_1m": 1, "return_3m": 3, "return_6m": 4, "max_similarity": 0.1},
        ]

        ranked = rank_recommendations(growth_candidates + diversifiers, {"半导体": 1.0}, top_n=5)

        growth_count = sum(1 for c in ranked if infer_exposure_cluster(c) == "growth_manufacturing")
        self.assertLessEqual(growth_count, 2)
        self.assertTrue(any(c.get("portfolio_role") for c in ranked))

    def test_rank_recommendations_with_portfolio_prefers_defensive_gap(self):
        candidates = [
            {"code": "100001", "name": "半导体芯片基金", "theme": "半导体", "return_1m": 8, "return_3m": 12, "return_6m": 20, "max_similarity": 0.2},
            {"code": "200001", "name": "中短债债券基金", "theme": "债券固收", "return_1m": 1, "return_3m": 2, "return_6m": 4, "max_similarity": 0.1},
        ]
        portfolio_risk = {
            "cluster_exposures": {"growth_manufacturing": 0.75, "defensive_income": 0.0},
            "warnings": ["成长制造暴露过高"],
        }

        ranked = rank_recommendations_with_portfolio(candidates, {}, portfolio_risk, top_n=2)

        self.assertEqual(ranked[0]["code"], "200001")
        self.assertEqual(ranked[0]["entry_plan"], "分批买入")
        self.assertIn("risk_budget_impact", ranked[0])


if __name__ == "__main__":
    unittest.main()
