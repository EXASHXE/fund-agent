"""Tests for special transaction type semantics in portfolio_input.transactions.

Verifies conversion/refund/fee/dividend handling, manual review flags,
and unit-change guarantees. All data is synthetic.
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.portfolio_input_transactions import (
    build_ledger_from_portfolio_input_transactions,
    normalize_portfolio_input_transaction,
)


class TestConversionSemantics:
    def test_conversion_marked_ambiguous(self):
        """conversion_in → action=conversion, ambiguous_portfolio_effect=True."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "conversion_in",
            "amount": 100.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "conversion"
        assert result["ambiguous_portfolio_effect"] is True
        assert result["manual_review_required"] is True
        assert "ambiguous_portfolio_effect: conversion" in result.get("manual_review_reasons", [])

    def test_conversion_out_marked_ambiguous(self):
        """conversion_out → action=conversion, ambiguous_portfolio_effect=True."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "conversion_out",
            "amount": 100.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "conversion"
        assert result["ambiguous_portfolio_effect"] is True
        assert result["manual_review_required"] is True

    def test_conversion_in_summary(self):
        """Conversion transactions counted in summary."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "conversion_in", "amount": 100.0},
            {"trade_date": "2026-06-02", "fund_code": "000001", "transaction_type": "conversion_out", "amount": 50.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["conversion_count"] == 2
        assert result["summary"]["ambiguous_portfolio_effect"] == 2


class TestRefundSemantics:
    def test_refund_marked_ambiguous(self):
        """refund → action=refund, ambiguous_portfolio_effect=True, manual_review_required=True."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "refund",
            "amount": 50.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "refund"
        assert result["ambiguous_portfolio_effect"] is True
        assert result["manual_review_required"] is True
        assert "ambiguous_portfolio_effect: refund" in result.get("manual_review_reasons", [])

    def test_refund_in_summary(self):
        """Refund transactions counted in summary."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "refund", "amount": 50.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["refund_count"] == 1


class TestFeeSemantics:
    def test_fee_does_not_change_units(self):
        """fee transaction → fee_transaction=True, no units field."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "fee",
            "amount": 5.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "fee"
        assert result.get("fee_transaction") is True
        # Fee should not have units or shares
        assert "units" not in result
        assert "shares" not in result
        # Fee should not require manual review
        assert result["manual_review_required"] is False
        # Fee should not have ambiguous_portfolio_effect
        assert result.get("ambiguous_portfolio_effect") is not True

    def test_fee_in_summary(self):
        """Fee transactions counted in summary."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "fee", "amount": 5.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["fee_transaction_count"] == 1


class TestDividendSemantics:
    def test_dividend_does_not_change_units(self):
        """dividend transaction → dividend_transaction=True, no units field."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "dividend",
            "amount": 10.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "dividend"
        assert result.get("dividend_transaction") is True
        # Dividend should not have units or shares
        assert "units" not in result
        assert "shares" not in result
        # Dividend should not require manual review
        assert result["manual_review_required"] is False

    def test_dividend_in_summary(self):
        """Dividend transactions counted in summary."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "dividend", "amount": 10.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["dividend_transaction_count"] == 1


class TestUnknownSemantics:
    def test_unknown_requires_manual_review(self):
        """unknown transaction → manual_review_required=True."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "mystery",
            "amount": 100.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "unknown"
        assert result["manual_review_required"] is True
        assert "unknown_transaction_type" in result.get("manual_review_reasons", [])

    def test_unknown_in_summary(self):
        """Unknown transactions counted in summary."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "mystery", "amount": 100.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["unknown_count"] == 1


class TestManualReviewRequired:
    def test_buy_no_manual_review(self):
        """Normal buy → no manual review required."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "buy",
            "amount": 100.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["manual_review_required"] is False
        assert result.get("manual_review_reasons") is None

    def test_sell_no_manual_review(self):
        """Normal sell → no manual review required."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "sell",
            "amount": 50.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["manual_review_required"] is False

    def test_validation_warning_also_sets_manual_review_required(self):
        """Validation warnings also set manual_review_required."""
        raw = {
            "trade_date": "bad-date",
            "fund_code": "000001",
            "transaction_type": "buy",
            "amount": 100.0,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["manual_review_required"] is True

    def test_summary_manual_review_required_count(self):
        """Summary counts manual_review_required transactions."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "conversion_in", "amount": 50.0},
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "refund", "amount": 25.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["manual_review_required_count"] == 2
