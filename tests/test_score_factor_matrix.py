import unittest
from datetime import date, timedelta

import pandas as pd

from src.analysis.scorer import FundAnalyzer


def _loaded_analyzer(completeness="A"):
    analyzer = FundAnalyzer()
    start = date(2025, 1, 1)
    analyzer.funds["000001"] = {
        "basic": {"name": "测试混合基金", "fund_type": "混合型", "manager": "张三"},
        "perf": {
            "近1年": {"sharpe_ratio": 1.2, "annual_volatility": 12.0},
            "近3年": {"sharpe_ratio": 1.1, "max_drawdown": 18.0},
        },
        "nav": pd.DataFrame(
            {"单位净值": [1 + i * 0.001 for i in range(260)], "日增长率": [0.1 for _ in range(260)]},
            index=[start + timedelta(days=i) for i in range(260)],
        ),
        "holdings": pd.DataFrame([{"股票名称": "寒武纪", "占净值比例": "8.2%"}]),
        "sectors": pd.DataFrame([{"行业": "半导体", "占比": "35%"}]),
        "holders": pd.DataFrame(),
        "completeness": completeness,
    }
    return analyzer


class ScoreFactorMatrixTest(unittest.TestCase):
    def test_score_contains_factor_matrix_and_confidence(self):
        score = _loaded_analyzer().score_fund("000001")

        self.assertIn("score_confidence", score)
        self.assertGreater(score["score_confidence"], 0.85)
        for dimension in ["macro", "meso", "micro"]:
            self.assertIn(dimension, score["factor_matrix"])
            self.assertGreater(len(score["factor_matrix"][dimension]), 0)
            for factor in score["factor_matrix"][dimension]:
                self.assertIn("value", factor)
                self.assertIn("score", factor)
                self.assertIn("weight", factor)
                self.assertIn("source", factor)
                self.assertIn("missing_policy", factor)

    def test_lower_completeness_reduces_confidence(self):
        high = _loaded_analyzer("A").score_fund("000001")
        low = _loaded_analyzer("C").score_fund("000001")

        self.assertLess(low["score_confidence"], high["score_confidence"])
        self.assertLessEqual(low["score_confidence"], 0.7)


if __name__ == "__main__":
    unittest.main()
