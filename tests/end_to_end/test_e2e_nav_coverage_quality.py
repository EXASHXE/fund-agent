"""End-to-end tests for NAV coverage quality in E2E pipeline.

Tests the integration of NAV coverage diagnostics with the reconstruction
pipeline. All data is synthetic.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.tools.portfolio.nav_coverage import (
    compute_nav_coverage,
    compute_portfolio_nav_coverage,
)


class TestE2ENavCoverageQuality:
    """E2E scenarios for NAV coverage quality."""

    def test_full_trade_date_nav_coverage(self):
        """buy/sell with trade-date NAV → estimated_full_coverage."""
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

    def test_partial_trade_date_nav_coverage(self):
        """Some trades missing NAV → estimated_partial_coverage, total_is_partial=True."""
        positions = [
            {
                "valuation_type": "estimated",
                "valuation_quality": "estimated_partial_coverage",
                "nav_coverage_status": "partial",
                "current_value": 500.0,
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
        assert result["estimated_current_value_total_is_partial"] is True
        assert result["nav_coverage_partial_count"] == 1

    def test_latest_nav_only_does_not_infer_units(self):
        """amount + latest_nav but no trade-date NAV → cashflow_only, no units_estimated."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
        ]
        nav_records = [
            {"date": "2026-06-20", "nav": 1.2600},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["coverage_status"] == "latest_only"
        assert result["valuation_quality"] == "cashflow_only"

    def test_explicit_units_with_latest_nav(self):
        """Explicit units + latest_nav → can estimate current_value, NAV gap still visible."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0, "units": 81.0},
        ]
        nav_records = [
            {"date": "2026-06-20", "nav": 1.2600},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
        )
        assert result["coverage_status"] == "full"
        assert result["trades_with_explicit_units"] == 1
        # NAV gap recorded in nav_gap_count, not in trades_missing
        assert result["trades_nav_gap_count"] == 1
        assert result["trades_missing_trade_date_nav"] == 0

    def test_qdii_stale_nav_warning(self):
        """QDII-like with stale NAV → stale warning, not failure."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0, "units": 81.0},
        ]
        nav_records = [
            {"date": "2026-06-09", "nav": 1.2345},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=nav_records,
            as_of_date=date(2026, 6, 20),
            is_qdii_like=True,
        )
        assert result["latest_nav_stale_days"] == 11
        assert result["is_qdii_like"] is True

    def test_domestic_stale_nav_warning(self):
        """Domestic fund with stale NAV → stale warning."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0, "units": 81.0},
        ]
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

    def test_conversion_requires_manual_review(self):
        """conversion_in/out → manual_review_required."""
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

    def test_refund_requires_manual_review(self):
        """refund → manual_review_required."""
        txns = [
            {"action": "buy", "trade_date": "2026-06-01", "amount": 100.0},
            {"action": "refund", "trade_date": "2026-06-15", "amount": 50.0},
        ]
        result = compute_nav_coverage(
            fund_code="000001",
            transactions=txns,
            nav_records=None,
            as_of_date=date(2026, 6, 20),
        )
        assert result["valuation_quality"] == "manual_review_required"

    def test_portfolio_summary_counts(self):
        """Portfolio-level summary counts are correct."""
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
            {
                "valuation_type": "estimated",
                "valuation_quality": "manual_review_required",
                "nav_coverage_status": "partial",
                "current_value": 500.0,
                "latest_nav_stale_days": 10,
                "is_qdii_like": True,
            },
        ]
        result = compute_portfolio_nav_coverage(positions)
        assert result["positions_total"] == 3
        assert result["positions_estimated"] == 2
        assert result["positions_cashflow_only"] == 1
        assert result["positions_manual_review_required"] == 1
        assert result["nav_coverage_full_count"] == 1
        assert result["nav_coverage_partial_count"] == 1
        assert result["nav_coverage_none_count"] == 1
        assert result["latest_nav_stale_count"] == 1
        assert result["qdii_like_count"] == 1
        assert result["estimated_current_value_total_is_partial"] is True
