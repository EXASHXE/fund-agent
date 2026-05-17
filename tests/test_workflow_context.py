import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from src.cli import _build_workflow_context


class WorkflowContextTest(unittest.TestCase):
    def test_monday_before_cutoff_uses_non_trade_day_mode(self):
        config = SimpleNamespace(holdings=[])
        with patch("src.cli._shared_today", lambda: date(2026, 5, 18)), \
             patch("src.cli.effective_report_date", lambda: date(2026, 5, 15)), \
             patch("src.engine.calendar.is_trade_day", lambda d: d == date(2026, 5, 18)):
            ctx = _build_workflow_context(config, {"by_fund": {}, "funds": []})

        self.assertTrue(ctx["run_is_trade_day"])
        self.assertFalse(ctx["is_trade_day"])
        self.assertEqual(ctx["mode"], "prior_settlement")


if __name__ == "__main__":
    unittest.main()
