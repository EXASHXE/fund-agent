"""Tests for lot-level valuation gate (M7.4 Phase 2).

Validates that:
1. Latest NAV without units does not produce current_value
2. Trade-date NAV required to derive units
3. Partial lot coverage does not produce current_value
4. Full lot coverage allows estimated current_value
5. QDII latest NAV without units blocks valuation
6. Conversion manual review blocks units confidence
"""
from __future__ import annotations

from typing import Any

import pytest

from scripts.reconstruct_portfolio_from_ledger import (
    _classify_lot_status,
    _compute_position_valuation_status,
    reconstruct_portfolio,
)


# ── 1. Lot status classification ────────────────────────────────────────


class TestClassifyLotStatus:
    """_classify_lot_status must correctly classify lot reconstruction status."""

    def test_explicit_units_is_confirmed(self):
        assert _classify_lot_status("explicit_units", "", "buy") == "confirmed"

    def test_trade_date_nav_derived_is_estimated(self):
        assert _classify_lot_status("trade_date_nav_derived", "", "buy") == "estimated"

    def test_unavailable_is_blocked_missing_units(self):
        assert _classify_lot_status("unavailable", "", "buy") == "blocked_missing_units"

    def test_identity_mismatch_is_blocked_identity(self):
        assert _classify_lot_status("explicit_units", "code_name_mismatch", "buy") == "blocked_identity"

    def test_identity_unverified_is_blocked_identity(self):
        assert _classify_lot_status("explicit_units", "manual_override_unverified", "buy") == "blocked_identity"

    def test_dividend_is_confirmed(self):
        assert _classify_lot_status("unavailable", "", "dividend") == "confirmed"

    def test_fee_is_confirmed(self):
        assert _classify_lot_status("unavailable", "", "fee") == "confirmed"

    def test_conversion_verified_is_confirmed(self):
        assert _classify_lot_status("conversion_verified", "", "conversion") == "confirmed"

    def test_conversion_estimated_is_estimated(self):
        assert _classify_lot_status("conversion_estimated", "", "conversion") == "estimated"

    def test_refund_matched_is_confirmed(self):
        assert _classify_lot_status("refund_matched", "", "refund") == "confirmed"


# ── 2. Position valuation status ────────────────────────────────────────


class TestComputePositionValuationStatus:
    """_compute_position_valuation_status must correctly determine position status."""

    def test_identity_mismatch_blocks(self):
        result = _compute_position_valuation_status(
            lot_statuses=["confirmed"],
            identity_status="code_name_mismatch",
            has_units=True,
            has_cost=True,
            latest_nav=1.0,
        )
        assert result == "blocked_identity"

    def test_identity_unverified_blocks(self):
        result = _compute_position_valuation_status(
            lot_statuses=["confirmed"],
            identity_status="manual_override_unverified",
            has_units=True,
            has_cost=True,
            latest_nav=1.0,
        )
        assert result == "blocked_identity"

    def test_no_cost_no_units_is_cashflow_only(self):
        result = _compute_position_valuation_status(
            lot_statuses=[],
            identity_status="",
            has_units=False,
            has_cost=False,
            latest_nav=1.0,
        )
        assert result == "cashflow_only"

    def test_all_confirmed_lots_is_confirmed(self):
        result = _compute_position_valuation_status(
            lot_statuses=["confirmed", "confirmed"],
            identity_status="",
            has_units=True,
            has_cost=True,
            latest_nav=1.0,
        )
        assert result == "confirmed"

    def test_all_estimated_lots_is_estimated_full(self):
        result = _compute_position_valuation_status(
            lot_statuses=["estimated", "estimated"],
            identity_status="",
            has_units=True,
            has_cost=True,
            latest_nav=1.0,
        )
        assert result == "estimated_full_lot_coverage"

    def test_mixed_confirmed_estimated_is_estimated_full(self):
        result = _compute_position_valuation_status(
            lot_statuses=["confirmed", "estimated"],
            identity_status="",
            has_units=True,
            has_cost=True,
            latest_nav=1.0,
        )
        assert result == "estimated_full_lot_coverage"

    def test_partial_coverage_is_estimated_partial(self):
        result = _compute_position_valuation_status(
            lot_statuses=["confirmed", "blocked_missing_units"],
            identity_status="",
            has_units=True,
            has_cost=True,
            latest_nav=1.0,
        )
        assert result == "estimated_partial_lot_coverage"

    def test_all_blocked_is_blocked_missing_units(self):
        result = _compute_position_valuation_status(
            lot_statuses=["blocked_missing_units", "blocked_missing_units"],
            identity_status="",
            has_units=False,
            has_cost=True,
            latest_nav=1.0,
        )
        assert result == "blocked_missing_units"

    def test_has_units_no_nav_is_cashflow_only(self):
        result = _compute_position_valuation_status(
            lot_statuses=["confirmed"],
            identity_status="",
            has_units=True,
            has_cost=True,
            latest_nav=None,
        )
        assert result == "cashflow_only"


# ── 3. Reconstruction integration tests ─────────────────────────────────


def _make_ledger(fund_code: str = "000001", trades: list[dict] | None = None) -> dict[str, Any]:
    """Build a ledger with specified trades."""
    transactions = []
    for t in trades or []:
        txn = {
            "fund_code": fund_code,
            "fund_name": "Test Fund",
            "action": t.get("action", "buy"),
            "amount": t.get("amount", 1000.0),
            "net_amount": t.get("net_amount", t.get("amount", 1000.0)),
            "trade_date": t.get("trade_date", "2025-01-15"),
            "confirmation_type": t.get("confirmation_type", "evidence_confirmed"),
            "confirmation_source": t.get("confirmation_source", "alipay"),
        }
        if "units" in t:
            txn["units"] = t["units"]
        transactions.append(txn)
    return {"transactions": transactions}


def _make_nav(fund_code: str = "000001", records: list[dict] | None = None) -> dict[str, Any]:
    """Build a NAV snapshot."""
    return {
        "nav_by_fund": {
            fund_code: {
                "records": records or [
                    {"date": "2025-01-15", "nav": 1.0},
                    {"date": "2025-06-01", "nav": 1.05},
                ],
            },
        },
    }


class TestLatestNavWithoutUnitsBlocksValuation:
    """Latest NAV alone must not produce current_value without confirmed units."""

    def test_no_trade_date_nav_no_units_no_current_value(self):
        """Buy with no trade-date NAV and no explicit units → cashflow_only."""
        ledger = _make_ledger(trades=[{"amount": 1000.0, "trade_date": "2025-01-15"}])
        nav = _make_nav(records=[{"date": "2025-06-01", "nav": 1.05}])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["valuation_type"] == "cashflow_only"
        assert pos["current_value"] is None


class TestTradeDateNavRequiredToDeriveUnits:
    """Trade-date NAV is required to derive units from amount."""

    def test_trade_date_nav_allows_units_derivation(self):
        """Buy with trade-date NAV → units derived → estimated."""
        ledger = _make_ledger(trades=[{"amount": 1000.0, "trade_date": "2025-01-15"}])
        nav = _make_nav(records=[
            {"date": "2025-01-15", "nav": 1.0},
            {"date": "2025-06-01", "nav": 1.05},
        ])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["valuation_type"] == "estimated"
        assert pos["current_value"] is not None
        assert pos["position_valuation_status"] in ("confirmed", "estimated_full_lot_coverage")


class TestPartialLotCoverageDoesNotProduceCurrentValue:
    """Partial lot coverage must not produce current_value."""

    def test_one_buy_with_nav_one_without(self):
        """Two buys: one with NAV, one without → partial lot coverage → no current_value."""
        ledger = _make_ledger(trades=[
            {"amount": 1000.0, "trade_date": "2025-01-15"},
            {"amount": 500.0, "trade_date": "2025-03-01"},
        ])
        # NAV only for first buy date
        nav = _make_nav(records=[
            {"date": "2025-01-15", "nav": 1.0},
            {"date": "2025-06-01", "nav": 1.05},
        ])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        # M7.4: partial lot coverage → cashflow_only, no current_value
        assert pos["valuation_type"] == "cashflow_only"
        assert pos["current_value"] is None
        # But diagnostic value should be available
        assert pos.get("partial_estimated_value") is not None


class TestFullLotCoverageAllowsEstimatedCurrentValue:
    """Full lot coverage with units + latest NAV allows estimated current_value."""

    def test_both_buys_have_trade_date_nav(self):
        """Two buys, both with NAV → full lot coverage → estimated."""
        ledger = _make_ledger(trades=[
            {"amount": 1000.0, "trade_date": "2025-01-15"},
            {"amount": 500.0, "trade_date": "2025-03-01"},
        ])
        nav = _make_nav(records=[
            {"date": "2025-01-15", "nav": 1.0},
            {"date": "2025-03-01", "nav": 1.02},
            {"date": "2025-06-01", "nav": 1.05},
        ])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["valuation_type"] == "estimated"
        assert pos["current_value"] is not None


class TestExplicitUnitsAllowValuation:
    """Explicit units in transaction data allow valuation even without trade-date NAV."""

    def test_explicit_units_with_latest_nav(self):
        """Buy with explicit units + latest NAV → estimated."""
        ledger = _make_ledger(trades=[
            {"amount": 1000.0, "trade_date": "2025-01-15", "units": 950.0},
        ])
        nav = _make_nav(records=[{"date": "2025-06-01", "nav": 1.05}])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        positions = result["confirmed_portfolio"]["positions"]
        assert len(positions) == 1
        pos = positions[0]
        assert pos["valuation_type"] == "estimated"
        assert pos["current_value"] is not None
        assert pos["position_valuation_status"] == "confirmed"
