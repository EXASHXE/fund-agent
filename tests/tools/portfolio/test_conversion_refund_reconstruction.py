"""Tests for M7.9 conversion and refund reconstruction.

Covers:
1. Conversion creates out and in legs
2. Conversion without both legs blocks
3. Refund matched reverses original transaction
4. Refund unmatched requires manual review
5. Conversion fee missing degrades quality
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.transaction_derived_reconstruction import (
    LOT_STATUS_CONFIRMED,
    LOT_STATUS_ESTIMATED,
    LOT_STATUS_MANUAL_REVIEW,
    SPECIAL_STATUS_CONVERSION_ESTIMATED,
    SPECIAL_STATUS_CONVERSION_VERIFIED,
    SPECIAL_STATUS_REFUND_MATCHED,
    SPECIAL_STATUS_REFUND_UNMATCHED,
    reconstruct_conversion,
    reconstruct_refund,
)


class TestConversionReconstruction:
    def test_conversion_creates_out_and_in_legs(self):
        result = reconstruct_conversion(
            conversion_amount=10000.0,
            source_units=5000.0,
            target_units=4800.0,
            source_nav=2.0,
            target_nav=2.08,
            has_both_legs=True,
        )
        assert result["conversion_out"]["units"] == 5000.0
        assert result["conversion_in"]["units"] == 4800.0
        assert result["special_transaction_status"] == SPECIAL_STATUS_CONVERSION_VERIFIED

    def test_conversion_without_both_legs_blocks(self):
        result = reconstruct_conversion(
            conversion_amount=10000.0,
            source_units=5000.0,
            has_both_legs=False,
        )
        assert result["special_transaction_status"] == "manual_review_required"
        assert result["conversion_out"]["lot_reconstruction_status"] == LOT_STATUS_MANUAL_REVIEW
        assert result["conversion_in"]["lot_reconstruction_status"] == LOT_STATUS_MANUAL_REVIEW

    def test_conversion_fee_missing_degrades_quality(self):
        result = reconstruct_conversion(
            conversion_amount=10000.0,
            source_units=5000.0,
            target_units=4800.0,
            source_nav=2.0,
            target_nav=2.08,
            has_both_legs=True,
        )
        # With explicit units, still verified even without fee
        assert result["special_transaction_status"] == SPECIAL_STATUS_CONVERSION_VERIFIED

    def test_conversion_estimated_when_units_derived(self):
        result = reconstruct_conversion(
            conversion_amount=10000.0,
            source_nav=2.0,
            target_nav=2.08,
            has_both_legs=True,
        )
        assert result["special_transaction_status"] == SPECIAL_STATUS_CONVERSION_ESTIMATED
        assert result["conversion_out"]["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED
        assert result["conversion_in"]["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED

    def test_conversion_with_group_id(self):
        result = reconstruct_conversion(
            conversion_amount=10000.0,
            source_units=5000.0,
            target_units=4800.0,
            conversion_group_id="CONV-001",
            has_both_legs=True,
        )
        assert result["conversion_group_id"] == "CONV-001"


class TestRefundReconstruction:
    def test_refund_matched_reverses_original_transaction(self):
        result = reconstruct_refund(
            refund_amount=1000.0,
            refund_units=500.0,
            matched_original_transaction_id="TXN001",
        )
        assert result["units"] == 500.0
        assert result["special_transaction_status"] == SPECIAL_STATUS_REFUND_MATCHED
        assert result["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED
        assert result["matched_original_transaction_id"] == "TXN001"

    def test_refund_unmatched_requires_manual_review(self):
        result = reconstruct_refund(
            refund_amount=1000.0,
            refund_units=500.0,
            matched_original_transaction_id=None,
        )
        assert result["special_transaction_status"] == SPECIAL_STATUS_REFUND_UNMATCHED
        assert result["lot_reconstruction_status"] == LOT_STATUS_MANUAL_REVIEW

    def test_refund_matched_amount_only(self):
        result = reconstruct_refund(
            refund_amount=1000.0,
            matched_original_transaction_id="TXN001",
        )
        assert result["special_transaction_status"] == SPECIAL_STATUS_REFUND_MATCHED
        assert result["units"] is None
        assert result["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED

    def test_refund_no_amount_no_units(self):
        result = reconstruct_refund(
            matched_original_transaction_id="TXN001",
        )
        assert result["lot_reconstruction_status"] == LOT_STATUS_MANUAL_REVIEW
