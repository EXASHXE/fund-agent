import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.news.pipeline import run_news_pipeline


class NewsPipelineTest(unittest.TestCase):
    def _config(self):
        return SimpleNamespace(
            holdings=[SimpleNamespace(code="000001", name="测试基金", type="domestic")]
        )

    def _analyzer(self):
        return SimpleNamespace(
            funds={
                "000001": {
                    "holdings": [{"stock_code": "688256", "stock_name": "寒武纪", "weight": 0.1}],
                    "sectors": [{"sector": "半导体", "weight": 0.3}],
                    "nav": pd.DataFrame(),
                }
            }
        )

    def test_pipeline_keeps_fetched_fund_news_after_deduplication(self):
        fetched = [{
            "title": "寒武纪订单增长",
            "content": "半导体需求改善",
            "date": "2026-05-22",
            "source": "财联社",
            "matched_terms": ["寒武纪"],
        }]
        with patch("src.news.news_fetcher.fetch_fund_news", return_value=fetched):
            result = run_news_pipeline(
                self._analyzer(),
                self._config(),
                days=7,
                report_date=date(2026, 5, 22),
            )

        self.assertEqual(result[0]["news_count"], 1)
        self.assertEqual(result[0]["news_list"][0]["title"], "寒武纪订单增长")

    def test_pipeline_excludes_post_cutoff_news_from_scoring(self):
        fetched = [
            {"title": "寒武纪订单增长", "content": "", "date": "2026-05-22", "source": "财联社", "matched_terms": ["寒武纪"]},
            {"title": "寒武纪盘后公告", "content": "", "date": "2026-05-23", "source": "交易所", "matched_terms": ["寒武纪"]},
        ]
        with patch("src.news.news_fetcher.fetch_fund_news", return_value=fetched):
            result = run_news_pipeline(
                self._analyzer(),
                self._config(),
                days=7,
                report_date=date(2026, 5, 22),
            )

        self.assertEqual([item["date"] for item in result[0]["news_list"]], ["2026-05-22"])
        self.assertEqual(result[0]["post_cutoff_news"][0]["date"], "2026-05-23")


if __name__ == "__main__":
    unittest.main()
