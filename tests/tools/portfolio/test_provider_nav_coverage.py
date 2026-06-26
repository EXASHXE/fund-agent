"""Tests for provider NAV coverage diagnostics (M7.4 Phase 6).

Validates that:
1. latest_nav_found_count is not equal to valuation coverage
2. insufficient_trade_date_nav_coverage reason code is emitted
3. provider_diagnostics reports trade-date NAV coverage
4. nav_used_for_units_count is tracked correctly
"""
from __future__ import annotations

from datetime import date

import pytest

from src.tools.portfolio.nav_coverage import compute_nav_coverage
from src.tools.portfolio.personal_health_report import (
    REASON_INSUFFICIENT_TRADE_DATE_NAV,
    VALID_REASON_CODES,
    build_personal_health_summary,
)


class TestLatestNavCountNotEqualValuationCoverage:
    """latest_nav_found_count ≠ valuation coverage. Valuation = units coverage + latest NAV."""

    def test_latest_nav_available_but_no_units(self):
        """A fund with latest NAV but no trade-date NAV for units is NOT valued."""
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15"},
            ],
            nav_records=[
                {"date": "2025-06-01", "nav": 1.5},
            ],
            as_of_date=date(2025, 6, 1),
        )
        # latest_nav is available
        assert nav_cov["latest_nav_available"] is True
        assert nav_cov["provider_diagnostics"]["latest_nav_found_count"] == 1
        # But no trade-date NAV for the buy → coverage is not full
        assert nav_cov["coverage_status"] != "full"
        assert nav_cov["trades_missing_trade_date_nav"] == 1

    def test_latest_nav_with_full_trade_date_nav(self):
        """A fund with both latest NAV and trade-date NAV for all trades is fully covered."""
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15"},
            ],
            nav_records=[
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.5},
            ],
            as_of_date=date(2025, 6, 1),
        )
        assert nav_cov["coverage_status"] == "full"
        assert nav_cov["provider_diagnostics"]["latest_nav_found_count"] == 1
        assert nav_cov["provider_diagnostics"]["trade_date_nav_found_count"] == 1


class TestInsufficientTradeDateNavCoverageReasonCode:
    """insufficient_trade_date_nav_coverage reason code must be emitted."""

    def test_reason_code_in_valid_set(self):
        assert REASON_INSUFFICIENT_TRADE_DATE_NAV in VALID_REASON_CODES

    def test_reason_code_emitted_when_partial_nav(self):
        """When trade_date_nav_found < trade_date_nav_requested, reason code fires."""
        artifacts = {
            "e2e_summary": {
                "pipeline_steps": {"reconstruction_status": "completed"},
            },
            "nav_coverage_summary": {
                "nav_coverage_partial_count": 1,
                "trade_date_nav_requested_count": 3,
                "trade_date_nav_found_count": 1,
            },
        }
        result = build_personal_health_summary(artifacts)
        assert REASON_INSUFFICIENT_TRADE_DATE_NAV in result["reason_codes"]

    def test_reason_code_not_emitted_when_full_nav(self):
        """When trade_date_nav_found == trade_date_nav_requested, no reason code."""
        artifacts = {
            "e2e_summary": {
                "pipeline_steps": {"reconstruction_status": "completed"},
            },
            "nav_coverage_summary": {
                "trade_date_nav_requested_count": 3,
                "trade_date_nav_found_count": 3,
            },
        }
        result = build_personal_health_summary(artifacts)
        assert REASON_INSUFFICIENT_TRADE_DATE_NAV not in result["reason_codes"]


class TestProviderDiagnosticsReportsTradeDateNavCoverage:
    """provider_diagnostics must report trade-date NAV coverage details."""

    def test_provider_diagnostics_present_in_output(self):
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15"},
            ],
            nav_records=[
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.5},
            ],
            as_of_date=date(2025, 6, 1),
            provider_name="akshare",
            provider_available=True,
        )
        pd = nav_cov["provider_diagnostics"]
        assert pd["provider_name"] == "akshare"
        assert pd["provider_available"] is True
        assert pd["trade_date_nav_requested_count"] == 1
        assert pd["trade_date_nav_found_count"] == 1
        assert pd["latest_nav_found_count"] == 1

    def test_provider_diagnostics_with_missing_nav(self):
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15"},
                {"action": "buy", "amount": 5000, "trade_date": "2025-03-01"},
            ],
            nav_records=[
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.5},
            ],
            as_of_date=date(2025, 6, 1),
        )
        pd = nav_cov["provider_diagnostics"]
        assert pd["trade_date_nav_requested_count"] == 2
        assert pd["trade_date_nav_found_count"] == 1
        assert pd["latest_nav_found_count"] == 1

    def test_provider_diagnostics_provider_unavailable(self):
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15"},
            ],
            nav_records=[],
            as_of_date=date(2025, 6, 1),
            provider_name="akshare",
            provider_available=False,
            provider_error_count=1,
        )
        pd = nav_cov["provider_diagnostics"]
        assert pd["provider_available"] is False
        assert pd["provider_error_count"] == 1
        assert pd["trade_date_nav_found_count"] == 0
        assert pd["latest_nav_found_count"] == 0


class TestNavUsedForUnitsCount:
    """nav_used_for_units_count must track trades where NAV was used to derive units."""

    def test_nav_used_for_units_when_no_explicit_units(self):
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15"},
            ],
            nav_records=[
                {"date": "2025-01-15", "nav": 1.0},
            ],
            as_of_date=date(2025, 6, 1),
        )
        assert nav_cov["nav_used_for_units_count"] == 1
        assert nav_cov["provider_diagnostics"]["nav_used_for_units_count"] == 1

    def test_nav_not_used_for_units_when_explicit(self):
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15", "units": 10000.0},
            ],
            nav_records=[
                {"date": "2025-01-15", "nav": 1.0},
            ],
            as_of_date=date(2025, 6, 1),
        )
        assert nav_cov["nav_used_for_units_count"] == 0
        assert nav_cov["trades_with_explicit_units"] == 1

    def test_mixed_explicit_and_nav(self):
        nav_cov = compute_nav_coverage(
            fund_code="000001",
            transactions=[
                {"action": "buy", "amount": 10000, "trade_date": "2025-01-15", "units": 10000.0},
                {"action": "buy", "amount": 5000, "trade_date": "2025-03-01"},
            ],
            nav_records=[
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-03-01", "nav": 1.1},
            ],
            as_of_date=date(2025, 6, 1),
        )
        assert nav_cov["nav_used_for_units_count"] == 1  # only the second trade
        assert nav_cov["trades_with_explicit_units"] == 1
