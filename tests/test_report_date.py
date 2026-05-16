import os
import unittest
from datetime import datetime, date
from unittest.mock import patch

from src.config.shared import effective_report_date


class ReportDateTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("FUND_REPORT_CUTOFF_HOUR", None)
        os.environ.pop("FUND_REPORT_CUTOFF_MINUTE", None)

    def test_default_cutoff_is_2130_on_trade_day(self):
        with patch("src.engine.calendar.is_trade_day", lambda d: True), \
             patch("src.engine.calendar.previous_trade_day", lambda d: d):
            before = effective_report_date(datetime(2026, 5, 15, 21, 29))
            at_cutoff = effective_report_date(datetime(2026, 5, 15, 21, 30))

        self.assertEqual(before, date(2026, 5, 14))
        self.assertEqual(at_cutoff, date(2026, 5, 15))


if __name__ == "__main__":
    unittest.main()
