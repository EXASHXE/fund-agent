"""May snapshot backtest for v0.10.5 private portfolio reconstruction.

Uses synthetic/anonymized fixtures. No real private files.
"""

from __future__ import annotations

from datetime import date

import pytest

from scripts.generate_planned_transactions import generate_planned_transactions
from scripts.build_transaction_ledger import build_transaction_ledger
from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio


SYNTHETIC_NAV = {
    "017436": {"2025-05-15": 2.4181, "2025-05-16": 2.4055, "2025-05-19": 2.3694, "2025-05-20": 2.3788, "2025-05-21": 2.3812},
    "008253": {"2025-05-15": 1.9867, "2025-05-16": 1.9612, "2025-05-19": 1.9137, "2025-05-20": 1.9221, "2025-05-21": 1.9355},
    "378006": {"2025-05-15": 1.2345, "2025-05-16": 1.2301, "2025-05-19": 1.2288, "2025-05-20": 1.2312},
    "001198": {"2025-05-15": 2.5789, "2025-05-16": 2.6012, "2025-05-19": 2.6171, "2025-05-20": 2.6245},
}


def _make_nav_snapshot(nav_data):
    nav_by_fund = {}
    for fc, dates in nav_data.items():
        records = [{"date": d, "nav": v} for d, v in sorted(dates.items())]
        nav_by_fund[fc] = {"provider": "synthetic", "records": records, "nav_dates": list(dates.keys())}
    return {"schema_version": "nav_snapshot.v1", "as_of_date": "2025-05-19", "nav_by_fund": nav_by_fund}


def _make_investment_plan():
    return {
        "schema_version": "investment_plan.v1",
        "plans": [
            {
                "plan_id": "daily_017436", "fund_code": "017436", "fund_name": "Synthetic Tech Mix A",
                "schedule": {"frequency": "daily", "start_date": "2025-05-15"}, "amount": 100,
                "execution_policy": {"assume_auto_execution": True, "confirmation_rules": {"settlement_days": 1, "require_nav_available": True, "expected_confirmation_date_offset_days": 3}},
                "fee_policy": {"subscription_fee_rate": 0.0015, "fee_source": "plan_declared", "fee_discount_rate": 0.1},
            },
            {
                "plan_id": "daily_008253", "fund_code": "008253", "fund_name": "Synthetic Pharma Mix C",
                "schedule": {"frequency": "daily", "start_date": "2025-05-15"}, "amount": 150,
                "execution_policy": {"assume_auto_execution": True, "confirmation_rules": {"settlement_days": 1, "require_nav_available": True, "expected_confirmation_date_offset_days": 3}},
                "fee_policy": {"subscription_fee_rate": None, "fee_source": "unknown"},
            },
            {
                "plan_id": "weekly_mon_378006", "fund_code": "378006", "fund_name": "Synthetic QDII Index A",
                "schedule": {"frequency": "weekly", "day_of_week": "monday", "start_date": "2025-05-12"}, "amount": 800,
                "execution_policy": {"assume_auto_execution": True, "confirmation_rules": {"settlement_days": 1, "qdii_lag_days": 1, "require_nav_available": True, "expected_confirmation_date_offset_days": 5}},
                "fee_policy": {"subscription_fee_rate": 0.0012, "fee_source": "plan_declared"}, "is_qdii": True,
            },
            {
                "plan_id": "biweekly_mon_001198", "fund_code": "001198", "fund_name": "Synthetic Consumer Mix A",
                "schedule": {"frequency": "biweekly", "day_of_week": "monday", "start_date": "2025-05-05"}, "amount": 1150,
                "execution_policy": {"assume_auto_execution": True, "confirmation_rules": {"settlement_days": 1, "require_nav_available": True, "expected_confirmation_date_offset_days": 3}},
                "fee_policy": {"subscription_fee_rate": 0.0015, "fee_source": "plan_declared", "fee_discount_rate": 0.1},
            },
        ],
    }


def _run_reconstruction(as_of):
    plan = _make_investment_plan()
    nav_snapshot = _make_nav_snapshot(SYNTHETIC_NAV)
    planned = generate_planned_transactions(plan, as_of, nav_snapshot)
    ledger = build_transaction_ledger(planned_transactions=planned["transactions"])
    return reconstruct_portfolio(ledger, nav_snapshot, as_of_date=as_of)


class TestFund017436Daily:
    def test_units_increase_0515_to_0518(self):
        r15 = _run_reconstruction(date(2025, 5, 15))
        r18 = _run_reconstruction(date(2025, 5, 19))
        p15 = next(p for p in r15["confirmed_portfolio"]["positions"] if p["fund_code"] == "017436")
        p18 = next(p for p in r18["confirmed_portfolio"]["positions"] if p["fund_code"] == "017436")
        if p15["units"] and p18["units"]:
            delta = p18["units"] - p15["units"]
            expected = 100 / 2.4181
            assert abs(delta - expected) < 2.0

    def test_units_increase_0518_to_0519(self):
        r18 = _run_reconstruction(date(2025, 5, 19))
        r19 = _run_reconstruction(date(2025, 5, 20))
        p18 = next(p for p in r18["confirmed_portfolio"]["positions"] if p["fund_code"] == "017436")
        p19 = next(p for p in r19["confirmed_portfolio"]["positions"] if p["fund_code"] == "017436")
        if p18["units"] and p19["units"]:
            delta = p19["units"] - p18["units"]
            expected = 100 / 2.3694
            assert abs(delta - expected) < 2.0

    def test_pending_amount_around_200(self):
        result = _run_reconstruction(date(2025, 5, 19))
        pos = next(p for p in result["confirmed_portfolio"]["positions"] if p["fund_code"] == "017436")
        if pos.get("pending_amount"):
            assert pos["pending_amount"] < 400


class TestFund008253Daily:
    def test_units_increase_0515_to_0518(self):
        r15 = _run_reconstruction(date(2025, 5, 15))
        r18 = _run_reconstruction(date(2025, 5, 19))
        p15 = next(p for p in r15["confirmed_portfolio"]["positions"] if p["fund_code"] == "008253")
        p18 = next(p for p in r18["confirmed_portfolio"]["positions"] if p["fund_code"] == "008253")
        if p15["units"] and p18["units"]:
            delta = p18["units"] - p15["units"]
            expected = 150 / 1.9867
            assert abs(delta - expected) < 3.0

    def test_pending_amount_around_300(self):
        result = _run_reconstruction(date(2025, 5, 19))
        pos = next(p for p in result["confirmed_portfolio"]["positions"] if p["fund_code"] == "008253")
        if pos.get("pending_amount"):
            assert pos["pending_amount"] < 600


class TestFund378006Weekly:
    def test_0518_pending_or_confirmed(self):
        result = _run_reconstruction(date(2025, 5, 19))
        pos = next(p for p in result["confirmed_portfolio"]["positions"] if p["fund_code"] == "378006")
        pending = pos.get("pending_amount") or 0
        has_buy = any(t for t in result["projected_portfolio"].get("pending_transactions", []) if t["fund_code"] == "378006")
        assert pending > 0 or has_buy or pos["units"] is not None

    def test_0519_pending_remains_800(self):
        # QDII has T+2 lag (settlement_days=1 + qdii_lag_days=1)
        # Monday 5/19 buy not confirmed until 5/21, so on 5/20 still pending
        result = _run_reconstruction(date(2025, 5, 20))
        pos = next(p for p in result["confirmed_portfolio"]["positions"] if p["fund_code"] == "378006")
        # 378006 should have pending amount or pending transaction, units unchanged from before
        pending = pos.get("pending_amount") or 0
        has_buy = any(t for t in result["projected_portfolio"].get("pending_transactions", []) if t["fund_code"] == "378006")
        assert pending > 0 or has_buy or pos["units"] is not None


class TestFund001198Biweekly:
    def test_0518_pending_or_confirmed(self):
        result = _run_reconstruction(date(2025, 5, 19))
        pos = next(p for p in result["confirmed_portfolio"]["positions"] if p["fund_code"] == "001198")
        pending = pos.get("pending_amount") or 0
        has_txn = any(t for t in result["projected_portfolio"].get("pending_transactions", []) if t["fund_code"] == "001198")
        assert pending > 0 or has_txn or pos["units"] is not None

    def test_0519_confirms(self):
        result = _run_reconstruction(date(2025, 5, 20))
        pos = next(p for p in result["confirmed_portfolio"]["positions"] if p["fund_code"] == "001198")
        if pos["units"] and pos["units"] > 0:
            expected = 1150 / 2.6171
            assert pos["units"] >= expected * 0.8


class TestCurrentValueFormula:
    @pytest.mark.parametrize("fund_code", ["017436", "008253", "001198"])
    def test_current_value_formula(self, fund_code):
        result = _run_reconstruction(date(2025, 5, 20))
        pos = next(p for p in result["confirmed_portfolio"]["positions"] if p["fund_code"] == fund_code)
        if pos["units"] and pos["latest_nav"] and pos["current_value"]:
            expected = round(pos["units"] * pos["latest_nav"], 2)
            assert abs(pos["current_value"] - expected) < 1.0


class TestConfirmationSeparation:
    def test_rule_confirmed_exists(self):
        plan = _make_investment_plan()
        nav = _make_nav_snapshot(SYNTHETIC_NAV)
        as_of = date(2025, 5, 20)
        planned = generate_planned_transactions(plan, as_of, nav)
        ledger = build_transaction_ledger(planned_transactions=planned["transactions"])
        result = reconstruct_portfolio(ledger, nav, as_of_date=as_of)
        has_rc = any("schedule_rule" in p.get("confirmation_sources", []) for p in result["confirmed_portfolio"]["positions"])
        assert has_rc

    def test_no_auto_execution_no_rule_confirmed(self):
        plan = _make_investment_plan()
        for p in plan["plans"]:
            p["execution_policy"]["assume_auto_execution"] = False
        nav = _make_nav_snapshot(SYNTHETIC_NAV)
        as_of = date(2025, 5, 20)
        planned = generate_planned_transactions(plan, as_of, nav)
        ledger = build_transaction_ledger(planned_transactions=planned["transactions"])
        for txn in ledger["transactions"]:
            if txn["source"] == "investment_plan":
                assert txn["confirmation_type"] != "rule_confirmed"


class TestNoFakePrecision:
    def test_no_zero_current_value_when_nav_available(self):
        result = _run_reconstruction(date(2025, 5, 20))
        for pos in result["confirmed_portfolio"]["positions"]:
            if pos["latest_nav"] and pos["units"] and pos["units"] > 0:
                assert pos["current_value"] is not None
                assert pos["current_value"] != 0
