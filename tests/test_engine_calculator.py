from datetime import date, timedelta
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
