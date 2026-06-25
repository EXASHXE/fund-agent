"""Tests for trade date rules (M7.2 Stage 4).

Validates:
1. 15:00 cutoff logic
2. Non-trading day handling
3. Effective trade date computation
4. Transaction annotation
"""
from __future__ import annotations

from datetime import date, datetime, time

import pytest

from src.tools.portfolio.trade_date_rules import (
    CUTOFF_STATUS_AFTER,
    CUTOFF_STATUS_BEFORE,
    CUTOFF_STATUS_NON_TRADING_DAY,
    CUTOFF_STATUS_UNKNOWN,
    CUTOFF_TIME,
    VALID_CUTOFF_STATUSES,
    annotate_transaction_with_cutoff,
    compute_cutoff_status,
    compute_effective_trade_date,
    is_trading_day,
    next_trading_day,
)


class TestIsTradingDay:
    def test_weekday_is_trading_day(self):
        # 2025-01-13 is a Monday
        assert is_trading_day(date(2025, 1, 13)) is True

    def test_saturday_is_not(self):
        # 2025-01-11 is a Saturday
        assert is_trading_day(date(2025, 1, 11)) is False

    def test_sunday_is_not(self):
        # 2025-01-12 is a Sunday
        assert is_trading_day(date(2025, 1, 12)) is False

    def test_holiday_is_not(self):
        # 2025-01-01 is New Year's Day (holiday)
        assert is_trading_day(date(2025, 1, 1)) is False

    def test_national_day_holiday(self):
        # 2025-10-01 is National Day
        assert is_trading_day(date(2025, 10, 1)) is False

    def test_regular_weekday_is_trading(self):
        # 2025-03-10 is a regular Monday
        assert is_trading_day(date(2025, 3, 10)) is True


class TestNextTradingDay:
    def test_monday_returns_monday(self):
        # 2025-01-13 is a Monday
        assert next_trading_day(date(2025, 1, 13)) == date(2025, 1, 13)

    def test_friday_returns_friday(self):
        # 2025-01-10 is a Friday
        assert next_trading_day(date(2025, 1, 10)) == date(2025, 1, 10)

    def test_saturday_returns_monday(self):
        # 2025-01-11 is a Saturday → next trading day is Monday 2025-01-13
        assert next_trading_day(date(2025, 1, 11)) == date(2025, 1, 13)

    def test_sunday_returns_monday(self):
        # 2025-01-12 is a Sunday → next trading day is Monday 2025-01-13
        assert next_trading_day(date(2025, 1, 12)) == date(2025, 1, 13)

    def test_holiday_returns_next_trading_day(self):
        # 2025-10-01 is National Day → skip to 2025-10-09 (Thursday)
        result = next_trading_day(date(2025, 10, 1))
        assert result > date(2025, 10, 1)
        assert is_trading_day(result)


class TestComputeCutoffStatus:
    def test_before_cutoff(self):
        dt = datetime(2025, 3, 10, 14, 30)  # 14:30 on a trading day
        assert compute_cutoff_status(dt, None) == CUTOFF_STATUS_BEFORE

    def test_at_cutoff(self):
        dt = datetime(2025, 3, 10, 15, 0)  # exactly 15:00
        assert compute_cutoff_status(dt, None) == CUTOFF_STATUS_AFTER

    def test_after_cutoff(self):
        dt = datetime(2025, 3, 10, 16, 0)  # 16:00 on a trading day
        assert compute_cutoff_status(dt, None) == CUTOFF_STATUS_AFTER

    def test_non_trading_day(self):
        dt = datetime(2025, 1, 11, 10, 0)  # Saturday
        assert compute_cutoff_status(dt, None) == CUTOFF_STATUS_NON_TRADING_DAY

    def test_holiday(self):
        dt = datetime(2025, 10, 1, 10, 0)  # National Day
        assert compute_cutoff_status(dt, None) == CUTOFF_STATUS_NON_TRADING_DAY

    def test_no_time_unknown(self):
        assert compute_cutoff_status(None, date(2025, 3, 10)) == CUTOFF_STATUS_UNKNOWN

    def test_nothing_unknown(self):
        assert compute_cutoff_status(None, None) == CUTOFF_STATUS_UNKNOWN


class TestComputeEffectiveTradeDate:
    def test_before_cutoff_same_day(self):
        dt = datetime(2025, 3, 10, 14, 30)
        assert compute_effective_trade_date(submitted_at=dt) == date(2025, 3, 10)

    def test_after_cutoff_next_day(self):
        dt = datetime(2025, 3, 10, 16, 0)  # Monday 16:00
        # Next trading day after Monday is Tuesday
        assert compute_effective_trade_date(submitted_at=dt) == date(2025, 3, 11)

    def test_friday_after_cutoff_monday(self):
        dt = datetime(2025, 3, 7, 16, 0)  # Friday 16:00
        # Next trading day after Friday+1 is Monday
        result = compute_effective_trade_date(submitted_at=dt)
        assert result == date(2025, 3, 10)
        assert result.weekday() == 0  # Monday

    def test_saturday_next_monday(self):
        dt = datetime(2025, 1, 11, 10, 0)  # Saturday
        result = compute_effective_trade_date(submitted_at=dt)
        assert result == date(2025, 1, 13)  # Monday

    def test_holiday_next_trading_day(self):
        dt = datetime(2025, 10, 1, 10, 0)  # National Day
        result = compute_effective_trade_date(submitted_at=dt)
        assert is_trading_day(result)

    def test_trade_date_only(self):
        result = compute_effective_trade_date(trade_date=date(2025, 3, 10))
        assert result == date(2025, 3, 10)

    def test_no_input_returns_none(self):
        assert compute_effective_trade_date() is None


class TestAnnotateTransactionWithCutoff:
    def test_annotates_before_cutoff(self):
        txn = {
            "submitted_at": "2025-03-10T14:30:00",
            "trade_date": "2025-03-10",
        }
        result = annotate_transaction_with_cutoff(txn)
        assert result["cutoff_status"] == CUTOFF_STATUS_BEFORE
        assert result["effective_trade_date"] == "2025-03-10"
        assert "before 15:00" in result["nav_date_note"]

    def test_annotates_after_cutoff(self):
        txn = {
            "submitted_at": "2025-03-10T16:00:00",
            "trade_date": "2025-03-10",
        }
        result = annotate_transaction_with_cutoff(txn)
        assert result["cutoff_status"] == CUTOFF_STATUS_AFTER
        assert result["effective_trade_date"] == "2025-03-11"
        assert "after 15:00" in result["nav_date_note"]

    def test_annotates_unknown_time(self):
        txn = {
            "trade_date": "2025-03-10",
        }
        result = annotate_transaction_with_cutoff(txn)
        assert result["cutoff_status"] == CUTOFF_STATUS_UNKNOWN
        assert result["effective_trade_date"] == "2025-03-10"

    def test_preserves_original_trade_date(self):
        txn = {
            "submitted_at": "2025-03-10T16:00:00",
            "trade_date": "2025-03-10",
        }
        result = annotate_transaction_with_cutoff(txn)
        # Original trade_date must NOT be modified
        assert result["trade_date"] == "2025-03-10"
        # effective_trade_date is different
        assert result["effective_trade_date"] == "2025-03-11"

    def test_valid_cutoff_statuses(self):
        assert VALID_CUTOFF_STATUSES == {
            CUTOFF_STATUS_BEFORE,
            CUTOFF_STATUS_AFTER,
            CUTOFF_STATUS_NON_TRADING_DAY,
            CUTOFF_STATUS_UNKNOWN,
        }
