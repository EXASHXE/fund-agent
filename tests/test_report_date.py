import os
import unittest
from datetime import datetime, date
from unittest.mock import patch

from src.config.shared import effective_report_date, dca_effective_date


class ReportDateTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("FUND_REPORT_CUTOFF_HOUR", None)
        os.environ.pop("FUND_REPORT_CUTOFF_MINUTE", None)
        os.environ.pop("FUND_DCA_CUTOFF_HOUR", None)
        os.environ.pop("FUND_DCA_CUTOFF_MINUTE", None)

    def test_default_cutoff_is_2222_on_trade_day(self):
        """22:22 前报告使用前一个交易日口径，22:22 后使用当日口径。"""
        import src.engine.calendar as cal_mod
        orig_trade = cal_mod.is_trade_day
        orig_prev = cal_mod.previous_trade_day
        cal_mod.is_trade_day = lambda d: True
        cal_mod.previous_trade_day = lambda d: d
        try:
            before = effective_report_date(datetime(2026, 5, 15, 22, 21))
            at_cutoff = effective_report_date(datetime(2026, 5, 15, 22, 22))
        finally:
            cal_mod.is_trade_day = orig_trade
            cal_mod.previous_trade_day = orig_prev

        self.assertEqual(before, date(2026, 5, 14))
        self.assertEqual(at_cutoff, date(2026, 5, 15))

    def test_dca_cutoff_is_1000(self):
        """10:00 前定投未更新，使用前一日；10:00 后当日定投已更新。"""
        before = dca_effective_date(datetime(2026, 5, 21, 9, 59))
        after = dca_effective_date(datetime(2026, 5, 21, 10, 0))

        self.assertEqual(before, date(2026, 5, 20))
        self.assertEqual(after, date(2026, 5, 21))


if __name__ == "__main__":
    unittest.main()
