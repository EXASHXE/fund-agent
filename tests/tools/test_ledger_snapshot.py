"""Tests for src.tools.portfolio.ledger_snapshot."""

from __future__ import annotations

import json

import pytest

from src.tools.portfolio.ledger_snapshot import (
    apply_settlement_rules,
    build_position_snapshot_from_transactions,
    calculate_realized_unrealized_pnl,
    normalize_transaction_events,
    reconcile_snapshot_with_portfolio,
)


class TestNormalizeTransactionEvents:
    def test_normalizes_action_from_type_field(self):
        raw = [{"type": "BUY", "fund_code": "110011", "date": "2025-06-01", "amount": 1000}]
        normalized, warnings = normalize_transaction_events(raw)
        assert len(normalized) == 1
        assert normalized[0]["action"] == "BUY"
        assert not warnings

    def test_unknown_action_warns(self):
        raw = [{"action": "UNKNOWN", "fund_code": "110011", "date": "2025-01-01", "amount": 100}]
        normalized, warnings = normalize_transaction_events(raw)
        assert len(normalized) == 1
        assert any("unknown action" in w for w in warnings)

    def test_missing_fund_code_warns(self):
        raw = [{"action": "BUY", "date": "2025-01-01", "amount": 100}]
        _normalized, warnings = normalize_transaction_events(raw)
        assert any("missing" in w for w in warnings)

    def test_converts_numeric_fields_to_float(self):
        raw = [{"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": "100.50", "shares": "200"}]
        normalized, _warnings = normalize_transaction_events(raw)
        assert normalized[0]["amount"] == 100.50
        assert normalized[0]["shares"] == 200.0

    def test_negative_buy_amount_clamped(self):
        raw = [{"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": -100}]
        _normalized, warnings = normalize_transaction_events(raw)
        assert any("negative" in w for w in warnings)

    def test_raw_not_list(self):
        normalized, warnings = normalize_transaction_events({})
        assert normalized == []
        assert any("must be a list" in w for w in warnings)

    def test_all_valid_actions(self):
        for action in ("BUY", "SELL", "DIVIDEND", "FEE", "TRANSFER_IN", "TRANSFER_OUT", "CALIBRATE"):
            raw = [{"action": action, "fund_code": "110011", "date": "2025-01-01", "amount": 100}]
            normalized, warnings = normalize_transaction_events(raw)
            assert len(normalized) == 1, f"Action {action} should be valid"
            assert normalized[0]["action"] == action


class TestBuildPositionSnapshot:
    def test_buy_builds_shares_and_cost(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-06-01", "amount": 10000, "shares": 10000, "nav": 1.0},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.20}, "2026-06-01"
        )
        assert len(result["positions"]) == 1
        pos = result["positions"][0]
        assert pos["fund_code"] == "110011"
        assert pos["shares"] == 10000.0
        assert pos["total_cost"] == 10000.0
        assert pos["current_value"] == 12000.0  # 10000 * 1.20
        assert pos["unrealized_pnl"] == 2000.0
        assert pos["unrealized_pnl_pct"] == 0.20

    def test_partial_sell_updates_shares_and_pnl(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000, "nav": 1.0},
            {"action": "SELL", "fund_code": "110011", "date": "2025-06-01", "amount": 3600, "shares": 3000, "nav": 1.2},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.30}, "2026-01-01"
        )
        assert len(result["positions"]) == 1
        pos = result["positions"][0]
        # After sell: 7000 shares, cost = 10000 - 3000 = 7000
        assert pos["shares"] == 7000.0
        assert pos["total_cost"] == 7000.0
        assert pos["current_value"] == 9100.0  # 7000 * 1.30
        # realized PnL from sell: 3600 - 3000 = 600
        assert pos["realized_pnl"] == 600.0
        assert pos["unrealized_pnl"] == 2100.0  # 9100 - 7000

    def test_sell_beyond_shares_warns_and_clamps(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 5000, "shares": 5000, "nav": 1.0},
            {"action": "SELL", "fund_code": "110011", "date": "2025-06-01", "amount": 12000, "shares": 10000, "nav": 1.2},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.30}, "2026-01-01"
        )
        pos = result["positions"][0]
        # Clamped to 5000 sell, should have 0 shares left
        assert pos["shares"] == 0.0
        assert any("exceeds" in w for w in result["warnings"])

    def test_missing_nav_warns(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000, "nav": 1.0},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {}, "2026-01-01"
        )
        pos = result["positions"][0]
        assert pos["current_value"] is None
        assert pos["unrealized_pnl"] is None
        assert any("MISSING_NAV" in w for w in result["warnings"]) or \
               any("missing" in w.lower() for w in result["warnings"]) or \
               any("MISSING_NAV_OMIT_CURRENT_VALUE" in pos.get("warnings", []))

    def test_weighted_average_cost_after_multiple_buys(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000, "nav": 1.0},
            {"action": "BUY", "fund_code": "110011", "date": "2025-06-01", "amount": 22000, "shares": 20000, "nav": 1.1},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.20}, "2026-01-01"
        )
        pos = result["positions"][0]
        # Total cost: 32000, total shares: 30000, avg: 1.0667
        assert pos["shares"] == 30000.0
        assert pos["total_cost"] == 32000.0
        assert round(pos["average_cost_nav"], 4) == 1.0667
        assert pos["current_value"] == 36000.0

    def test_deterministic_as_of_date(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 100, "shares": 100},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.0}, "2026-06-03"
        )
        assert result["as_of_date"] == "2026-06-03"

    def test_dividend_and_fee_cashflow(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "DIVIDEND", "fund_code": "110011", "date": "2025-06-01", "amount": 500},
            {"action": "FEE", "fund_code": "110011", "date": "2025-06-01", "amount": 50},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.20}, "2026-01-01"
        )
        cf = result["cashflow_summary"]
        assert cf["dividend_income"] == 500.0
        assert cf["fee_expense"] == 50.0
        assert cf["total_inflows"] == 500.0
        assert cf["total_outflows"] == 10050.0
        # Dividend adds to realized_pnl
        pos = result["positions"][0]
        assert pos["realized_pnl"] == 450.0  # 500 - 50

    def test_transfer_in_transfer_out(self):
        txn = [
            {"action": "TRANSFER_IN", "fund_code": "110011", "date": "2025-01-01", "amount": 5000, "shares": 5000},
            {"action": "TRANSFER_OUT", "fund_code": "110011", "date": "2025-06-01", "amount": 3000, "shares": 3000},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.20}, "2026-01-01"
        )
        pos = result["positions"][0]
        assert pos["shares"] == 2000.0
        assert pos["total_cost"] == 2000.0

    def test_json_serializable(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.20}, "2026-01-01"
        )
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["as_of_date"] == "2026-01-01"
        assert len(parsed["positions"]) == 1

    def test_calibrate_action(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 1000, "shares": 1000},
            {"action": "CALIBRATE", "fund_code": "110011", "date": "2025-06-01", "amount": 5000, "shares": 5000},
        ]
        result = build_position_snapshot_from_transactions(
            txn, {"110011": 1.20}, "2026-01-01"
        )
        pos = result["positions"][0]
        assert pos["total_cost"] == 5000.0
        assert pos["shares"] == 5000.0


class TestReconcileSnapshotWithPortfolio:
    def test_matched_when_same(self):
        snapshot = {
            "positions": [
                {"fund_code": "110011", "shares": 100.0, "current_value": 120.0}
            ]
        }
        portfolio = {
            "positions": [
                {"fund_code": "110011", "shares": 100.0, "current_value": 120.0}
            ]
        }
        result = reconcile_snapshot_with_portfolio(snapshot, portfolio)
        assert result["matched"] is True
        assert len(result["mismatches"]) == 0

    def test_shares_mismatch_detected(self):
        snapshot = {
            "positions": [
                {"fund_code": "110011", "shares": 100.0, "current_value": 120.0}
            ]
        }
        portfolio = {
            "positions": [
                {"fund_code": "110011", "shares": 105.0, "current_value": 126.0}
            ]
        }
        result = reconcile_snapshot_with_portfolio(snapshot, portfolio)
        assert result["matched"] is False
        assert len(result["mismatches"]) > 0

    def test_missing_in_portfolio(self):
        snapshot = {
            "positions": [
                {"fund_code": "110011", "shares": 100.0, "current_value": 120.0},
                {"fund_code": "000001", "shares": 50.0, "current_value": 60.0},
            ]
        }
        portfolio = {
            "positions": [
                {"fund_code": "110011", "shares": 100.0, "current_value": 120.0}
            ]
        }
        result = reconcile_snapshot_with_portfolio(snapshot, portfolio)
        assert result["matched"] is False
        assert any("MISSING_IN_PORTFOLIO" in m["reason"] for m in result["mismatches"])

    def test_missing_in_snapshot(self):
        snapshot = {
            "positions": [
                {"fund_code": "110011", "shares": 100.0, "current_value": 120.0}
            ]
        }
        portfolio = {
            "positions": [
                {"fund_code": "110011", "shares": 100.0, "current_value": 120.0},
                {"fund_code": "000001", "shares": 50.0, "current_value": 60.0},
            ]
        }
        result = reconcile_snapshot_with_portfolio(snapshot, portfolio)
        assert result["matched"] is False
        assert any("MISSING_IN_SNAPSHOT" in m["reason"] for m in result["mismatches"])

    def test_does_not_throw_on_mismatch(self):
        snapshot = {"positions": [{"fund_code": "X", "shares": 1}]}
        portfolio = {"positions": [{"fund_code": "X", "shares": 999}]}
        result = reconcile_snapshot_with_portfolio(snapshot, portfolio)
        assert result is not None
        assert result["matched"] is False


class TestApplySettlementRules:
    def test_confirms_settled_transactions(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2026-05-25", "amount": 1000},
        ]
        result = apply_settlement_rules(txn, "2026-06-01")
        # 2026-05-25 + 3 days = 2026-05-28, before 2026-06-01 -> confirmed
        assert len(result["confirmed"]) == 1
        assert len(result["pending"]) == 0

    def test_pends_unsettled_transactions(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2026-05-30", "amount": 1000},
        ]
        result = apply_settlement_rules(txn, "2026-06-01")
        # 2026-05-30 + 3 days = 2026-06-02, after 2026-06-01 -> pending
        assert len(result["confirmed"]) == 0
        assert len(result["pending"]) == 1

    def test_include_pending_option(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2026-05-30", "amount": 1000},
        ]
        result = apply_settlement_rules(txn, "2026-06-01", {"include_pending": True})
        assert len(result["confirmed"]) == 1
        assert len(result["pending"]) == 0
        assert len(result["warnings"]) == 1

    def test_invalid_date_returns_all_confirmed(self):
        txn = [{"action": "BUY", "fund_code": "110011", "date": "2026-01-01", "amount": 1000}]
        result = apply_settlement_rules(txn, "not-a-date")
        assert len(result["confirmed"]) == 1


class TestCalculateRealizedUnrealizedPnl:
    def test_basic_pnl_calculation(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        assert len(result["positions"]) == 1
        assert result["positions"][0]["unrealized_pnl"] == 5000.0
        assert result["positions"][0]["realized_pnl"] is None


class TestHardenedTransactionSemantics:
    """Tests for explicit transaction semantics hardened in v0.4.8-dev."""

    def test_buy_amount_nav_infers_shares(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "nav": 1.25},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        pos = result["positions"][0]
        assert pos["shares"] == 8000.0  # 10000 / 1.25

    def test_buy_amount_only_warns_unresolved(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        # amount-only BUY: cost applied but shares unresolved
        pos = result["positions"][0]
        assert pos["shares"] == 0.0  # No shares inferred without nav
        assert pos["total_cost"] == 10000.0  # Cost is still recorded
        assert len(result["unresolved_events"]) >= 1

    def test_sell_amount_nav_infers_shares(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "SELL", "fund_code": "110011", "date": "2025-06-01", "amount": 3000, "nav": 1.50},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        pos = result["positions"][0]
        assert pos["shares"] == 8000.0  # Sold 3000/1.50 = 2000 shares

    def test_sell_amount_only_unresolved_no_cashflow(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "SELL", "fund_code": "110011", "date": "2025-06-01", "amount": 3000},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        # Unresolved SELL: no nav to infer shares, so skip
        pos = result["positions"][0]
        assert pos["shares"] == 10000.0  # Unchanged
        assert len(result["unresolved_events"]) >= 1

    def test_transfer_out_no_realized_pnl(self):
        """TRANSFER_OUT reduces shares and pro-rata cost but no realized PnL."""
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "TRANSFER_OUT", "fund_code": "110011", "date": "2025-06-01", "shares": 5000},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        pos = result["positions"][0]
        assert pos["shares"] == 5000.0
        assert pos["total_cost"] == 5000.0  # Pro-rata cost reduction
        assert pos["realized_pnl"] is None or pos["realized_pnl"] == 0.0

    def test_transfer_in_increases_position(self):
        """TRANSFER_IN adds shares and cost but is NOT a cash inflow."""
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 5000, "shares": 5000},
            {"action": "TRANSFER_IN", "fund_code": "110011", "date": "2025-06-01", "amount": 10000, "shares": 10000},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        pos = result["positions"][0]
        assert pos["shares"] == 15000.0
        assert pos["total_cost"] == 15000.0

    def test_dividend_adds_realized_income(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "DIVIDEND", "fund_code": "110011", "date": "2025-06-01", "amount": 500},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.20})
        pos = result["positions"][0]
        assert pos["shares"] == 10000.0  # Unchanged
        assert pos["realized_pnl"] == 500.0

    def test_fee_reduces_realized_income(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "DIVIDEND", "fund_code": "110011", "date": "2025-06-01", "amount": 500},
            {"action": "FEE", "fund_code": "110011", "date": "2025-06-01", "amount": 50},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.20})
        pos = result["positions"][0]
        assert pos["realized_pnl"] == 450.0  # 500 - 50

    def test_calibrate_warns(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 1000, "shares": 1000},
            {"action": "CALIBRATE", "fund_code": "110011", "date": "2025-06-01", "amount": 5000, "shares": 5000},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        pos = result["positions"][0]
        assert pos["total_cost"] == 5000.0
        assert pos["shares"] == 5000.0
        assert "CALIBRATE_OVERRIDE" in pos["warnings"]

    def test_unknown_action_marked_invalid(self):
        raw = [{"action": "BAD_ACTION", "fund_code": "110011", "date": "2025-01-01", "amount": 100}]
        normalized, warnings = normalize_transaction_events(raw)
        assert len(normalized) == 1
        assert normalized[0].get("valid") is False
        assert "unknown_action" in normalized[0].get("invalid_reason", "")

    def test_invalid_events_skipped_in_pnl(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "BAD_ACTION", "fund_code": "110011", "date": "2025-06-01", "amount": 9999,
             "valid": False, "invalid_reason": "unknown_action:BAD_ACTION"},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        assert result["invalid_events_count"] >= 1
        pos = result["positions"][0]
        assert pos["shares"] == 10000.0  # Invalid event skipped, no change

    def test_cost_basis_never_negative(self):
        """After extreme sells, cost basis should not go negative."""
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "SELL", "fund_code": "110011", "date": "2025-06-01", "amount": 50000, "shares": 10000, "nav": 5.0},
        ]
        result = calculate_realized_unrealized_pnl(txn, {"110011": 1.50})
        pos = result["positions"][0]
        assert pos["shares"] == 0.0
        assert pos["total_cost"] >= 0.0

    def test_shares_never_negative(self):
        """SELL beyond available shares should clamp, not go negative."""
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 5000, "shares": 5000},
            {"action": "SELL", "fund_code": "110011", "date": "2025-06-01", "amount": 12000, "shares": 10000, "nav": 1.2},
        ]
        snapshot = build_position_snapshot_from_transactions(txn, {"110011": 1.30}, "2026-01-01")
        pos = snapshot["positions"][0]
        assert pos["shares"] >= 0.0
        assert any("exceeds" in w.lower() or "clamp" in w.lower() for w in snapshot["warnings"])

    def test_json_serializable_after_hardening(self):
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000, "shares": 10000},
            {"action": "DIVIDEND", "fund_code": "110011", "date": "2025-06-01", "amount": 500},
            {"action": "FEE", "fund_code": "110011", "date": "2025-06-01", "amount": 50},
        ]
        result = build_position_snapshot_from_transactions(txn, {"110011": 1.20}, "2026-06-01")
        json_str = json.dumps(result, default=str)
        parsed = json.loads(json_str)
        assert parsed["as_of_date"] == "2026-06-01"

    def test_transfer_not_cashflow(self):
        """TRANSFER_IN/TRANSFER_OUT are position movements, not cashflow."""
        txn = [
            {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 5000, "shares": 5000},
            {"action": "TRANSFER_IN", "fund_code": "110011", "date": "2025-06-01", "amount": 3000, "shares": 3000},
            {"action": "TRANSFER_OUT", "fund_code": "110011", "date": "2025-09-01", "amount": 2000, "shares": 2000},
        ]
        snapshot = build_position_snapshot_from_transactions(txn, {"110011": 1.50}, "2026-01-01")
        cf = snapshot["cashflow_summary"]
        # Only BUY is a cash outflow; TRANSFER_IN/OUT are not cashflow
        assert cf["total_outflows"] == 5000.0
        assert cf["total_inflows"] == 0.0


class TestHardenedReconciliation:
    def test_configurable_tolerances(self):
        snapshot = {"positions": [{"fund_code": "110011", "shares": 100.0, "current_value": 120.0}]}
        portfolio = {"positions": [{"fund_code": "110011", "shares": 100.5, "current_value": 120.5}]}
        # With high tolerance, this should match
        result = reconcile_snapshot_with_portfolio(
            snapshot, portfolio,
            options={"shares_tolerance": 1.0, "value_tolerance": 1.0}
        )
        assert result["matched"] is True

    def test_severity_included(self):
        snapshot = {"positions": [{"fund_code": "110011", "shares": 100.0, "current_value": 120.0}]}
        portfolio = {"positions": [{"fund_code": "110011", "shares": 200.0, "current_value": 240.0}]}
        result = reconcile_snapshot_with_portfolio(snapshot, portfolio)
        for m in result["mismatches"]:
            assert "severity" in m
        for c in result["comparisons"]:
            assert "severity" in c
