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
