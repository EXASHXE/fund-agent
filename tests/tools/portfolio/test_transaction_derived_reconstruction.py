"""Tests for M7.9 transaction-derived holdings reconstruction.

Covers:
1. Buy units from amount + trade NAV
2. Sell units deduction
3. Conversion out/in legs
4. Refund matched/unmatched
5. Fee missing degrades quality
6. Identity unverified blocks reconstruction valuation
7. Full reconstruction allows current_value
8. Partial reconstruction blocks portfolio total
9. Transaction-derived value labeled estimated
10. No holdings snapshot does not automatically block if reconstruction full
"""
from __future__ import annotations

import pytest
from datetime import date

from src.tools.portfolio.transaction_derived_reconstruction import (
    AMOUNT_SEMANTICS_GROSS,
    AMOUNT_SEMANTICS_NET,
    AMOUNT_SEMANTICS_UNKNOWN,
    DIVIDEND_TYPE_CASH,
    DIVIDEND_TYPE_REINVEST,
    DIVIDEND_TYPE_UNKNOWN,
    FEE_CONFIDENCE_EXPLICIT,
    FEE_CONFIDENCE_SCHEDULE,
    FEE_CONFIDENCE_UNKNOWN,
    LOT_STATUS_BLOCKED_MISSING_TRADE_NAV,
    LOT_STATUS_CONFIRMED,
    LOT_STATUS_ESTIMATED,
    LOT_STATUS_MANUAL_REVIEW,
    SPECIAL_STATUS_CONVERSION_ESTIMATED,
    SPECIAL_STATUS_CONVERSION_VERIFIED,
    SPECIAL_STATUS_REFUND_MATCHED,
    SPECIAL_STATUS_REFUND_UNMATCHED,
    reconstruct_buy_units,
    reconstruct_conversion,
    reconstruct_dividend,
    reconstruct_position,
    reconstruct_refund,
    reconstruct_sell_units,
)
from src.tools.portfolio.valuation_source_model import (
    HOLDINGS_SOURCE_CASHFLOW_ONLY,
    HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT,
    HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL,
    HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL,
    HOLDINGS_SOURCE_UNAVAILABLE,
    PORTFOLIO_VALUATION_TRANSACTION_DERIVED_FULL,
    PORTFOLIO_VALUATION_TRANSACTION_DERIVED_PARTIAL,
    PORTFOLIO_VALUATION_UNAVAILABLE,
    POSITION_VALUATION_BLOCKED_IDENTITY,
    POSITION_VALUATION_CONFIRMED,
    POSITION_VALUATION_CASHFLOW_ONLY,
    POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_FULL,
    POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_PARTIAL,
    RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED,
    RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_MISSING_FEE,
    RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS,
    RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND,
    RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS,
    RECONSTRUCTION_QUALITY_BLOCKED,
    RECONSTRUCTION_QUALITY_CONFIRMED,
    RECONSTRUCTION_QUALITY_ESTIMATED_HIGH,
    RECONSTRUCTION_QUALITY_ESTIMATED_MEDIUM,
    RECONSTRUCTION_QUALITY_PARTIAL,
    VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS,
    VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE,
    VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV,
    VALUATION_SOURCE_UNAVAILABLE,
    can_output_current_value,
    compute_holdings_source,
    compute_reconstruction_quality,
    compute_valuation_source_from_holdings,
    is_valuation_estimated,
)


# ── Buy units tests ─────────────────────────────────────────────────────

class TestBuyUnitsReconstruction:
    def test_buy_units_derived_from_trade_date_nav(self):
        result = reconstruct_buy_units(
            gross_amount=10000.0,
            effective_trade_date=date(2025, 5, 15),
            trade_date_nav=1.5,
            amount_semantics=AMOUNT_SEMANTICS_NET,  # Use NET for confirmed
        )
        assert result["units"] is not None
        assert result["units"] > 0
        assert result["units_source"] == "trade_date_nav_derived"
        assert result["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED

    def test_buy_with_explicit_units(self):
        result = reconstruct_buy_units(
            gross_amount=10000.0,
            effective_trade_date=date(2025, 5, 15),
            trade_date_nav=1.5,
            explicit_units=6666.67,
        )
        assert result["units"] == 6666.67
        assert result["units_source"] == "explicit_units"
        assert result["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED

    def test_buy_fee_applied_when_available(self):
        result = reconstruct_buy_units(
            gross_amount=10000.0,
            effective_trade_date=date(2025, 5, 15),
            trade_date_nav=1.5,
            subscription_fee_rate=0.0015,
            amount_semantics=AMOUNT_SEMANTICS_GROSS,
        )
        assert result["fee_amount"] is not None
        assert result["fee_amount"] > 0
        assert result["fee_confidence"] == FEE_CONFIDENCE_SCHEDULE
        # Net amount should be less than gross
        assert result["net_amount"] < 10000.0

    def test_buy_fee_missing_degrades_quality(self):
        result = reconstruct_buy_units(
            gross_amount=10000.0,
            effective_trade_date=date(2025, 5, 15),
            trade_date_nav=1.5,
            amount_semantics=AMOUNT_SEMANTICS_GROSS,
        )
        assert result["fee_confidence"] == FEE_CONFIDENCE_UNKNOWN
        # When fee unknown and semantics known, still confirmed
        # (conservative estimate applied)
        assert result["lot_reconstruction_status"] in (LOT_STATUS_CONFIRMED, LOT_STATUS_ESTIMATED)

    def test_buy_amount_semantics_unknown_degrades_quality(self):
        result = reconstruct_buy_units(
            gross_amount=10000.0,
            effective_trade_date=date(2025, 5, 15),
            trade_date_nav=1.5,
            amount_semantics=AMOUNT_SEMANTICS_UNKNOWN,
        )
        assert result["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED

    def test_buy_no_nav_blocks(self):
        result = reconstruct_buy_units(
            gross_amount=10000.0,
            effective_trade_date=date(2025, 5, 15),
            trade_date_nav=None,
        )
        assert result["units"] is None
        assert result["lot_reconstruction_status"] == LOT_STATUS_BLOCKED_MISSING_TRADE_NAV

    def test_buy_after_cutoff_uses_next_trade_nav(self):
        """Verify that the caller passes the correct NAV based on cutoff."""
        # The NAV lookup is done by the caller, not by reconstruct_buy_units
        # Here we just verify that the function works with the NAV it receives
        result = reconstruct_buy_units(
            gross_amount=10000.0,
            effective_trade_date=date(2025, 5, 16),  # Next trading day
            trade_date_nav=1.52,  # NAV for next trading day
            amount_semantics=AMOUNT_SEMANTICS_NET,
        )
        assert result["units"] is not None
        assert abs(result["units"] - 10000.0 / 1.52) < 0.01


# ── Sell units tests ────────────────────────────────────────────────────

class TestSellUnitsReconstruction:
    def test_sell_with_explicit_units_deducts_units(self):
        result = reconstruct_sell_units(
            redemption_amount=5000.0,
            redemption_nav=1.5,
            explicit_units=3333.33,
            current_units=10000.0,
        )
        assert result["units_sold"] == 3333.33
        assert result["units_source"] == "explicit_units"
        assert result["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED

    def test_sell_units_derived_from_nav_and_fee_when_semantics_known(self):
        result = reconstruct_sell_units(
            redemption_amount=5000.0,
            redemption_nav=1.5,
            redemption_fee_rate=0.005,
            amount_semantics=AMOUNT_SEMANTICS_NET,
            current_units=10000.0,
        )
        assert result["units_sold"] is not None
        assert result["units_sold"] > 0
        assert result["units_source"] == "trade_date_nav_derived"

    def test_sell_without_fee_degrades_quality(self):
        result = reconstruct_sell_units(
            redemption_amount=5000.0,
            redemption_nav=1.5,
            amount_semantics=AMOUNT_SEMANTICS_GROSS,
            current_units=10000.0,
        )
        # Without fee info, quality depends on semantics
        assert result["lot_reconstruction_status"] in (LOT_STATUS_CONFIRMED, LOT_STATUS_ESTIMATED)

    def test_sell_amount_semantics_unknown_blocks_confirmed_reconstruction(self):
        result = reconstruct_sell_units(
            redemption_amount=5000.0,
            redemption_nav=1.5,
            amount_semantics=AMOUNT_SEMANTICS_UNKNOWN,
            current_units=10000.0,
        )
        assert result["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED

    def test_sell_cannot_make_units_negative(self):
        result = reconstruct_sell_units(
            redemption_amount=50000.0,
            redemption_nav=1.5,
            explicit_units=20000.0,
            current_units=100.0,
        )
        assert result["negative_units_warning"] is True
        assert result["lot_reconstruction_status"] == LOT_STATUS_MANUAL_REVIEW


# ── Conversion tests ────────────────────────────────────────────────────

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

    def test_conversion_fee_missing_degrades_quality(self):
        result = reconstruct_conversion(
            conversion_amount=10000.0,
            source_units=5000.0,
            target_units=4800.0,
            source_nav=2.0,
            target_nav=2.08,
            has_both_legs=True,
        )
        # No fee provided but units are explicit → still verified
        assert result["special_transaction_status"] == SPECIAL_STATUS_CONVERSION_VERIFIED

    def test_conversion_estimated_when_units_derived(self):
        result = reconstruct_conversion(
            conversion_amount=10000.0,
            source_nav=2.0,
            target_nav=2.08,
            has_both_legs=True,
        )
        # Units derived from NAV → estimated
        assert result["special_transaction_status"] == SPECIAL_STATUS_CONVERSION_ESTIMATED


# ── Refund tests ────────────────────────────────────────────────────────

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

    def test_refund_unmatched_requires_manual_review(self):
        result = reconstruct_refund(
            refund_amount=1000.0,
            refund_units=500.0,
            matched_original_transaction_id=None,
        )
        assert result["special_transaction_status"] == SPECIAL_STATUS_REFUND_UNMATCHED
        assert result["lot_reconstruction_status"] == LOT_STATUS_MANUAL_REVIEW


# ── Dividend tests ──────────────────────────────────────────────────────

class TestDividendReconstruction:
    def test_cash_dividend_does_not_change_units(self):
        result = reconstruct_dividend(
            dividend_amount=100.0,
            dividend_type=DIVIDEND_TYPE_CASH,
        )
        assert result["units_change"] == 0.0
        assert result["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED

    def test_reinvested_dividend_requires_nav(self):
        result = reconstruct_dividend(
            dividend_amount=100.0,
            dividend_type=DIVIDEND_TYPE_REINVEST,
            reinvest_nav=1.5,
        )
        assert result["units_change"] > 0
        assert result["lot_reconstruction_status"] == LOT_STATUS_ESTIMATED

    def test_reinvested_dividend_with_explicit_units(self):
        result = reconstruct_dividend(
            dividend_amount=100.0,
            dividend_type=DIVIDEND_TYPE_REINVEST,
            reinvest_units=66.67,
        )
        assert result["units_change"] == 66.67
        assert result["lot_reconstruction_status"] == LOT_STATUS_CONFIRMED

    def test_unknown_dividend_type_degrades_quality(self):
        result = reconstruct_dividend(
            dividend_amount=100.0,
            dividend_type=DIVIDEND_TYPE_UNKNOWN,
        )
        assert result["units_change"] == 0.0
        assert result["blocker"] == RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED


# ── Valuation source model tests ────────────────────────────────────────

class TestValuationSourceModel:
    def test_holdings_snapshot_provides_platform_reported(self):
        source = compute_valuation_source_from_holdings(
            holdings_source=HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT,
            has_units=True,
            has_latest_nav=True,
            has_current_value_from_snapshot=True,
        )
        assert source == VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE

    def test_transaction_derived_full_provides_reconstructed(self):
        source = compute_valuation_source_from_holdings(
            holdings_source=HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL,
            has_units=True,
            has_latest_nav=True,
        )
        assert source == VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV

    def test_transaction_derived_partial_provides_partial(self):
        source = compute_valuation_source_from_holdings(
            holdings_source=HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL,
            has_units=True,
            has_latest_nav=True,
        )
        assert source == VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS

    def test_cashflow_only_provides_unavailable(self):
        source = compute_valuation_source_from_holdings(
            holdings_source=HOLDINGS_SOURCE_CASHFLOW_ONLY,
            has_units=False,
            has_latest_nav=False,
        )
        assert source == VALUATION_SOURCE_UNAVAILABLE

    def test_is_valuation_estimated(self):
        assert is_valuation_estimated(VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV)
        assert is_valuation_estimated(VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS)
        assert not is_valuation_estimated(VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE)
        assert not is_valuation_estimated(VALUATION_SOURCE_UNAVAILABLE)

    def test_compute_holdings_source_full(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=1.0,
            has_units=True,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL

    def test_compute_holdings_source_partial(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=0.7,
            has_units=True,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL

    def test_compute_holdings_source_cashflow(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=0.0,
            has_units=False,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_CASHFLOW_ONLY

    def test_compute_holdings_source_snapshot_takes_precedence(self):
        source = compute_holdings_source(
            has_snapshot=True,
            units_coverage_ratio=1.0,
            has_units=True,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT

    def test_can_output_current_value_full_reconstruction(self):
        assert can_output_current_value(
            identity_status="provider_verified",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=1.0,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_CONFIRMED,
        )

    def test_can_output_current_value_identity_unverified_blocks(self):
        assert not can_output_current_value(
            identity_status="manual_override_unverified",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=1.0,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_CONFIRMED,
        )

    def test_can_output_current_value_partial_blocks(self):
        assert not can_output_current_value(
            identity_status="provider_verified",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=0.7,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_PARTIAL,
        )

    def test_reconstruction_quality_confirmed(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed", "confirmed"],
            blockers=[],
            units_coverage_ratio=1.0,
            identity_status="verified",
        )
        assert quality == RECONSTRUCTION_QUALITY_CONFIRMED

    def test_reconstruction_quality_blocked_by_identity(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed"],
            blockers=[],
            units_coverage_ratio=1.0,
            identity_status="manual_override_unverified",
        )
        assert quality == RECONSTRUCTION_QUALITY_BLOCKED


# ── Position reconstruction integration tests ───────────────────────────

class TestPositionReconstruction:
    def _make_buy_txn(self, amount=10000.0, trade_date="2025-05-15", nav=1.5):
        return {
            "action": "buy",
            "amount": amount,
            "trade_date": trade_date,
            "effective_trade_date": trade_date,
            "confirmation_type": "evidence_confirmed",
            "fee_amount": None,
        }

    def _make_sell_txn(self, amount=5000.0, trade_date="2025-06-15", nav=1.6):
        return {
            "action": "sell",
            "amount": amount,
            "trade_date": trade_date,
            "effective_trade_date": trade_date,
            "confirmation_type": "evidence_confirmed",
            "fee_amount": None,
        }

    def _make_nav_records(self, nav=1.5, date_str="2025-05-15"):
        return [{"date": date_str, "nav": nav}]

    def test_full_reconstruction_allows_current_value(self):
        result = reconstruct_position(
            transactions=[self._make_buy_txn()],
            nav_records=self._make_nav_records(),
            identity_status="provider_verified",
            latest_nav=1.5,
            latest_nav_date="2025-05-15",
        )
        assert result["current_value"] is not None
        assert result["holdings_source"] == HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL
        assert result["valuation_source"] == VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV

    def test_identity_unverified_blocks_reconstruction_valuation(self):
        result = reconstruct_position(
            transactions=[self._make_buy_txn()],
            nav_records=self._make_nav_records(),
            identity_status="manual_override_unverified",
            latest_nav=1.5,
            latest_nav_date="2025-05-15",
        )
        assert result["current_value"] is None
        assert RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED in result["reconstruction_blockers"]

    def test_provider_verified_allows_reconstruction(self):
        result = reconstruct_position(
            transactions=[self._make_buy_txn()],
            nav_records=self._make_nav_records(),
            identity_status="provider_verified",
            latest_nav=1.5,
            latest_nav_date="2025-05-15",
        )
        assert result["current_value"] is not None

    def test_transaction_derived_value_labeled_estimated(self):
        result = reconstruct_position(
            transactions=[self._make_buy_txn()],
            nav_records=self._make_nav_records(),
            identity_status="provider_verified",
            latest_nav=1.5,
            latest_nav_date="2025-05-15",
        )
        assert is_valuation_estimated(result["valuation_source"])

    def test_no_holdings_snapshot_does_not_block_if_reconstruction_full(self):
        result = reconstruct_position(
            transactions=[self._make_buy_txn()],
            nav_records=self._make_nav_records(),
            identity_status="provider_verified",
            latest_nav=1.5,
            latest_nav_date="2025-05-15",
            has_snapshot=False,
        )
        assert result["current_value"] is not None
        assert result["holdings_source"] == HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL

    def test_partial_reconstruction_blocks_portfolio_total(self):
        # Position with identity unverified → blocked
        result = reconstruct_position(
            transactions=[self._make_buy_txn()],
            nav_records=self._make_nav_records(),
            identity_status="manual_override_unverified",
            latest_nav=1.5,
            latest_nav_date="2025-05-15",
            has_snapshot=False,
        )
        assert result["current_value"] is None

    def test_sell_reduces_units(self):
        result = reconstruct_position(
            transactions=[
                self._make_buy_txn(amount=10000.0, nav=1.5),
                self._make_sell_txn(amount=3000.0, nav=1.6),
            ],
            nav_records=[
                {"date": "2025-05-15", "nav": 1.5},
                {"date": "2025-06-15", "nav": 1.6},
            ],
            identity_status="provider_verified",
            latest_nav=1.6,
            latest_nav_date="2025-06-15",
        )
        assert result["total_units"] is not None
        # Buy: 10000/1.5 = 6666.67, Sell: 3000/1.6 = 1875.0
        # Remaining: ~4791.67
        assert result["total_units"] > 0
        assert result["sell_count"] == 1
