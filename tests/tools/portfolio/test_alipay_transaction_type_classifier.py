"""Tests for M7.20 Alipay transaction type classifier.

Validates:
1. alipay_buy_suffix_classified
2. alipay_fixed_investment_classified
3. alipay_sell_suffix_classified
4. alipay_conversion_pattern_classified
5. alipay_dividend_classified
6. alipay_refund_classified
7. alipay_pending_classified
8. unknown_transaction_requires_manual_review
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.alipay_transaction_type_classifier import (
    TXN_TYPE_ACTIVITY_GIFT,
    TXN_TYPE_BUY,
    TXN_TYPE_BUY_REFUND,
    TXN_TYPE_CASH_DIVIDEND,
    TXN_TYPE_CONFIRMATION_REFUND,
    TXN_TYPE_CONVERSION_IN,
    TXN_TYPE_CONVERSION_OUT,
    TXN_TYPE_DIVIDEND_REINVESTMENT,
    TXN_TYPE_FIXED_INVESTMENT,
    TXN_TYPE_MANAGEMENT_FEE,
    TXN_TYPE_PENDING_CONFIRMATION,
    TXN_TYPE_REDEMPTION,
    TXN_TYPE_SELL,
    TXN_TYPE_SERVICE_FEE,
    TXN_TYPE_UNKNOWN,
    classify_alipay_transaction,
    classify_transactions,
)


def _make_txn(
    action: str = "buy",
    fund_name: str = "某基金",
    remark: str = "",
    pending: bool = False,
) -> dict:
    return {
        "action": action,
        "fund_name": fund_name,
        "remark": remark,
        "pending": pending,
        "amount": 1000.0,
    }


class TestAlipayBuySuffixClassified:
    """Buy transactions with various suffixes."""

    def test_buy_action(self):
        txn = _make_txn(action="buy")
        assert classify_alipay_transaction(txn) == TXN_TYPE_BUY

    def test_buy_with_fund_name_keyword(self):
        txn = _make_txn(action="unknown", fund_name="某基金-买入")
        assert classify_alipay_transaction(txn) == TXN_TYPE_BUY

    def test_purchase_keyword(self):
        txn = _make_txn(action="unknown", fund_name="某基金 购买")
        assert classify_alipay_transaction(txn) == TXN_TYPE_BUY


class TestAlipayFixedInvestmentClassified:
    """Fixed investment (定投) transactions."""

    def test_fixed_investment_action(self):
        txn = _make_txn(action="buy", fund_name="某基金-定投")
        assert classify_alipay_transaction(txn) == TXN_TYPE_FIXED_INVESTMENT

    def test_fixed_investment_keyword(self):
        txn = _make_txn(action="unknown", fund_name="某基金定投")
        assert classify_alipay_transaction(txn) == TXN_TYPE_FIXED_INVESTMENT


class TestAlipaySellSuffixClassified:
    """Sell/redemption transactions."""

    def test_sell_action(self):
        txn = _make_txn(action="sell")
        assert classify_alipay_transaction(txn) == TXN_TYPE_SELL

    def test_sell_keyword(self):
        txn = _make_txn(action="unknown", fund_name="某基金-卖出")
        assert classify_alipay_transaction(txn) == TXN_TYPE_SELL

    def test_redemption_keyword(self):
        txn = _make_txn(action="sell", fund_name="某基金-赎回")
        assert classify_alipay_transaction(txn) == TXN_TYPE_REDEMPTION


class TestAlipayConversionPatternClassified:
    """Conversion (转换) transactions with direction."""

    def test_conversion_out(self):
        txn = _make_txn(action="conversion", fund_name="某基金-转出")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CONVERSION_OUT

    def test_conversion_in(self):
        txn = _make_txn(action="conversion", fund_name="某基金-转换至")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CONVERSION_IN

    def test_conversion_ambiguous_defaults_out(self):
        txn = _make_txn(action="conversion", fund_name="某基金")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CONVERSION_OUT

    def test_conversion_in_via_remark(self):
        txn = _make_txn(action="conversion", fund_name="某基金", remark="转入某基金B")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CONVERSION_IN


class TestAlipayDividendClassified:
    """Dividend transactions."""

    def test_cash_dividend(self):
        txn = _make_txn(action="dividend", fund_name="某基金-分红")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CASH_DIVIDEND

    def test_dividend_keyword(self):
        txn = _make_txn(action="unknown", fund_name="某基金-收益发放")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CASH_DIVIDEND

    def test_dividend_reinvestment(self):
        txn = _make_txn(action="dividend", fund_name="某基金-红利再投")
        assert classify_alipay_transaction(txn) == TXN_TYPE_DIVIDEND_REINVESTMENT


class TestAlipayRefundClassified:
    """Refund transactions with subtypes."""

    def test_buy_refund(self):
        txn = _make_txn(action="refund", fund_name="某基金-买入退款")
        assert classify_alipay_transaction(txn) == TXN_TYPE_BUY_REFUND

    def test_confirmation_refund(self):
        txn = _make_txn(action="refund", fund_name="某基金-确认成功退款")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CONFIRMATION_REFUND

    def test_conversion_refund(self):
        txn = _make_txn(action="refund", fund_name="某基金-转换退款")
        assert classify_alipay_transaction(txn) == TXN_TYPE_CONFIRMATION_REFUND

    def test_generic_refund(self):
        txn = _make_txn(action="refund", fund_name="某基金-退款")
        assert classify_alipay_transaction(txn) == TXN_TYPE_BUY_REFUND


class TestAlipayPendingClassified:
    """Pending confirmation transactions."""

    def test_pending_flag(self):
        txn = _make_txn(action="buy", pending=True)
        assert classify_alipay_transaction(txn) == TXN_TYPE_PENDING_CONFIRMATION

    def test_pending_keyword(self):
        txn = _make_txn(action="unknown", fund_name="某基金-份额确认中")
        assert classify_alipay_transaction(txn) == TXN_TYPE_PENDING_CONFIRMATION


class TestActivityGift:
    """Activity gift transactions."""

    def test_activity_gift(self):
        txn = _make_txn(action="unknown", fund_name="某基金-活动赠送")
        assert classify_alipay_transaction(txn) == TXN_TYPE_ACTIVITY_GIFT


class TestFeeTypes:
    """Fee subtypes."""

    def test_management_fee(self):
        txn = _make_txn(action="fee", fund_name="某基金-管理费")
        assert classify_alipay_transaction(txn) == TXN_TYPE_MANAGEMENT_FEE

    def test_service_fee(self):
        txn = _make_txn(action="fee", fund_name="某基金-销售服务费")
        assert classify_alipay_transaction(txn) == TXN_TYPE_SERVICE_FEE


class TestUnknownTransactionRequiresManualReview:
    """Unknown transactions must be flagged for manual review."""

    def test_unknown_action(self):
        txn = _make_txn(action="unknown", fund_name="某基金")
        assert classify_alipay_transaction(txn) == TXN_TYPE_UNKNOWN

    def test_unknown_in_summary(self):
        txns = [_make_txn(action="unknown", fund_name="某基金")]
        summary = classify_transactions(txns)
        assert summary.unknown_count == 1
        assert summary.manual_review_count == 1


class TestClassifyTransactionsSummary:
    """Summary counts from batch classification."""

    def test_mixed_transactions(self):
        txns = [
            _make_txn(action="buy", fund_name="基金A-买入"),
            _make_txn(action="buy", fund_name="基金A-定投"),
            _make_txn(action="sell", fund_name="基金B-卖出"),
            _make_txn(action="dividend", fund_name="基金C-分红"),
            _make_txn(action="refund", fund_name="基金D-买入退款"),
            _make_txn(action="conversion", fund_name="基金E-转出"),
            _make_txn(action="unknown", fund_name="基金F"),
        ]
        summary = classify_transactions(txns)
        assert summary.total_transactions == 7
        assert summary.buy_count == 2  # buy + fixed_investment
        assert summary.fixed_investment_count == 1
        assert summary.sell_count == 1
        assert summary.dividend_count == 1
        assert summary.refund_count == 1
        assert summary.conversion_count == 1
        assert summary.unknown_count == 1

    def test_empty_transactions(self):
        summary = classify_transactions([])
        assert summary.total_transactions == 0
        assert summary.buy_count == 0
