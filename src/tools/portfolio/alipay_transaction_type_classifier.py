"""Alipay transaction type classifier — M7.20.

Enhanced classification of Alipay fund transactions into fine-grained
lifecycle categories: buy, fixed_investment, sell, conversion_in,
conversion_out, cash_dividend, dividend_reinvestment, buy_refund,
confirmation_refund, pending_confirmation, activity_gift, fee, unknown.

This module operates on normalized transaction dicts (from
import_alipay_transactions.py output) and produces a transaction_type_summary
with counts for each category.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence


# ── Fine-grained transaction types ───────────────────────────────────────

TXN_TYPE_BUY = "buy"
TXN_TYPE_FIXED_INVESTMENT = "fixed_investment"
TXN_TYPE_SELL = "sell"
TXN_TYPE_REDEMPTION = "redemption"
TXN_TYPE_CONVERSION_IN = "conversion_in"
TXN_TYPE_CONVERSION_OUT = "conversion_out"
TXN_TYPE_CASH_DIVIDEND = "cash_dividend"
TXN_TYPE_DIVIDEND_REINVESTMENT = "dividend_reinvestment"
TXN_TYPE_BUY_REFUND = "buy_refund"
TXN_TYPE_CONFIRMATION_REFUND = "confirmation_refund"
TXN_TYPE_PENDING_CONFIRMATION = "pending_confirmation"
TXN_TYPE_ACTIVITY_GIFT = "activity_gift"
TXN_TYPE_MANAGEMENT_FEE = "management_fee"
TXN_TYPE_SERVICE_FEE = "service_fee"
TXN_TYPE_UNKNOWN = "unknown"

VALID_TXN_TYPES = frozenset({
    TXN_TYPE_BUY,
    TXN_TYPE_FIXED_INVESTMENT,
    TXN_TYPE_SELL,
    TXN_TYPE_REDEMPTION,
    TXN_TYPE_CONVERSION_IN,
    TXN_TYPE_CONVERSION_OUT,
    TXN_TYPE_CASH_DIVIDEND,
    TXN_TYPE_DIVIDEND_REINVESTMENT,
    TXN_TYPE_BUY_REFUND,
    TXN_TYPE_CONFIRMATION_REFUND,
    TXN_TYPE_PENDING_CONFIRMATION,
    TXN_TYPE_ACTIVITY_GIFT,
    TXN_TYPE_MANAGEMENT_FEE,
    TXN_TYPE_SERVICE_FEE,
    TXN_TYPE_UNKNOWN,
})


@dataclass
class TransactionTypeSummary:
    """Summary of transaction type classification counts."""

    total_transactions: int = 0
    buy_count: int = 0
    sell_count: int = 0
    fixed_investment_count: int = 0
    conversion_count: int = 0
    dividend_count: int = 0
    refund_count: int = 0
    pending_count: int = 0
    fee_count: int = 0
    unknown_count: int = 0
    manual_review_count: int = 0
    # Fine-grained counts
    conversion_in_count: int = 0
    conversion_out_count: int = 0
    cash_dividend_count: int = 0
    dividend_reinvestment_count: int = 0
    buy_refund_count: int = 0
    confirmation_refund_count: int = 0
    pending_confirmation_count: int = 0
    activity_gift_count: int = 0
    management_fee_count: int = 0
    service_fee_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_transactions": self.total_transactions,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "fixed_investment_count": self.fixed_investment_count,
            "conversion_count": self.conversion_count,
            "dividend_count": self.dividend_count,
            "refund_count": self.refund_count,
            "pending_count": self.pending_count,
            "fee_count": self.fee_count,
            "unknown_count": self.unknown_count,
            "manual_review_count": self.manual_review_count,
            "conversion_in_count": self.conversion_in_count,
            "conversion_out_count": self.conversion_out_count,
            "cash_dividend_count": self.cash_dividend_count,
            "dividend_reinvestment_count": self.dividend_reinvestment_count,
            "buy_refund_count": self.buy_refund_count,
            "confirmation_refund_count": self.confirmation_refund_count,
            "pending_confirmation_count": self.pending_confirmation_count,
            "activity_gift_count": self.activity_gift_count,
            "management_fee_count": self.management_fee_count,
            "service_fee_count": self.service_fee_count,
        }


def classify_alipay_transaction(txn: dict[str, Any]) -> str:
    """Classify a normalized Alipay transaction into a fine-grained type.

    Uses product_name keywords, action field, and pending flag to determine
    the specific transaction lifecycle event.

    Args:
        txn: Normalized transaction dict with fields like action, fund_name,
             product_name, remark, pending, etc.

    Returns:
        One of the TXN_TYPE_* constants.
    """
    action = txn.get("action", "").lower()
    pending = txn.get("pending", False)

    # Get text fields for keyword matching
    product_name = txn.get("fund_name", "") or txn.get("product_name", "")
    remark = txn.get("remark", "") or ""
    text = f"{product_name} {remark}"

    # ── Pending confirmation ─────────────────────────────────────────
    if pending or "确认中" in text:
        return TXN_TYPE_PENDING_CONFIRMATION

    # ── Activity gift ────────────────────────────────────────────────
    if "活动赠送" in text or "赠送" in text:
        return TXN_TYPE_ACTIVITY_GIFT

    # ── Refund subtypes ──────────────────────────────────────────────
    if action == "refund" or "退款" in text or "退回" in text:
        # Distinguish buy refund vs confirmation refund
        if "确认成功退款" in text:
            return TXN_TYPE_CONFIRMATION_REFUND
        if "买入退款" in text or "申购退款" in text:
            return TXN_TYPE_BUY_REFUND
        if "转换退款" in text:
            return TXN_TYPE_CONFIRMATION_REFUND
        # Generic refund
        return TXN_TYPE_BUY_REFUND

    # ── Fee subtypes ─────────────────────────────────────────────────
    if action == "fee" or "手续费" in text:
        if "管理费" in text:
            return TXN_TYPE_MANAGEMENT_FEE
        if "销售服务费" in text or "服务费" in text:
            return TXN_TYPE_SERVICE_FEE
        return TXN_TYPE_MANAGEMENT_FEE

    # ── Conversion subtypes ──────────────────────────────────────────
    if action == "conversion" or "转换" in text:
        if "转出" in text or "转换出" in text:
            return TXN_TYPE_CONVERSION_OUT
        if "转换至" in text or "转入" in text or "转换入" in text:
            return TXN_TYPE_CONVERSION_IN
        # Ambiguous conversion — check remark for direction
        if "转出" in remark:
            return TXN_TYPE_CONVERSION_OUT
        if "转入" in remark or "转换至" in remark:
            return TXN_TYPE_CONVERSION_IN
        # Default: conversion_out for source fund
        return TXN_TYPE_CONVERSION_OUT

    # ── Dividend subtypes ────────────────────────────────────────────
    if action == "dividend" or "分红" in text or "收益发放" in text:
        if "红利再投" in text or "再投资" in text:
            return TXN_TYPE_DIVIDEND_REINVESTMENT
        return TXN_TYPE_CASH_DIVIDEND

    # ── Sell / redemption ────────────────────────────────────────────
    if action == "sell" or "卖出" in text:
        if "赎回" in text:
            return TXN_TYPE_REDEMPTION
        return TXN_TYPE_SELL

    # ── Buy / fixed investment ───────────────────────────────────────
    if action == "buy" or "买入" in text or "申购" in text or "购买" in text or "定投" in text:
        if "定投" in text:
            return TXN_TYPE_FIXED_INVESTMENT
        return TXN_TYPE_BUY

    # ── Redemption keyword alone ─────────────────────────────────────
    if "赎回" in text:
        return TXN_TYPE_REDEMPTION

    # ── Fallback: unknown ────────────────────────────────────────────
    return TXN_TYPE_UNKNOWN


def classify_transactions(
    transactions: Sequence[dict[str, Any]],
) -> TransactionTypeSummary:
    """Classify all transactions and produce a summary.

    Args:
        transactions: Sequence of normalized transaction dicts.

    Returns:
        TransactionTypeSummary with counts for each type.
    """
    summary = TransactionTypeSummary()
    summary.total_transactions = len(transactions)

    for txn in transactions:
        txn_type = classify_alipay_transaction(txn)

        # Update aggregate counts
        if txn_type in (TXN_TYPE_BUY, TXN_TYPE_FIXED_INVESTMENT):
            summary.buy_count += 1
        if txn_type == TXN_TYPE_FIXED_INVESTMENT:
            summary.fixed_investment_count += 1
        if txn_type in (TXN_TYPE_SELL, TXN_TYPE_REDEMPTION):
            summary.sell_count += 1
        if txn_type in (TXN_TYPE_CONVERSION_IN, TXN_TYPE_CONVERSION_OUT):
            summary.conversion_count += 1
        if txn_type in (TXN_TYPE_CASH_DIVIDEND, TXN_TYPE_DIVIDEND_REINVESTMENT):
            summary.dividend_count += 1
        if txn_type in (TXN_TYPE_BUY_REFUND, TXN_TYPE_CONFIRMATION_REFUND):
            summary.refund_count += 1
        if txn_type == TXN_TYPE_PENDING_CONFIRMATION:
            summary.pending_count += 1
        if txn_type in (TXN_TYPE_MANAGEMENT_FEE, TXN_TYPE_SERVICE_FEE):
            summary.fee_count += 1
        if txn_type == TXN_TYPE_UNKNOWN:
            summary.unknown_count += 1
            summary.manual_review_count += 1

        # Update fine-grained counts
        if txn_type == TXN_TYPE_CONVERSION_IN:
            summary.conversion_in_count += 1
        elif txn_type == TXN_TYPE_CONVERSION_OUT:
            summary.conversion_out_count += 1
        elif txn_type == TXN_TYPE_CASH_DIVIDEND:
            summary.cash_dividend_count += 1
        elif txn_type == TXN_TYPE_DIVIDEND_REINVESTMENT:
            summary.dividend_reinvestment_count += 1
        elif txn_type == TXN_TYPE_BUY_REFUND:
            summary.buy_refund_count += 1
        elif txn_type == TXN_TYPE_CONFIRMATION_REFUND:
            summary.confirmation_refund_count += 1
        elif txn_type == TXN_TYPE_PENDING_CONFIRMATION:
            summary.pending_confirmation_count += 1
        elif txn_type == TXN_TYPE_ACTIVITY_GIFT:
            summary.activity_gift_count += 1
        elif txn_type == TXN_TYPE_MANAGEMENT_FEE:
            summary.management_fee_count += 1
        elif txn_type == TXN_TYPE_SERVICE_FEE:
            summary.service_fee_count += 1

    return summary
