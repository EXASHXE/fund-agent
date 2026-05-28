import unittest
import time
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

    def test_pipeline_fetches_multiple_funds_in_parallel_and_preserves_order(self):
        config = SimpleNamespace(
            holdings=[
                SimpleNamespace(code="000001", name="一号基金", type="domestic"),
                SimpleNamespace(code="000002", name="二号基金", type="domestic"),
            ]
        )
        analyzer = SimpleNamespace(
            funds={
                "000001": {
                    "holdings": [{"stock_code": "688256", "stock_name": "寒武纪", "weight": 0.1}],
                    "sectors": [],
                    "nav": pd.DataFrame(),
                },
                "000002": {
                    "holdings": [{"stock_code": "002371", "stock_name": "北方华创", "weight": 0.1}],
                    "sectors": [],
                    "nav": pd.DataFrame(),
                },
            }
        )

        def fake_fetch(code, name, **kwargs):
            time.sleep(0.15)
            return [{
                "title": f"{name} 订单增长",
                "content": "半导体需求改善",
                "date": "2026-05-22",
                "source": "财联社",
                "matched_terms": [name],
            }]

        started = time.perf_counter()
        with patch("src.news.news_fetcher.fetch_fund_news", side_effect=fake_fetch):
            result = run_news_pipeline(
                analyzer,
                config,
                days=7,
                report_date=date(2026, 5, 22),
                max_workers=2,
            )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.28)
        self.assertEqual([item["fund_code"] for item in result], ["000001", "000002"])
        self.assertEqual(result[0]["news_list"][0]["title"], "一号基金 订单增长")


if __name__ == "__main__":
    unittest.main()
