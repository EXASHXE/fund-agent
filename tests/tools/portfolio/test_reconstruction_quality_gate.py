"""Tests for M7.9 reconstruction quality gate.

Covers:
1. Full reconstruction allows current_value
2. Partial reconstruction blocks portfolio total
3. Snapshot takes precedence over reconstruction
4. Reconstruction value marked estimated not platform_reported
5. No holdings snapshot does not automatically block if reconstruction full
6. Reconstruction quality computation
7. Blocker severity
8. Can output current_value gate
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.valuation_source_model import (
    BLOCKER_SEVERITY_BLOCK,
    BLOCKER_SEVERITY_DEGRADE,
    HOLDINGS_SOURCE_CASHFLOW_ONLY,
    HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT,
    HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL,
    HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL,
    HOLDINGS_SOURCE_UNAVAILABLE,
    POSITION_VALUATION_BLOCKED_IDENTITY,
    POSITION_VALUATION_CONFIRMED,
    POSITION_VALUATION_CASHFLOW_ONLY,
    POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_FULL,
    POSITION_VALUATION_RECONSTRUCTED_ESTIMATED_PARTIAL,
    PORTFOLIO_VALUATION_PLATFORM_SNAPSHOT_FULL,
    PORTFOLIO_VALUATION_TRANSACTION_DERIVED_FULL,
    PORTFOLIO_VALUATION_TRANSACTION_DERIVED_PARTIAL,
    PORTFOLIO_VALUATION_UNAVAILABLE,
    RECONSTRUCTION_BLOCKER_CODE_NAME_MISMATCH,
    RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED,
    RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED,
    RECONSTRUCTION_BLOCKER_MISSING_FEE,
    RECONSTRUCTION_BLOCKER_MISSING_TRADE_NAV,
    RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS,
    RECONSTRUCTION_BLOCKER_QDII_NAV_LAG,
    RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND,
    RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS,
    RECONSTRUCTION_QUALITY_BLOCKED,
    RECONSTRUCTION_QUALITY_CONFIRMED,
    RECONSTRUCTION_QUALITY_ESTIMATED_HIGH,
    RECONSTRUCTION_QUALITY_ESTIMATED_LOW,
    RECONSTRUCTION_QUALITY_ESTIMATED_MEDIUM,
    RECONSTRUCTION_QUALITY_PARTIAL,
    VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS,
    VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE,
    VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV,
    VALUATION_SOURCE_UNAVAILABLE,
    can_output_current_value,
    compute_holdings_source,
    compute_profit_source,
    compute_reconstruction_quality,
    compute_valuation_source_from_holdings,
    get_blocker_severity,
    is_valuation_estimated,
)


class TestReconstructionQuality:
    def test_confirmed_quality(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed", "confirmed"],
            blockers=[],
            units_coverage_ratio=1.0,
            identity_status="verified",
        )
        assert quality == RECONSTRUCTION_QUALITY_CONFIRMED

    def test_estimated_high_quality(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed", "confirmed", "confirmed", "estimated"],
            blockers=[],
            units_coverage_ratio=1.0,
            identity_status="provider_verified",
        )
        assert quality == RECONSTRUCTION_QUALITY_ESTIMATED_HIGH

    def test_estimated_medium_with_degrade_blocker(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed", "confirmed"],
            blockers=[RECONSTRUCTION_BLOCKER_MISSING_FEE],
            units_coverage_ratio=1.0,
            identity_status="verified",
        )
        assert quality == RECONSTRUCTION_QUALITY_ESTIMATED_MEDIUM

    def test_estimated_low_with_multiple_degrade_blockers(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed", "confirmed"],
            blockers=[RECONSTRUCTION_BLOCKER_MISSING_FEE, RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS],
            units_coverage_ratio=1.0,
            identity_status="verified",
        )
        assert quality == RECONSTRUCTION_QUALITY_ESTIMATED_LOW

    def test_partial_quality(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed", "estimated"],
            blockers=[],
            units_coverage_ratio=0.7,
            identity_status="verified",
        )
        assert quality == RECONSTRUCTION_QUALITY_PARTIAL

    def test_blocked_by_identity(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed"],
            blockers=[],
            units_coverage_ratio=1.0,
            identity_status="manual_override_unverified",
        )
        assert quality == RECONSTRUCTION_QUALITY_BLOCKED

    def test_blocked_by_blocker_severity(self):
        quality = compute_reconstruction_quality(
            lot_statuses=["confirmed"],
            blockers=[RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS],
            units_coverage_ratio=1.0,
            identity_status="verified",
        )
        assert quality == RECONSTRUCTION_QUALITY_BLOCKED


class TestBlockerSeverity:
    def test_identity_unverified_is_blocker(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED) == BLOCKER_SEVERITY_BLOCK

    def test_code_name_mismatch_is_blocker(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_CODE_NAME_MISMATCH) == BLOCKER_SEVERITY_BLOCK

    def test_negative_units_is_blocker(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS) == BLOCKER_SEVERITY_BLOCK

    def test_unmatched_refund_is_blocker(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_UNMATCHED_REFUND) == BLOCKER_SEVERITY_BLOCK

    def test_conversion_unverified_is_blocker(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_CONVERSION_UNVERIFIED) == BLOCKER_SEVERITY_BLOCK

    def test_missing_fee_is_degrade(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_MISSING_FEE) == BLOCKER_SEVERITY_DEGRADE

    def test_missing_nav_is_degrade(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_MISSING_TRADE_NAV) == BLOCKER_SEVERITY_DEGRADE

    def test_unknown_semantics_is_degrade(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_UNKNOWN_AMOUNT_SEMANTICS) == BLOCKER_SEVERITY_DEGRADE

    def test_dividend_unmodeled_is_degrade(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_DIVIDEND_UNMODELED) == BLOCKER_SEVERITY_DEGRADE

    def test_qdii_nav_lag_is_degrade(self):
        assert get_blocker_severity(RECONSTRUCTION_BLOCKER_QDII_NAV_LAG) == BLOCKER_SEVERITY_DEGRADE


class TestCanOutputCurrentValue:
    def test_full_reconstruction_allows_current_value(self):
        assert can_output_current_value(
            identity_status="provider_verified",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=1.0,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_CONFIRMED,
        )

    def test_identity_unverified_blocks(self):
        assert not can_output_current_value(
            identity_status="manual_override_unverified",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=1.0,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_CONFIRMED,
        )

    def test_no_units_blocks(self):
        assert not can_output_current_value(
            identity_status="provider_verified",
            total_units=0,
            latest_nav=1.5,
            units_coverage_ratio=1.0,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_CONFIRMED,
        )

    def test_no_nav_blocks(self):
        assert not can_output_current_value(
            identity_status="provider_verified",
            total_units=1000.0,
            latest_nav=None,
            units_coverage_ratio=1.0,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_CONFIRMED,
        )

    def test_partial_coverage_blocks(self):
        assert not can_output_current_value(
            identity_status="provider_verified",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=0.7,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_PARTIAL,
        )

    def test_blocking_blocker_blocks(self):
        assert not can_output_current_value(
            identity_status="provider_verified",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=1.0,
            blockers=[RECONSTRUCTION_BLOCKER_NEGATIVE_UNITS],
            reconstruction_quality=RECONSTRUCTION_QUALITY_ESTIMATED_HIGH,
        )

    def test_user_verified_override_allows(self):
        assert can_output_current_value(
            identity_status="user_verified_override",
            total_units=1000.0,
            latest_nav=1.5,
            units_coverage_ratio=1.0,
            blockers=[],
            reconstruction_quality=RECONSTRUCTION_QUALITY_CONFIRMED,
        )


class TestHoldingsSource:
    def test_snapshot_takes_precedence(self):
        source = compute_holdings_source(
            has_snapshot=True,
            units_coverage_ratio=1.0,
            has_units=True,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT

    def test_full_reconstruction(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=1.0,
            has_units=True,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL

    def test_partial_reconstruction(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=0.7,
            has_units=True,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_TRANSACTION_DERIVED_PARTIAL

    def test_cashflow_only(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=0.0,
            has_units=False,
            has_cost=True,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_CASHFLOW_ONLY

    def test_unavailable(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=0.0,
            has_units=False,
            has_cost=False,
            blockers=[],
        )
        assert source == HOLDINGS_SOURCE_UNAVAILABLE

    def test_blocking_blocker_downgrades(self):
        source = compute_holdings_source(
            has_snapshot=False,
            units_coverage_ratio=1.0,
            has_units=True,
            has_cost=True,
            blockers=[RECONSTRUCTION_BLOCKER_IDENTITY_UNVERIFIED],
        )
        # Identity blocker should prevent full reconstruction
        assert source != HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL


class TestValuationSourceEstimation:
    def test_reconstructed_units_is_estimated(self):
        assert is_valuation_estimated(VALUATION_SOURCE_RECONSTRUCTED_UNITS_LATEST_NAV)

    def test_partial_reconstructed_is_estimated(self):
        assert is_valuation_estimated(VALUATION_SOURCE_PARTIAL_RECONSTRUCTED_UNITS)

    def test_platform_reported_is_not_estimated(self):
        assert not is_valuation_estimated(VALUATION_SOURCE_PLATFORM_REPORTED_CURRENT_VALUE)

    def test_unavailable_is_not_estimated(self):
        assert not is_valuation_estimated(VALUATION_SOURCE_UNAVAILABLE)


class TestProfitSource:
    def test_platform_reported_profit(self):
        source = compute_profit_source(
            has_platform_reported_profit=True,
            holdings_source=HOLDINGS_SOURCE_PLATFORM_REPORTED_SNAPSHOT,
        )
        assert source == "platform_reported_profit"

    def test_reconstructed_cashflow_cost(self):
        source = compute_profit_source(
            has_platform_reported_profit=False,
            holdings_source=HOLDINGS_SOURCE_TRANSACTION_DERIVED_FULL,
        )
        assert source == "reconstructed_cashflow_cost"

    def test_unavailable(self):
        source = compute_profit_source(
            has_platform_reported_profit=False,
            holdings_source=HOLDINGS_SOURCE_CASHFLOW_ONLY,
        )
        assert source == "unavailable"
