from datetime import date, timedelta
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.cli import _compute_holdings
from src.engine.calculator import compute_fund
from src.engine.events import EventType, FundEvent, generate_events


def _is_weekday(d):
    return d.weekday() < 5


def _next_weekday(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


class EngineCalculatorTest(unittest.TestCase):
    def test_qdii_buy_uses_t_plus_1_nav_for_shares(self):
        events = [
            FundEvent(
                event_type=EventType.BUY,
                event_date=date(2026, 5, 11),
                amount=1000,
            )
        ]
        nav_map = {
            date(2026, 5, 11): 1.0,
            date(2026, 5, 12): 2.0,
        }

        with patch("src.engine.calculator.is_trade_day", _is_weekday), \
             patch("src.engine.calculator.next_trade_day", _next_weekday), \
             patch("src.engine.events.is_trade_day", _is_weekday), \
             patch("src.engine.events.next_trade_day", _next_weekday):
            result = compute_fund(
                events=events,
                nav_map=nav_map,
                fee_rate=0,
                settle_delay=2,
                today=date(2026, 5, 13),
            )

        self.assertEqual(result["total_shares"], 500.0)
        self.assertEqual(result["current_asset"], 1000.0)

    def test_buy_shares_keep_four_decimal_precision(self):
        events = [
            FundEvent(
                event_type=EventType.BUY,
                event_date=date(2026, 5, 11),
                amount=1000,
            )
        ]
        nav_map = {date(2026, 5, 11): 1.2345}

        with patch("src.engine.calculator.is_trade_day", _is_weekday), \
             patch("src.engine.calculator.next_trade_day", _next_weekday), \
             patch("src.engine.events.is_trade_day", _is_weekday), \
             patch("src.engine.events.next_trade_day", _next_weekday):
            result = compute_fund(
                events=events,
                nav_map=nav_map,
                fee_rate=0.0015,
                settle_delay=1,
                today=date(2026, 5, 12),
            )

        self.assertEqual(result["total_shares"], 808.8313)

    def test_buy_uses_transaction_nav_when_provided(self):
        events = [
            FundEvent(
                event_type=EventType.BUY,
                event_date=date(2026, 5, 11),
                amount=1000,
                nav=2.0,
            )
        ]
        nav_map = {
            date(2026, 5, 11): 1.0,
            date(2026, 5, 12): 1.5,
        }

        with patch("src.engine.calculator.is_trade_day", _is_weekday), \
             patch("src.engine.calculator.next_trade_day", _next_weekday), \
             patch("src.engine.events.is_trade_day", _is_weekday), \
             patch("src.engine.events.next_trade_day", _next_weekday):
            result = compute_fund(
                events=events,
                nav_map=nav_map,
                fee_rate=0,
                settle_delay=1,
                today=date(2026, 5, 12),
            )

        self.assertEqual(result["total_shares"], 500.0)
        self.assertEqual(result["avg_cost"], 2.0)

    def test_generate_events_orders_buy_before_calibration_on_same_day(self):
        events = generate_events(
            purchases=[{"date": "2026-05-11", "amount": 1000}],
            dca_strategy=None,
            calibrations=[{"date": "2026-05-11", "actual_shares": 100}],
            today=date(2026, 5, 11),
        )

        self.assertEqual(
            [event.event_type for event in events],
            [EventType.BUY, EventType.CALIBRATE],
        )

    def test_compute_holdings_keeps_transaction_ledger_as_truth(self):
        store = SimpleNamespace(
            get_fund=lambda code: {"id": None, "code": code, "name": "测试基金"}
        )
        holding = SimpleNamespace(
            code="000001",
            name="测试基金",
            type="domestic",
            fee_rate=0.0,
            settle_delay=1,
            purchases=[
                SimpleNamespace(
                    date=date(2026, 5, 11),
                    amount=1000.0,
                    nav=2.0,
                    after_1500=False,
                )
            ],
            dca=None,
            calibrations=[],
            shares=400.0,
            avg_cost=1.5,
            pending_amount=0.0,
        )
        config = SimpleNamespace(holdings=[holding])
        nav_df = pd.DataFrame(
            {"单位净值": [1.0, 3.0]},
            index=[date(2026, 5, 11), date(2026, 5, 15)],
        )
        analyzer = SimpleNamespace(
            funds={"000001": {"nav": nav_df, "basic": {"name": "测试基金"}}}
        )

        with patch("src.cli.effective_report_date", lambda: date(2026, 5, 15)), \
             patch("src.db.database.get_session", lambda: None), \
             patch("src.engine.calculator.is_trade_day", _is_weekday), \
             patch("src.engine.calculator.next_trade_day", _next_weekday), \
             patch("src.engine.events.is_trade_day", _is_weekday), \
             patch("src.engine.events.next_trade_day", _next_weekday):
            result = _compute_holdings(store, config, ["000001"], analyzer=analyzer)

        detail = result["by_fund"]["000001"]
        self.assertEqual(detail["total_shares"], 500.0)
        self.assertEqual(detail["avg_cost"], 2.0)
        self.assertEqual(detail["current_value"], 1500.0)
        self.assertEqual(detail["profit"], 500.0)


if __name__ == "__main__":
    unittest.main()
