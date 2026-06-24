"""Tests for NAV coverage quality diagnostics.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.tools.portfolio.nav_coverage import (
    DOMESTIC_STALE_THRESHOLD_DAYS,
    QDII_STALE_THRESHOLD_DAYS,
    compute_nav_coverage,
    compute_portfolio_nav_coverage,
)


class TestComputeNavCoverage:
    def test_full_trade_date_nav_coverage(self):
        """buy/sell with trade-date NAV → coverage_status=full, valuation_quality=estimated_full_coverage."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
            {"action": "sell", "trade_date": "2026-06-15", "amount": 50.0},
        ]
        nav_records = [
            {"date": "2026-06-01", "nav": 1.2345},
            {"date": "2026-06-15", "nav": 1.2500},
            {"date": "2026-06-20", "nav": 1.2600},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["coverage_status"] == "full"
        assert result["valuation_quality"] == "estimated_full_coverage"
        assert result["trade_nav_coverage_ratio"] == 1.0
        assert result["trades_missing_trade_date_nav"] == 0

    def test_partial_trade_date_nav_coverage(self):
        """Some trades missing NAV → coverage_status=partial, valuation_quality=estimated_partial_coverage."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
            {"action": "buy", "trade_date": "2026-06-10", "amount": 200.0},
        ]
        nav_records = [
            {"date": "2026-06-01", "nav": 1.2345},
            # Missing 2026-06-10
            {"date": "2026-06-20", "nav": 1.2600},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["coverage_status"] == "partial"
        assert result["valuation_quality"] == "estimated_partial_coverage"
        assert result["trades_missing_trade_date_nav"] == 1

    def test_latest_nav_only_does_not_infer_units(self):
        """amount + latest_nav but no trade-date NAV and no explicit units → cashflow_only."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
        ]
        nav_records = [
            {"date": "2026-06-20", "nav": 1.2600},  # Only latest, not trade-date
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["coverage_status"] == "latest_only"
        assert result["valuation_quality"] == "cashflow_only"

    def test_explicit_units_without_trade_nav(self):
        """User-provided units → NAV coverage gap still visible but coverage_status=full."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0, "units": 81.0},
        ]
        nav_records = [
            {"date": "2026-06-20", "nav": 1.2600},  # Latest only
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["trades_with_explicit_units"] == 1
        # Coverage is full because explicit units don't need NAV
        assert result["coverage_status"] == "full"
        # NAV gap is still recorded in nav_gap_count
        assert result["trades_nav_gap_count"] == 1
        # trades_missing_trade_date_nav is 0 because explicit units cover the need
        assert result["trades_missing_trade_date_nav"] == 0

    def test_qdii_stale_nav_warning(self):
        """QDII-like fund with stale NAV → stale warning with QDII threshold."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0, "units": 81.0},
        ]
        # NAV is 9 days old — domestic threshold (7) would flag, QDII threshold (10) would not
        nav_records = [
            {"date": "2026-06-11", "nav": 1.2345},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
            is_qdii_like=True,
        )
        assert result["is_qdii_like"] is True
        # 9 days stale, QDII threshold is 10 → NOT stale for QDII
        assert result["latest_nav_stale_days"] is None

        # Now test with 11 days stale → QDII threshold exceeded
        nav_records_stale = [
            {"date": "2026-06-09", "nav": 1.2345},
        ]
        result2 = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records_stale,
            as_of_date=date(2026, 6, 20),
            is_qdii_like=True,
        )
        assert result2["latest_nav_stale_days"] == 11
        assert any("stale" in w for w in result2["warnings"])

    def test_domestic_stale_nav_warning(self):
        """Non-QDII fund with stale NAV → stale warning with domestic threshold."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0, "units": 81.0},
        ]
        # NAV is 8 days old — exceeds domestic threshold of 7
        nav_records = [
            {"date": "2026-06-12", "nav": 1.2345},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
            is_qdii_like=False,
        )
        assert result["latest_nav_stale_days"] == 8
        assert any("stale" in w for w in result["warnings"])

    def test_no_nav_records(self):
        """No NAV records at all → coverage_status=none."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=None,
            as_of_date=date(2026, 6, 20),
        )
        assert result["coverage_status"] == "none"
        assert result["valuation_quality"] == "unavailable"
        assert result["latest_nav_available"] is False

    def test_dividend_fee_not_counted_in_nav_coverage(self):
        """dividend/fee do not require NAV for coverage calculation."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
            {"action": "dividend", "trade_date": "2026-06-15", "amount": 5.0},
            {"action": "fee", "trade_date": "2026-06-16", "amount": 1.0},
        ]
        nav_records = [
            {"date": "2026-06-01", "nav": 1.2345},
            {"date": "2026-06-20", "nav": 1.2600},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        # Only buy is counted in trade_count
        assert result["trade_count"] == 1
        assert result["coverage_status"] == "full"

    def test_conversion_requires_manual_review(self):
        """conversion transactions → manual_review_required."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
            {"action": "conversion", "trade_date": "2026-06-15", "amount": 50.0},
        ]
        nav_records = [
            {"date": "2026-06-01", "nav": 1.2345},
            {"date": "2026-06-20", "nav": 1.2600},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["valuation_quality"] == "manual_review_required"
        assert any("manual review" in w for w in result["warnings"])

    def test_refund_requires_manual_review(self):
        """refund transactions → manual_review_required."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
            {"action": "refund", "trade_date": "2026-06-15", "amount": 50.0},
        ]
        nav_records = [
            {"date": "2026-06-01", "nav": 1.2345},
            {"date": "2026-06-20", "nav": 1.2600},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["valuation_quality"] == "manual_review_required"

    def test_no_trades(self):
        """No buy/sell transactions → coverage_status=none."""
        txns = [
            {"action": "dividend", "trade_date": "2026-06-15", "amount": 5.0},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=None,
            as_of_date=date(2026, 6, 20),
        )
        assert result["trade_count"] == 0
        assert result["coverage_status"] == "none"

    def test_warnings_no_sensitive_content(self):
        """Warning text must not contain real fund names or amounts."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
            {"action": "conversion", "trade_date": "2026-06-15", "amount": 50.0},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=None,
            as_of_date=date(2026, 6, 20),
        )
        warning_text = " ".join(result["warnings"])
        assert "000001" not in warning_text
        assert "100.0" not in warning_text
        assert "50.0" not in warning_text


class TestComputePortfolioNavCoverage:
    def test_basic_summary(self):
        """Portfolio-level NAV coverage summary from positions."""
        positions = [
            {
                "valuation_type": "estimated",
                "valuation_quality": "estimated_full_coverage",
                "nav_coverage_status": "full",
                "current_value": 1000.0,
                "latest_nav_stale_days": None,
                "is_qdii_like": False,
            },
            {
                "valuation_type": "cashflow_only",
                "valuation_quality": "cashflow_only",
                "nav_coverage_status": "none",
                "current_value": None,
                "latest_nav_stale_days": None,
                "is_qdii_like": False,
            },
        ]
        result = compute_portfolio_nav_coverage(positions)
        assert result["positions_total"] == 2
        assert result["positions_estimated"] == 1
        assert result["positions_cashflow_only"] == 1
        assert result["nav_coverage_full_count"] == 1
        assert result["nav_coverage_none_count"] == 1
        assert result["estimated_current_value_total"] == 1000.0
        assert result["estimated_current_value_total_is_partial"] is True

    def test_full_coverage_not_partial(self):
        """When all positions have valuation, total is not partial."""
        positions = [
            {
                "valuation_type": "estimated",
                "valuation_quality": "estimated_full_coverage",
                "nav_coverage_status": "full",
                "current_value": 1000.0,
                "latest_nav_stale_days": None,
                "is_qdii_like": False,
            },
        ]
        result = compute_portfolio_nav_coverage(positions)
        assert result["estimated_current_value_total_is_partial"] is False

    def test_stale_and_qdii_counts(self):
        """Stale NAV and QDII counts are correct."""
        positions = [
            {
                "valuation_type": "estimated",
                "valuation_quality": "estimated_full_coverage",
                "nav_coverage_status": "full",
                "current_value": 500.0,
                "latest_nav_stale_days": 10,
                "is_qdii_like": True,
            },
            {
                "valuation_type": "estimated",
                "valuation_quality": "estimated_full_coverage",
                "nav_coverage_status": "full",
                "current_value": 500.0,
                "latest_nav_stale_days": None,
                "is_qdii_like": False,
            },
        ]
        result = compute_portfolio_nav_coverage(positions)
        assert result["latest_nav_stale_count"] == 1
        assert result["qdii_like_count"] == 1
        assert result["positions_manual_review_required"] == 0

    def test_manual_review_required_count(self):
        """Manual review required positions counted correctly."""
        positions = [
            {
                "valuation_type": "estimated",
                "valuation_quality": "manual_review_required",
                "nav_coverage_status": "partial",
                "current_value": 500.0,
                "latest_nav_stale_days": None,
                "is_qdii_like": False,
            },
        ]
        result = compute_portfolio_nav_coverage(positions)
        assert result["positions_manual_review_required"] == 1
