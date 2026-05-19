import sys
import types
import unittest

import pandas as pd

from src.news.news_fetcher import extract_holding_keywords, fetch_fund_news


class NewsFetcherTest(unittest.TestCase):
    def test_fund_keyword_uses_market_news_fallback(self):
        fake_ak = types.SimpleNamespace()
        fake_ak.fund_portfolio_hold_em = lambda symbol, date: pd.DataFrame()

        def stock_news_em(symbol):
            raise AssertionError("stock_news_em should not receive fund keywords")

        fake_ak.stock_news_em = stock_news_em
        fake_ak.stock_info_global_cls = lambda symbol="全部": pd.DataFrame([
            {
                "标题": "纳斯达克科技股上涨，人工智能板块走强",
                "内容": "英伟达和微软带动美股科技股反弹",
                "时间": "2026-05-18 09:00:00",
                "来源": "财联社",
            }
        ])
        fake_ak.stock_news_main_cx = lambda: pd.DataFrame()
        fake_ak.news_cctv = lambda date: pd.DataFrame()

        old = sys.modules.get("akshare")
        sys.modules["akshare"] = fake_ak
        try:
            news = fetch_fund_news("017436", "华宝纳斯达克精选股票(QDII)A", days=7)
        finally:
            if old is not None:
                sys.modules["akshare"] = old
            else:
                sys.modules.pop("akshare", None)

        self.assertEqual(len(news), 1)
        self.assertIn("纳斯达克", news[0]["title"])

    def test_holding_keywords_do_not_fallback_to_json_cache(self):
        fake_ak = types.SimpleNamespace()

        def fund_portfolio_hold_em(symbol, date):
            raise RuntimeError("network unavailable")

        fake_ak.fund_portfolio_hold_em = fund_portfolio_hold_em

        old = sys.modules.get("akshare")
        sys.modules["akshare"] = fake_ak
        try:
            stock_codes, keywords = extract_holding_keywords("017436")
        finally:
            if old is not None:
                sys.modules["akshare"] = old
            else:
                sys.modules.pop("akshare", None)

        self.assertEqual(stock_codes, [])
        self.assertEqual(keywords, [])

    def test_agent_keywords_skip_holding_fetch(self):
        fake_ak = types.SimpleNamespace()
        calls = []

        def fund_portfolio_hold_em(symbol, date):
            calls.append((symbol, date))
            raise RuntimeError("holding fetch should be skipped")

        fake_ak.fund_portfolio_hold_em = fund_portfolio_hold_em
        fake_ak.stock_news_em = lambda symbol: pd.DataFrame()
        fake_ak.stock_info_global_cls = lambda symbol="全部": pd.DataFrame([
            {
                "标题": "寒武纪订单增长带动国产AI芯片关注",
                "内容": "半导体设备和算力产业链活跃",
                "时间": "2026-05-18 09:00:00",
                "来源": "财联社",
            }
        ])
        fake_ak.stock_news_main_cx = lambda: pd.DataFrame()
        fake_ak.news_cctv = lambda date: pd.DataFrame()

        old = sys.modules.get("akshare")
        sys.modules["akshare"] = fake_ak
        try:
            news = fetch_fund_news(
                "001198",
                "东方惠灵活配置混合A",
                keywords=["寒武纪", "国产AI芯片"],
                days=7,
            )
        finally:
            if old is not None:
                sys.modules["akshare"] = old
            else:
                sys.modules.pop("akshare", None)

        self.assertEqual(len(news), 1)
        self.assertIn("寒武纪", news[0]["title"])
        self.assertEqual(calls, [])

    def test_matches_terms_chinese_short(self):
        from src.news.news_fetcher import _matches_terms
        self.assertTrue(_matches_terms("芯片行业迎来利好", ["芯片"]))
        self.assertTrue(_matches_terms("半导体板块大涨", ["半导体"]))
        self.assertTrue(_matches_terms("白酒消费回暖", ["白酒"]))

    def test_matches_terms_english_short(self):
        from src.news.news_fetcher import _matches_terms
        self.assertTrue(_matches_terms("AI芯片需求爆发", ["AI"]))
        self.assertTrue(_matches_terms("NVIDIA股价创新高", ["NV"]))

    def test_matches_terms_no_false_positive(self):
        from src.news.news_fetcher import _matches_terms
        self.assertFalse(_matches_terms("正常文章内容", ["芯片"]))
        self.assertFalse(_matches_terms("regular text no match", ["AI"]))

    def test_degrade_keywords_truncates_to_three_chars(self):
        from src.news.news_fetcher import _degrade_keywords
        result = _degrade_keywords(["英伟达", "寒武纪", "消费", "AI"])
        self.assertIn("英伟达", result)  # 3-char stays intact
        self.assertIn("寒武纪", result)
        self.assertIn("消费", result)  # exact 2-char stays intact
        self.assertIn("AI", result)  # 2-char stays intact
        self.assertEqual(len(result), 4)


if __name__ == "__main__":
    unittest.main()
