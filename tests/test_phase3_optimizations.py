import unittest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import pandas as pd
import sys

from src.analysis.correlation import compute_correlations
from src.engine.events import generate_events, EventType, FundEvent
from src.news.news_fetcher import _cached_ak_call


def _is_weekday(d):
    return d.weekday() < 5


def _next_weekday(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


class Phase3OptimizationsTest(unittest.TestCase):
    def test_pairwise_correlation_with_missing_days(self):
        """测试相关性计算：用 pairwise 方式在有非重叠日期时是否正常。"""
        dates = [date(2026, 5, 1) + timedelta(days=i) for i in range(50)]
        
        # A: 35天有效数据 (0..34)
        returns_a = [float(i % 5) if i < 35 else None for i in range(50)]
        # B: 49天有效数据
        returns_b = [float(i % 5) for i in range(50)]
        returns_b[5] = None
        # C: 49天有效数据
        returns_c = [float(i % 5) for i in range(50)]
        returns_c[10] = None
        
        series_a = pd.Series(returns_a, index=dates)
        series_b = pd.Series(returns_b, index=dates)
        series_c = pd.Series(returns_c, index=dates)
        
        funds_data = {
            "A": {"nav": pd.DataFrame({"日增长率": series_a})},
            "B": {"nav": pd.DataFrame({"日增长率": series_b})},
            "C": {"nav": pd.DataFrame({"日增长率": series_c})},
        }
        
        corr_df = compute_correlations(funds_data)
        self.assertEqual(corr_df.shape, (3, 3))
        self.assertFalse(corr_df.isna().all().all())
        
        # D: 35天有效数据 (15..49)
        returns_d = [float(i % 5) if i >= 15 else None for i in range(50)]
        series_d = pd.Series(returns_d, index=dates)
        funds_data["D"] = {"nav": pd.DataFrame({"日增长率": series_d})}
        
        corr_df2 = compute_correlations(funds_data)
        self.assertEqual(corr_df2.shape, (4, 4))
        # A 与 D 的共同非空数据只有 20 天 (< 30)，所以 corr_df2.loc["A", "D"] 应该为 NaN
        self.assertTrue(pd.isna(corr_df2.loc["A", "D"]))

    def test_dca_deduplication_resilience(self):
        """测试 DCA 去重在 actual_purchase 其记账日或生效日匹配时的容错行为。"""
        # 情况一：记账日等于定投日 (e.event_date == dd)
        dd = date(2026, 5, 11)
        purchases = [
            {"date": "2026-05-11", "amount": 1000, "after_1500": True}  # e.event_date == dd
        ]
        dca_strategy = {
            "enabled": True,
            "amount": 1000,
            "frequency": "weekly",
            "start_date": "2026-05-11",
            "day_of_week": "mon",
        }
        
        with patch("src.engine.events.is_trade_day", _is_weekday), \
             patch("src.engine.events.next_trade_day", _next_weekday):
            events = generate_events(purchases, dca_strategy, [], date(2026, 5, 11))
        self.assertEqual(len([e for e in events if e.event_type == EventType.BUY]), 1)
        
        # 情况二：生效日等于定投日 (_effective_trade_date == dd)
        purchases_2 = [
            {"date": "2026-05-11", "amount": 1000, "after_1500": True}  # 生效日为 5-12 (周二)
        ]
        dca_strategy_2 = {
            "enabled": True,
            "amount": 1000,
            "frequency": "weekly",
            "start_date": "2026-05-12",
            "day_of_week": "tue",
        }
        
        with patch("src.engine.events.is_trade_day", _is_weekday), \
             patch("src.engine.events.next_trade_day", _next_weekday):
            events_2 = generate_events(purchases_2, dca_strategy_2, [], date(2026, 5, 12))
            
        self.assertEqual(len([e for e in events_2 if e.event_type == EventType.BUY]), 1)

    @patch("time.sleep", return_value=None)
    def test_akshare_retry_success(self, mock_sleep):
        """测试 _cached_ak_call 的自动重试成功行为。"""
        mock_func = MagicMock()
        mock_func.side_effect = [Exception("Net Error 1"), Exception("Net Error 2"), "success_data"]
        
        mock_ak = MagicMock()
        mock_ak.some_api = mock_func
        
        # 必须显式更新全局模块
        with patch.dict("sys.modules", {"akshare": mock_ak}):
            sys.modules["akshare"] = mock_ak
            res = _cached_ak_call("some_api", arg1="val1")
            
        self.assertEqual(res, "success_data")
        self.assertEqual(mock_func.call_count, 3)

    @patch("time.sleep", return_value=None)
    def test_akshare_retry_fail(self, mock_sleep):
        """测试 _cached_ak_call 的自动重试3次全部失败时抛出异常的行为。"""
        mock_func = MagicMock()
        mock_func.side_effect = Exception("Persistent Net Error")
        mock_ak = MagicMock()
        mock_ak.some_api = mock_func
        
        with patch.dict("sys.modules", {"akshare": mock_ak}):
            sys.modules["akshare"] = mock_ak
            with self.assertRaises(Exception) as ctx:
                _cached_ak_call("some_api", arg1="val1")
            self.assertIn("Persistent Net Error", str(ctx.exception))
        
        self.assertEqual(mock_func.call_count, 3)


if __name__ == "__main__":
    unittest.main()
