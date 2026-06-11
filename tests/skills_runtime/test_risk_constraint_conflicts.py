"""Tests for risk_constraint_conflicts in decision_support."""
from __future__ import annotations

import pytest

from src.skills_runtime.decision_support.risk_constraint_conflicts import build_risk_constraint_conflicts


class TestRiskConstraintConflicts:
    def test_max_trade_pct_exceeded(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.05, "liquidity_reserve_pct": 0.1},
            "constraints": {},
        }
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            requested_amount=10000,
            capped_amount=5000,
        )
        items = result["items"]
        assert any(i["constraint"] == "max_trade_pct" for i in items)

    def test_forbidden_action_conflict(self):
        payload = {
            "portfolio_context": {"total_value": 100000},
            "risk_profile": {},
            "constraints": {"forbidden_actions": ["SELL"]},
        }
        result = build_risk_constraint_conflicts(
            action="SELL",
            payload=payload,
            requested_amount=5000,
            capped_amount=0,
        )
        items = result["items"]
        assert any(i["constraint"] == "forbidden_actions" and i["resolution"] == "reject_trade" for i in items)

    def test_cash_available_conflict_for_buy(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 3000},
            "risk_profile": {"max_trade_pct": 0.1, "liquidity_reserve_pct": 0.1},
            "constraints": {},
        }
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            requested_amount=10000,
            capped_amount=2000,
        )
        items = result["items"]
        assert any(i["constraint"] == "cash_available" for i in items)

    def test_min_trade_amount_conflict(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.1},
            "constraints": {"min_trade_amount": 5000},
        }
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            requested_amount=3000,
            capped_amount=3000,
        )
        items = result["items"]
        assert any(i["constraint"] == "min_trade_amount" and i["resolution"] == "reject_trade" for i in items)

    def test_summary_counts(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 2000},
            "risk_profile": {"max_trade_pct": 0.05, "liquidity_reserve_pct": 0.1},
            "constraints": {},
        }
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            requested_amount=10000,
            capped_amount=2000,
        )
        summary = result["summary"]
        assert isinstance(summary["has_blocking_conflict"], bool)
        assert isinstance(summary["has_capping_conflict"], bool)
        assert isinstance(summary["blocked_trade_count"], int)
        assert isinstance(summary["capped_trade_count"], int)

    def test_passive_action_no_conflicts(self):
        result = build_risk_constraint_conflicts(
            action="HOLD",
            payload={},
            requested_amount=0,
            capped_amount=0,
        )
        assert result["items"] == []

    def test_trade_plan_conflicts(self):
        payload = {
            "portfolio_context": {"total_value": 100000},
            "risk_profile": {},
            "constraints": {"forbidden_actions": ["SELL"]},
        }
        trade_plan = [
            {"trade_id": "T1", "action": "SELL", "amount": 5000},
            {"trade_id": "T2", "action": "BUY", "amount": 5000, "cap_reasons": ["max_trade_pct (0.05)"]},
        ]
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            trade_plan=trade_plan,
        )
        items = result["items"]
        assert any(i.get("trade_id") == "T1" and i["constraint"] == "forbidden_actions" for i in items)
        assert any(i.get("trade_id") == "T2" and i["constraint"] == "max_trade_pct" for i in items)


class TestRiskConstraintConflictItemStructure:
    def _make_conflict_item(self, constraint: str) -> dict:
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.05, "liquidity_reserve_pct": 0.1},
            "constraints": {"forbidden_actions": ["SELL"], "max_buy_amount": 3000, "min_trade_amount": 1000},
        }
        if constraint == "forbidden_actions":
            result = build_risk_constraint_conflicts(
                action="SELL", payload=payload, requested_amount=5000, capped_amount=0,
            )
        elif constraint == "cash_available":
            payload["portfolio_context"]["cash_available"] = 2000
            result = build_risk_constraint_conflicts(
                action="BUY", payload=payload, requested_amount=10000, capped_amount=2000,
            )
        elif constraint == "min_trade_amount":
            result = build_risk_constraint_conflicts(
                action="BUY", payload=payload, requested_amount=500, capped_amount=500,
            )
        elif constraint == "max_trade_pct":
            result = build_risk_constraint_conflicts(
                action="BUY", payload=payload, requested_amount=10000, capped_amount=5000,
            )
        elif constraint == "max_buy_amount":
            result = build_risk_constraint_conflicts(
                action="BUY", payload=payload, requested_amount=10000, capped_amount=3000,
            )
        else:
            result = build_risk_constraint_conflicts(
                action="BUY", payload=payload, requested_amount=10000, capped_amount=5000,
            )
        match = [i for i in result["items"] if i["constraint"] == constraint]
        assert match, f"expected conflict item for {constraint}"
        return match[0]

    def test_forbidden_action_item_structure(self):
        item = self._make_conflict_item("forbidden_actions")
        assert item["constraint"] == "forbidden_actions"
        assert item["resolution"] == "reject_trade"
        assert item["requested"] == 5000
        assert item["allowed"] == 0.0
        assert item["reason"] != ""

    def test_cash_available_item_structure(self):
        item = self._make_conflict_item("cash_available")
        assert item["constraint"] == "cash_available"
        assert item["resolution"] in ("cap_amount", "downgrade_to_hold")
        assert item["requested"] > 0
        assert item["allowed"] >= 0
        assert item["reason"] != ""

    def test_min_trade_amount_item_structure(self):
        item = self._make_conflict_item("min_trade_amount")
        assert item["constraint"] == "min_trade_amount"
        assert item["resolution"] == "reject_trade"
        assert item["allowed"] == 0.0
        assert item["reason"] != ""

    def test_max_trade_pct_item_structure(self):
        item = self._make_conflict_item("max_trade_pct")
        assert item["constraint"] == "max_trade_pct"
        assert item["resolution"] in ("cap_amount", "downgrade_to_hold")
        assert item["requested"] > item["allowed"]
        assert item["reason"] != ""

    def test_max_buy_amount_item_structure(self):
        item = self._make_conflict_item("max_buy_amount")
        assert item["constraint"] == "max_buy_amount"
        assert item["resolution"] in ("cap_amount", "downgrade_to_hold")
        assert item["requested"] > item["allowed"]
        assert item["reason"] != ""


class TestRiskConstraintConflictsSummary:
    def test_blocking_conflict_summary(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 0},
            "risk_profile": {"max_trade_pct": 0.05, "liquidity_reserve_pct": 0.1},
            "constraints": {},
        }
        result = build_risk_constraint_conflicts(
            action="BUY", payload=payload, requested_amount=10000, capped_amount=0,
        )
        summary = result["summary"]
        assert summary["has_blocking_conflict"] is True
        assert summary["blocked_trade_count"] >= 1

    def test_capping_conflict_summary(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.05},
            "constraints": {},
        }
        result = build_risk_constraint_conflicts(
            action="BUY", payload=payload, requested_amount=10000, capped_amount=5000,
        )
        summary = result["summary"]
        assert summary["has_capping_conflict"] is True
        assert summary["capped_trade_count"] >= 1

    def test_no_conflict_summary(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.5},
            "constraints": {},
        }
        result = build_risk_constraint_conflicts(
            action="BUY", payload=payload, requested_amount=1000, capped_amount=1000,
        )
        summary = result["summary"]
        assert summary["has_blocking_conflict"] is False
        assert summary["has_capping_conflict"] is False
        assert summary["blocked_trade_count"] == 0
        assert summary["capped_trade_count"] == 0


class TestSingleDecisionRequestedVsCapped:
    def test_requested_amount_from_payload_exceeds_max_trade_pct(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.05},
            "constraints": {},
        }
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            requested_amount=15000,
            capped_amount=5000,
        )
        items = result["items"]
        max_trade_item = next(i for i in items if i["constraint"] == "max_trade_pct")
        assert max_trade_item["requested"] == 15000
        assert max_trade_item["allowed"] == 5000.0
        assert max_trade_item["actual"] == 5000
        assert max_trade_item["resolution"] == "cap_amount"

    def test_requested_amount_from_payload_exceeds_max_buy_amount(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.5},
            "constraints": {"max_buy_amount": 3000},
        }
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            requested_amount=10000,
            capped_amount=3000,
        )
        items = result["items"]
        max_buy_item = next(i for i in items if i["constraint"] == "max_buy_amount")
        assert max_buy_item["requested"] == 10000
        assert max_buy_item["allowed"] == 3000
        assert max_buy_item["actual"] == 3000
        assert max_buy_item["resolution"] == "cap_amount"


class TestTradePlanCapReasonsFromValidatedTrades:
    def test_validated_trade_with_cap_reasons(self):
        payload = {
            "portfolio_context": {"total_value": 100000},
            "risk_profile": {},
            "constraints": {},
        }
        validated_trades = [
            {
                "trade_id": "T1",
                "fund_code": "110011",
                "action": "BUY",
                "requested_amount": 10000,
                "amount": 5000,
                "cap_reasons": ["max_trade_pct (0.05) exceeded"],
            },
        ]
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            trade_plan=validated_trades,
        )
        items = result["items"]
        assert len(items) >= 1
        cap_item = next(i for i in items if i["constraint"] == "max_trade_pct")
        assert cap_item["requested"] == 10000
        assert cap_item["allowed"] == 5000
        assert cap_item["actual"] == 5000
        assert cap_item["resolution"] == "cap_amount"

    def test_validated_trade_forbidden_action(self):
        payload = {
            "portfolio_context": {"total_value": 100000},
            "risk_profile": {},
            "constraints": {"forbidden_actions": ["SELL"]},
        }
        validated_trades = [
            {
                "trade_id": "T1",
                "fund_code": "110011",
                "action": "SELL",
                "requested_amount": 5000,
                "amount": 5000,
            },
        ]
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            trade_plan=validated_trades,
        )
        items = result["items"]
        assert any(i["constraint"] == "forbidden_actions" and i["resolution"] == "reject_trade" for i in items)

    def test_validated_trade_cash_available_cap_reason(self):
        payload = {
            "portfolio_context": {"total_value": 100000},
            "risk_profile": {},
            "constraints": {},
        }
        validated_trades = [
            {
                "trade_id": "T1",
                "fund_code": "110011",
                "action": "BUY",
                "requested_amount": 20000,
                "amount": 3000,
                "cap_reasons": ["cash_available insufficient after liquidity reserve"],
            },
        ]
        result = build_risk_constraint_conflicts(
            action="BUY",
            payload=payload,
            trade_plan=validated_trades,
        )
        items = result["items"]
        cash_item = next(i for i in items if i["constraint"] == "cash_available")
        assert cash_item["requested"] == 20000
        assert cash_item["allowed"] == 3000
