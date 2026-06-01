"""Trade plan contract tests — every trade leg must have required fields,
trade IDs must be deterministic and free of UUIDs.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.portfolio.analysis import apply_trade_constraints, simulate_rebalance

PORTFOLIO = {
    "as_of_date": "2026-06-01",
    "total_value": 200000.0,
    "cash_available": 20000.0,
    "positions": [
        {
            "fund_code": "110011",
            "fund_name": "Broad Market Alpha",
            "current_value": 60000.0,
            "total_cost": 58000.0,
            "target_weight": 0.25,
            "tags": ["broad_market"],
        },
        {
            "fund_code": "000001",
            "fund_name": "Government Bond Stable",
            "current_value": 40000.0,
            "total_cost": 39000.0,
            "target_weight": 0.25,
            "tags": ["fixed_income"],
        },
    ],
}
RISK_PROFILE = {
    "risk_level": "moderate",
    "max_single_fund_weight": 0.3,
    "max_theme_weight": 0.4,
    "max_industry_weight": 0.3,
    "max_trade_pct": 0.1,
    "liquidity_reserve_pct": 0.1,
    "short_term_trade_budget_pct": 0.1,
}
CONSTRAINTS = {"min_trade_amount": 100.0, "forbidden_actions": []}
TARGETS = {"110011": 0.25, "000001": 0.25}

REQUIRED_FIELDS = {
    "trade_id",
    "fund_code",
    "fund_name",
    "action",
    "amount",
    "requested_amount",
    "current_weight",
    "target_weight",
    "capped",
    "cap_reasons",
    "rationale",
    "tags",
    "evidence_refs",
    "risk_flags_refs",
}


def test_every_trade_leg_has_required_fields():
    plan = simulate_rebalance(
        portfolio=PORTFOLIO,
        target_weights=TARGETS,
        constraints=CONSTRAINTS,
        risk_profile=RISK_PROFILE,
        risk_flags_refs=["overweight_single_fund"],
        evidence_refs=["ev:portfolio_allocation_concentration"],
    )
    trades = plan["suggested_trade_plan"]
    assert len(trades) > 0, "expected at least one trade leg"

    for trade in trades:
        missing = REQUIRED_FIELDS - set(trade.keys())
        assert not missing, f"trade leg missing fields: {missing}"

    for trade in trades:
        assert isinstance(trade["evidence_refs"], list)
        assert isinstance(trade["risk_flags_refs"], list)
        assert trade["action"] in ("BUY", "SELL"), f"unexpected action: {trade['action']}"


def test_trade_id_deterministic():
    plan1 = simulate_rebalance(
        portfolio=PORTFOLIO,
        target_weights=TARGETS,
        constraints=CONSTRAINTS,
        risk_profile=RISK_PROFILE,
    )
    plan2 = simulate_rebalance(
        portfolio=PORTFOLIO,
        target_weights=TARGETS,
        constraints=CONSTRAINTS,
        risk_profile=RISK_PROFILE,
    )
    ids1 = [t["trade_id"] for t in plan1["suggested_trade_plan"]]
    ids2 = [t["trade_id"] for t in plan2["suggested_trade_plan"]]
    assert ids1 == ids2, f"trade IDs not deterministic: {ids1} vs {ids2}"


def test_trade_id_no_random_uuid():
    plan = simulate_rebalance(
        portfolio=PORTFOLIO,
        target_weights=TARGETS,
        constraints=CONSTRAINTS,
        risk_profile=RISK_PROFILE,
    )
    for trade in plan["suggested_trade_plan"]:
        tid = trade["trade_id"]
        assert len(tid.split("-")) <= 3, f"trade_id looks UUID-like: {tid}"
        assert "-" not in tid or any(c.isdigit() for c in tid.split("-")[-1]), f"trade_id: {tid}"


def test_risk_flags_refs_passed_through():
    plan = simulate_rebalance(
        portfolio=PORTFOLIO,
        target_weights=TARGETS,
        constraints=CONSTRAINTS,
        risk_profile=RISK_PROFILE,
        risk_flags_refs=["overweight_single_fund", "insufficient_cash_reserve"],
        evidence_refs=["ev:portfolio_risk_flags"],
    )
    for trade in plan["suggested_trade_plan"]:
        assert trade["risk_flags_refs"] == ["overweight_single_fund", "insufficient_cash_reserve"]
        assert trade["evidence_refs"] == ["ev:portfolio_risk_flags"]


def test_apply_trade_constraints_preserves_refs():
    trades = [
        {
            "fund_code": "110011",
            "action": "SELL",
            "amount": 5000.0,
            "evidence_refs": ["ev:test"],
            "risk_flags_refs": ["overweight_single_fund"],
            "rationale": "test",
        },
    ]
    result = apply_trade_constraints(
        trade_plan=trades,
        portfolio=PORTFOLIO,
        constraints=CONSTRAINTS,
        risk_profile=RISK_PROFILE,
    )
    for trade in result:
        assert trade["evidence_refs"] == ["ev:test"]
        assert trade["risk_flags_refs"] == ["overweight_single_fund"]
        assert "rationale" in trade


def test_apply_trade_constraints_adds_rationale():
    trades = [
        {
            "fund_code": "110011",
            "action": "SELL",
            "amount": 5000.0,
        },
    ]
    result = apply_trade_constraints(
        trade_plan=trades,
        portfolio=PORTFOLIO,
        constraints=CONSTRAINTS,
        risk_profile=RISK_PROFILE,
    )
    for trade in result:
        assert "rationale" in trade
        assert trade["rationale"] in (
            "rebalance to target weight",
            "constraint-capped rebalance",
        )
