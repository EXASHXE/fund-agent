"""Tests for M7.9 trade date rules extensions (confirm date, rule profiles, settlement).

Covers:
1. Domestic T+1 confirm
2. QDII T+2 confirm
3. Unknown rule profile blocks full reconstruction
4. Rule profile inference
5. Settlement date computation
6. Full date annotation
"""
from __future__ import annotations

import pytest
from datetime import date, datetime

from src.tools.portfolio.trade_date_rules import (
    RULE_PROFILE_DOMESTIC_T1,
    RULE_PROFILE_QDII_T2,
    RULE_PROFILE_UNKNOWN,
    RULE_PROFILE_MONEY_MARKET_T1,
    RULE_PROFILE_BOND_T1,
    annotate_transaction_with_dates,
    compute_confirm_date,
    compute_settlement_date,
    infer_rule_profile,
    is_trading_day,
    CUTOFF_STATUS_BEFORE,
    CUTOFF_STATUS_AFTER,
)


class TestConfirmDateRules:
    def test_domestic_confirm_date_t1(self):
        trade_date = date(2025, 5, 15)
        confirm = compute_confirm_date(trade_date, RULE_PROFILE_DOMESTIC_T1)
        assert confirm == date(2025, 5, 16)

    def test_qdii_confirm_date_t2(self):
        trade_date = date(2025, 5, 15)
        confirm = compute_confirm_date(trade_date, RULE_PROFILE_QDII_T2)
        assert confirm == date(2025, 5, 19)  # Skips weekend

    def test_unknown_rule_profile_returns_none(self):
        trade_date = date(2025, 5, 15)
        confirm = compute_confirm_date(trade_date, RULE_PROFILE_UNKNOWN)
        assert confirm is None

    def test_confirm_date_skips_weekend(self):
        # Friday → T+1 is Saturday → Monday
        trade_date = date(2025, 5, 16)
        confirm = compute_confirm_date(trade_date, RULE_PROFILE_DOMESTIC_T1)
        assert confirm == date(2025, 5, 19)  # Monday

    def test_money_market_t1(self):
        trade_date = date(2025, 5, 15)
        confirm = compute_confirm_date(trade_date, RULE_PROFILE_MONEY_MARKET_T1)
        assert confirm == date(2025, 5, 16)

    def test_bond_fund_t1(self):
        trade_date = date(2025, 5, 15)
        confirm = compute_confirm_date(trade_date, RULE_PROFILE_BOND_T1)
        assert confirm == date(2025, 5, 16)


class TestRuleProfileInference:
    def test_qdii_detected_by_name(self):
        profile = infer_rule_profile(fund_name="华夏海外收益QDII")
        assert profile == RULE_PROFILE_QDII_T2

    def test_qdii_detected_by_flag(self):
        profile = infer_rule_profile(is_qdii_like=True)
        assert profile == RULE_PROFILE_QDII_T2

    def test_money_market_detected_by_name(self):
        profile = infer_rule_profile(fund_name="天弘余额宝货币")
        assert profile == RULE_PROFILE_MONEY_MARKET_T1

    def test_bond_detected_by_name(self):
        profile = infer_rule_profile(fund_name="易方达增强回报债券")
        assert profile == RULE_PROFILE_BOND_T1

    def test_domestic_default(self):
        profile = infer_rule_profile(fund_code="000001")
        assert profile == RULE_PROFILE_DOMESTIC_T1

    def test_unknown_when_no_info(self):
        profile = infer_rule_profile()
        assert profile == RULE_PROFILE_UNKNOWN


class TestSettlementDate:
    def test_domestic_settlement_t1(self):
        trade_date = date(2025, 5, 15)
        settlement = compute_settlement_date(trade_date, RULE_PROFILE_DOMESTIC_T1)
        assert settlement == date(2025, 5, 16)

    def test_qdii_settlement_t2(self):
        trade_date = date(2025, 5, 15)
        settlement = compute_settlement_date(trade_date, RULE_PROFILE_QDII_T2)
        assert settlement == date(2025, 5, 19)

    def test_unknown_returns_none(self):
        trade_date = date(2025, 5, 15)
        settlement = compute_settlement_date(trade_date, RULE_PROFILE_UNKNOWN)
        assert settlement is None


class TestAnnotateTransactionWithDates:
    def test_annotate_adds_all_date_fields(self):
        txn = {
            "submitted_at": "2025-05-15T10:30:00",
            "trade_date": "2025-05-15",
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
        }
        result = annotate_transaction_with_dates(txn)
        assert "cutoff_status" in result
        assert "effective_trade_date" in result
        assert "confirm_date" in result
        assert "settlement_date" in result
        assert "rule_profile" in result
        assert "submitted_date" in result
        assert "submitted_time" in result
        assert "cutoff_time" in result

    def test_annotate_domestic_fund(self):
        txn = {
            "submitted_at": "2025-05-15T10:30:00",
            "trade_date": "2025-05-15",
            "fund_code": "000001",
        }
        result = annotate_transaction_with_dates(txn)
        assert result["rule_profile"] == RULE_PROFILE_DOMESTIC_T1
        assert result["cutoff_status"] == CUTOFF_STATUS_BEFORE

    def test_annotate_qdii_fund(self):
        txn = {
            "submitted_at": "2025-05-15T10:30:00",
            "trade_date": "2025-05-15",
            "fund_name": "华夏海外收益QDII",
        }
        result = annotate_transaction_with_dates(txn)
        assert result["rule_profile"] == RULE_PROFILE_QDII_T2

    def test_annotate_after_cutoff(self):
        txn = {
            "submitted_at": "2025-05-15T16:00:00",
            "trade_date": "2025-05-15",
            "fund_code": "000001",
        }
        result = annotate_transaction_with_dates(txn)
        assert result["cutoff_status"] == CUTOFF_STATUS_AFTER
        # Effective trade date should be next trading day
        assert result["effective_trade_date"] != "2025-05-15"
