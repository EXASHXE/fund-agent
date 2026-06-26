"""Tests for holdings snapshot overlay (M7.5 Phase 3/4)."""
from __future__ import annotations

import pytest

from src.tools.portfolio.holdings_snapshot_overlay import apply_holdings_snapshot_overlay


def _make_confirmed_portfolio(positions=None, summary=None):
    """Build a minimal confirmed_portfolio dict for testing."""
    if positions is None:
        positions = []
    if summary is None:
        summary = {
            "total_positions": len(positions),
            "valued_positions_count": sum(1 for p in positions if p.get("current_value") is not None),
            "portfolio_valuation_status": "unavailable",
            "is_partial_diagnostic": True,
        }
    return {
        "schema_version": "confirmed_portfolio.v1",
        "as_of_date": "2026-06-26",
        "positions": positions,
        "summary": summary,
    }


def _make_snapshot(positions=None):
    """Build a minimal holdings snapshot dict for testing."""
    if positions is None:
        positions = []
    return {
        "schema_version": "current_holdings_snapshot.v1",
        "as_of_date": "2026-06-26",
        "positions": positions,
        "summary": {"positions_total": len(positions)},
    }


class TestOverlayMatchByCode:
    def test_match_by_fund_code(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test Fund A",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": ["valuation_blocked_cashflow_only"],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {
                "fund_code": "000001",
                "fund_name": "Test Fund A",
                "shares": 1000.00,
                "latest_nav": 1.50,
                "current_value": 1500.00,
                "user_verified": True,
                "identity_verification_status": "user_verified_override",
                "valuation_source": "authoritative_holdings_snapshot",
            },
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        pos = result["positions"][0]
        assert pos["current_value"] == 1500.00
        assert pos["valuation_type"] == "holdings_snapshot"
        assert pos["valuation_source"] == "authoritative_holdings_snapshot"
        assert pos["units"] == 1000.00
        assert pos["units_source"] == "holdings_snapshot"
        assert pos["identity_verification_status"] == "user_verified_override"
        assert pos["holding_source"] == "holdings_snapshot_authoritative"
        assert pos["snapshot_matched"] is True

    def test_match_by_normalized_name(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": None,
                "fund_name": "华夏沪深300ETF联接A",
                "units": None,
                "current_value": None,
                "valuation_type": "none",
                "valuation_source": "none",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {
                "fund_code": "000051",
                "fund_name": "华夏沪深300ETF联接A",
                "shares": 5000.00,
                "latest_nav": 1.20,
                "user_verified": True,
                "identity_verification_status": "user_verified_override",
                "valuation_source": "authoritative_holdings_snapshot",
            },
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        pos = result["positions"][0]
        assert pos["current_value"] == 6000.00
        assert pos["fund_code"] is None  # original portfolio doesn't have code
        assert pos["snapshot_matched"] is True


class TestOverlayValuation:
    def test_shares_plus_nav_computes_current_value(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test", "shares": 2000, "latest_nav": 2.5, "valuation_source": "authoritative_holdings_snapshot"},
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        pos = result["positions"][0]
        assert pos["current_value"] == 5000.00
        assert pos["valuation_type"] == "holdings_snapshot"

    def test_current_value_only_no_shares(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test", "current_value": 3000, "valuation_source": "platform_reported_current_value"},
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        pos = result["positions"][0]
        # current_value should be set since reconstructed had none
        assert pos["current_value"] == 3000.00
        assert pos["valuation_type"] == "holdings_snapshot_reported"
        assert pos["platform_reported_current_value"] == 3000.00


class TestReconciliationGap:
    def test_shares_mismatch_flags_gap(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test",
                "units": 4800.0,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test", "shares": 5000, "latest_nav": 1.5, "valuation_source": "authoritative_holdings_snapshot"},
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        pos = result["positions"][0]
        assert pos["reconciliation_gap"] == "shares_mismatch"
        assert "reconciliation_gap_shares" in pos["data_quality"]
        assert result["summary"]["reconciliation_gap_count"] == 1
        # Units should still be overridden by snapshot
        assert pos["units"] == 5000.0

    def test_shares_match_no_gap(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test",
                "units": 5000.0,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test", "shares": 5000, "latest_nav": 1.5, "valuation_source": "authoritative_holdings_snapshot"},
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        pos = result["positions"][0]
        assert "reconciliation_gap" not in pos
        assert result["summary"]["reconciliation_gap_count"] == 0


class TestSnapshotOnlyPosition:
    def test_unmatched_snapshot_position_added(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Existing Fund",
                "units": 100,
                "current_value": 150,
                "valuation_type": "estimated",
                "valuation_source": "estimated_from_transactions_and_nav",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000002", "fund_name": "New Fund", "shares": 2000, "latest_nav": 1.0, "valuation_source": "authoritative_holdings_snapshot"},
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        assert len(result["positions"]) == 2
        new_pos = [p for p in result["positions"] if p.get("fund_code") == "000002"][0]
        assert new_pos["current_value"] == 2000.0
        assert new_pos["holding_source"] == "holdings_snapshot_only"
        assert new_pos["snapshot_matched"] is False
        assert "snapshot_only_position" in new_pos["data_quality"]


class TestPortfolioSummaryRecomputation:
    def test_full_coverage_after_overlay(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test A",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
            {
                "fund_code": "000002",
                "fund_name": "Test B",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test A", "shares": 1000, "latest_nav": 1.0, "valuation_source": "authoritative_holdings_snapshot"},
            {"fund_code": "000002", "fund_name": "Test B", "shares": 2000, "latest_nav": 2.0, "valuation_source": "authoritative_holdings_snapshot"},
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        assert result["summary"]["portfolio_valuation_status"] == "estimated_full_coverage"
        assert result["summary"]["is_partial_diagnostic"] is False
        assert result["summary"]["total_current_value"] == 5000.0
        assert result["summary"]["holdings_snapshot_valued_count"] == 2

    def test_partial_coverage_after_overlay(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test A",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
            {
                "fund_code": "000002",
                "fund_name": "Test B",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test A", "shares": 1000, "latest_nav": 1.0, "valuation_source": "authoritative_holdings_snapshot"},
            # No snapshot data for 000002
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        assert result["summary"]["portfolio_valuation_status"] == "partial_diagnostic_only"
        assert result["summary"]["is_partial_diagnostic"] is True


class TestUserVerifiedIdentityOverride:
    def test_user_verified_overrides_identity_status(self):
        portfolio = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "identity_unverified_blocked",
                "data_quality": ["identity_unverified"],
                "identity_verification_status": "manual_override_unverified",
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test", "shares": 1000, "latest_nav": 1.5, "user_verified": True, "valuation_source": "authoritative_holdings_snapshot"},
        ])
        result = apply_holdings_snapshot_overlay(portfolio, snapshot)
        pos = result["positions"][0]
        assert pos["identity_verification_status"] == "user_verified_override"
        assert "identity_unverified" not in pos["data_quality"]
        assert pos["current_value"] == 1500.0


class TestNoMutation:
    def test_original_portfolio_not_mutated(self):
        original = _make_confirmed_portfolio([
            {
                "fund_code": "000001",
                "fund_name": "Test",
                "units": None,
                "current_value": None,
                "valuation_type": "cashflow_only",
                "valuation_source": "cashflow_only",
                "data_quality": [],
                "holding_source": "transaction_derived",
            },
        ])
        snapshot = _make_snapshot([
            {"fund_code": "000001", "fund_name": "Test", "shares": 1000, "latest_nav": 1.5, "valuation_source": "authoritative_holdings_snapshot"},
        ])
        result = apply_holdings_snapshot_overlay(original, snapshot)
        # Original should be unchanged
        assert original["positions"][0]["current_value"] is None
        assert original["positions"][0]["valuation_type"] == "cashflow_only"
        # Result should be updated
        assert result["positions"][0]["current_value"] == 1500.0
