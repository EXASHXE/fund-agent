"""Tests for special_transaction_status (M7.2 Stage 6).

Validates that:
1. _determine_special_transaction_status returns correct status for conversion/refund
2. portfolio_input_transactions normalizes special_transaction_status correctly
3. reconstruct_portfolio handles computable/estimated conversion/refund transactions
4. computable conversions/refunds are included in unit calculations
5. ambiguous/manual_review_required conversions/refunds are excluded from units

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

from typing import Any

import pytest

from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio
from src.tools.portfolio.portfolio_input_transactions import (
    _determine_special_transaction_status,
    normalize_portfolio_input_transaction,
)


# ── 1. _determine_special_transaction_status ────────────────────────────


class TestDetermineSpecialTransactionStatus:
    """Test _determine_special_transaction_status logic."""

    def test_conversion_computable_all_fields(self):
        """conversion with source, target, units, nav → computable."""
        result = _determine_special_transaction_status(
            "conversion",
            {"source_fund_code": "000001", "target_fund_code": "000002", "units": 100, "nav": 1.5},
        )
        assert result == "computable"

    def test_conversion_computable_from_to_fields(self):
        """conversion with from_fund_code, to_fund_code → computable."""
        result = _determine_special_transaction_status(
            "conversion",
            {"from_fund_code": "000001", "to_fund_code": "000002", "units": 100, "nav": 1.5},
        )
        assert result == "computable"

    def test_conversion_estimated_partial_data(self):
        """conversion with source and units but no target → estimated."""
        result = _determine_special_transaction_status(
            "conversion",
            {"source_fund_code": "000001", "units": 100},
        )
        assert result == "estimated"

    def test_conversion_ambiguous_source_only(self):
        """conversion with source only → ambiguous."""
        result = _determine_special_transaction_status(
            "conversion",
            {"source_fund_code": "000001"},
        )
        assert result == "ambiguous"

    def test_conversion_manual_review_no_data(self):
        """conversion with no identifying data → manual_review_required."""
        result = _determine_special_transaction_status(
            "conversion",
            {},
        )
        assert result == "manual_review_required"

    def test_refund_computable_all_fields(self):
        """refund with amount, reference, units → computable."""
        result = _determine_special_transaction_status(
            "refund",
            {"amount": 1000, "refund_reference": "REF001", "units": 50},
        )
        assert result == "computable"

    def test_refund_computable_original_transaction_id(self):
        """refund with original_transaction_id → computable."""
        result = _determine_special_transaction_status(
            "refund",
            {"amount": 1000, "original_transaction_id": "TXN001", "units": 50},
        )
        assert result == "computable"

    def test_refund_estimated_amount_and_ref(self):
        """refund with amount and reference but no units → estimated."""
        result = _determine_special_transaction_status(
            "refund",
            {"amount": 1000, "refund_reference": "REF001"},
        )
        assert result == "estimated"

    def test_refund_ambiguous_amount_only(self):
        """refund with amount only → ambiguous."""
        result = _determine_special_transaction_status(
            "refund",
            {"amount": 1000},
        )
        assert result == "ambiguous"

    def test_refund_manual_review_no_data(self):
        """refund with no data → manual_review_required."""
        result = _determine_special_transaction_status(
            "refund",
            {},
        )
        assert result == "manual_review_required"

    def test_non_conversion_non_refund_returns_manual_review(self):
        """Any other action type returns manual_review_required."""
        result = _determine_special_transaction_status("buy", {})
        assert result == "manual_review_required"


# ── 2. normalize_portfolio_input_transaction includes special_transaction_status ──


class TestNormalizePortfolioInputTransactionSpecialStatus:
    """normalize_portfolio_input_transaction must include special_transaction_status
    for conversion/refund transactions."""

    def test_conversion_in_gets_special_status(self):
        raw = {
            "trade_date": "2025-01-15",
            "transaction_type": "conversion_in",
            "amount": 1000.0,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "source_fund_code": "000001",
            "target_fund_code": "000002",
            "units": 100,
            "nav": 1.5,
        }
        entry = normalize_portfolio_input_transaction(raw, 0)
        assert entry["action"] == "conversion"
        assert entry["special_transaction_status"] == "computable"
        assert entry.get("ambiguous_portfolio_effect") is True

    def test_conversion_out_gets_special_status(self):
        raw = {
            "trade_date": "2025-01-15",
            "transaction_type": "conversion_out",
            "amount": 1000.0,
            "fund_code": "000002",
            "fund_name": "Test Fund B",
            "from_fund_code": "000001",
            "to_fund_code": "000002",
            "units": 100,
            "nav": 1.5,
        }
        entry = normalize_portfolio_input_transaction(raw, 0)
        assert entry["action"] == "conversion"
        assert entry["special_transaction_status"] == "computable"

    def test_refund_computable_in_normalized(self):
        raw = {
            "trade_date": "2025-01-15",
            "transaction_type": "refund",
            "amount": 500.0,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "refund_reference": "REF001",
            "units": 50,
        }
        entry = normalize_portfolio_input_transaction(raw, 0)
        assert entry["action"] == "refund"
        assert entry["special_transaction_status"] == "computable"

    def test_conversion_ambiguous_no_manual_review(self):
        """conversion with special_transaction_status=ambiguous should have
        manual_review_required=True (insufficient data)."""
        raw = {
            "trade_date": "2025-01-15",
            "transaction_type": "conversion_in",
            "amount": 1000.0,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "source_fund_code": "000001",
        }
        entry = normalize_portfolio_input_transaction(raw, 0)
        assert entry["special_transaction_status"] == "ambiguous"
        assert entry["manual_review_required"] is True

    def test_conversion_computable_no_forced_manual_review(self):
        """conversion with special_transaction_status=computable should NOT
        have manual_review_required forced by the action alone."""
        raw = {
            "trade_date": "2025-01-15",
            "transaction_type": "conversion_in",
            "amount": 1000.0,
            "fund_code": "000001",
            "fund_name": "Test Fund",
            "source_fund_code": "000001",
            "target_fund_code": "000002",
            "units": 100,
            "nav": 1.5,
        }
        entry = normalize_portfolio_input_transaction(raw, 0)
        assert entry["special_transaction_status"] == "computable"
        # computable should NOT force manual_review_required from the action
        assert "ambiguous_portfolio_effect: conversion" not in entry.get("manual_review_reasons", [])

    def test_buy_has_no_special_status(self):
        """Buy transactions should not have special_transaction_status."""
        raw = {
            "trade_date": "2025-01-15",
            "transaction_type": "buy",
            "amount": 1000.0,
            "fund_code": "000001",
            "fund_name": "Test Fund",
        }
        entry = normalize_portfolio_input_transaction(raw, 0)
        assert "special_transaction_status" not in entry


# ── 3. Reconstruction handles computable conversion ─────────────────────


class TestReconstructionComputableConversion:
    """reconstruct_portfolio must include computable conversions in unit calculations."""

    def _make_nav(self, fund_code: str = "000001") -> dict[str, Any]:
        return {
            "nav_by_fund": {
                fund_code: {
                    "records": [
                        {"date": "2025-01-15", "nav": 1.0},
                        {"date": "2025-06-01", "nav": 1.05},
                    ],
                },
            },
        }

    def test_computable_conversion_out_adds_units(self):
        """conversion_out with computable status should add units to target fund."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000002",
                    "fund_name": "Target Fund",
                    "action": "conversion",
                    "transaction_type": "conversion_out",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "computable",
                    "units": 500.0,
                },
            ],
        }
        nav = {
            "nav_by_fund": {
                "000002": {
                    "records": [
                        {"date": "2025-02-01", "nav": 2.0},
                        {"date": "2025-06-01", "nav": 2.1},
                    ],
                },
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["fund_code"] == "000002"
        # Units should be 500 from the conversion
        assert pos["units"] == 500.0
        assert pos["valuation_type"] == "estimated"
        assert "conversion_computable" in pos.get("confirmation_sources", [])

    def test_computable_conversion_in_subtracts_units(self):
        """conversion_in with computable status should subtract units from source fund."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Source Fund",
                    "action": "buy",
                    "amount": 2000.0,
                    "net_amount": 2000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Source Fund",
                    "action": "conversion",
                    "transaction_type": "conversion_in",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "computable",
                    "units": 500.0,
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        # Buy gives 2000 units, conversion_in removes 500 → 1500
        assert pos["units"] == 1500.0

    def test_estimated_conversion_adds_units_with_flag(self):
        """estimated conversion should add units but set data quality flag."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000002",
                    "fund_name": "Target Fund",
                    "action": "conversion",
                    "transaction_type": "conversion_out",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "estimated",
                    "units": 500.0,
                },
            ],
        }
        nav = {
            "nav_by_fund": {
                "000002": {
                    "records": [
                        {"date": "2025-02-01", "nav": 2.0},
                        {"date": "2025-06-01", "nav": 2.1},
                    ],
                },
            },
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["units"] == 500.0
        assert "conversion_or_refund_estimated" in pos.get("data_quality", [])
        assert "conversion_estimated" in pos.get("confirmation_sources", [])

    def test_ambiguous_conversion_excluded_from_units(self):
        """ambiguous conversion should still be excluded from unit calculations."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "conversion",
                    "transaction_type": "conversion_in",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "ambiguous",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        # Only the buy should contribute to units
        assert pos["units"] == 1000.0
        assert pos["has_manual_review"] is True

    def test_no_special_status_conversion_excluded(self):
        """conversion without special_transaction_status defaults to manual review."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 1000.0,
                    "net_amount": 1000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "conversion",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    # No special_transaction_status → defaults to manual_review_required
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        pos = positions[0]
        # Only the buy should contribute to units
        assert pos["units"] == 1000.0
        assert pos["has_manual_review"] is True


# ── 4. Reconstruction handles computable refund ─────────────────────────


class TestReconstructionComputableRefund:
    """reconstruct_portfolio must include computable refunds in unit calculations."""

    def _make_nav(self, fund_code: str = "000001") -> dict[str, Any]:
        return {
            "nav_by_fund": {
                fund_code: {
                    "records": [
                        {"date": "2025-01-15", "nav": 1.0},
                        {"date": "2025-06-01", "nav": 1.05},
                    ],
                },
            },
        }

    def test_computable_refund_adds_units(self):
        """computable refund should add units back to the position."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 2000.0,
                    "net_amount": 2000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "refund",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "computable",
                    "units": 200.0,
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        # Buy gives 2000 units, refund adds 200 → 2200
        assert pos["units"] == 2200.0
        assert "refund_computable" in pos.get("confirmation_sources", [])

    def test_computable_refund_amount_only(self):
        """computable refund with amount but no units → adds to cost only."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 2000.0,
                    "net_amount": 2000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "refund",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "computable",
                    # No units field
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        pos = positions[0]
        # Buy gives 2000 units; refund adds cost but no units
        assert pos["units"] == 2000.0
        # Cost should be 2000 + 500 = 2500
        assert pos["cost_basis"] == 2500.0

    def test_estimated_refund_adds_units_with_flag(self):
        """estimated refund should add units but set data quality flag."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 2000.0,
                    "net_amount": 2000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "refund",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "estimated",
                    "units": 200.0,
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        pos = positions[0]
        assert pos["units"] == 2200.0
        assert "conversion_or_refund_estimated" in pos.get("data_quality", [])
        assert "refund_estimated" in pos.get("confirmation_sources", [])

    def test_ambiguous_refund_excluded_from_units(self):
        """ambiguous refund should be excluded from unit calculations."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "buy",
                    "amount": 2000.0,
                    "net_amount": 2000.0,
                    "trade_date": "2025-01-15",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "refund",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "ambiguous",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        pos = positions[0]
        # Only the buy should contribute to units
        assert pos["units"] == 2000.0
        assert pos["has_manual_review"] is True

    def test_computable_refund_creates_no_reconstruction_note(self):
        """computable refund should NOT create a 'requires manual review' note."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "refund",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "computable",
                    "units": 200.0,
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        notes = result["reconstruction_notes"]
        refund_notes = [n for n in notes if "refund" in n.get("note", "").lower()]
        assert len(refund_notes) == 0

    def test_manual_review_refund_creates_reconstruction_note(self):
        """manual_review_required refund should create a reconstruction note."""
        ledger = {
            "transactions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "action": "refund",
                    "amount": 500.0,
                    "trade_date": "2025-02-01",
                    "confirmation_type": "evidence_confirmed",
                    "confirmation_source": "alipay",
                    "special_transaction_status": "manual_review_required",
                },
            ],
        }
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=self._make_nav(),
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        notes = result["reconstruction_notes"]
        refund_notes = [n for n in notes if "refund" in n.get("note", "").lower()]
        assert len(refund_notes) >= 1
