"""Tests for Phase 2 artifacts: position_contribution, profit_protection_diagnostics,
and redemption fee blocker/warning classification.
"""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis.contribution_stage import compute_position_contribution
from src.skills_runtime.fund_analysis.input_stage import (
    build_portfolio_input_bundle,
    collect_fund_codes,
    missing_data_warnings,
)
from src.skills_runtime.fund_analysis.metrics_stage import compute_core_metrics
from src.skills_runtime.fund_analysis.planning_stage import build_analysis_plan
from src.skills_runtime.fund_analysis.professional_rules import (
    compute_redemption_fee_risk,
    _classify_fee_items,
)
from src.skills_runtime.fund_analysis.profit_protection_rules import (
    compute_profit_protection_diagnostics,
)
from src.skills_runtime.fund_analysis.context import PortfolioInputBundle


FORMAL_DECISION_ARTIFACTS = {"decision", "decisions", "execution_ledger", "execution_ledgers"}


def _base_payload(**overrides) -> dict:
    payload = {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 200000.0,
            "cash_available": 20000.0,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Example Fund A",
                    "current_value": 80000.0,
                    "total_cost": 60000.0,
                    "shares": 50000.0,
                    "target_weight": 0.4,
                    "tags": ["equity", "growth"],
                },
                {
                    "fund_code": "220022",
                    "fund_name": "Example Fund B",
                    "current_value": 100000.0,
                    "total_cost": 95000.0,
                    "shares": 80000.0,
                    "target_weight": 0.5,
                    "tags": ["bond", "income"],
                },
            ],
        },
        "fund_profiles": {
            "110011": {"fund_code": "110011", "name": "Example Fund A", "fund_type": "equity"},
            "220022": {"fund_code": "220022", "name": "Example Fund B", "fund_type": "bond"},
        },
        "nav_history": {
            "110011": [{"date": "2025-06-01", "nav": 1.4}, {"date": "2026-06-01", "nav": 1.6}],
            "220022": [{"date": "2025-06-01", "nav": 1.15}, {"date": "2026-06-01", "nav": 1.25}],
        },
        "holdings": {
            "110011": [{"name": "Stock A", "weight": 0.08, "industry": "tech"}],
            "220022": [{"name": "Bond B", "weight": 0.05, "industry": "govt"}],
        },
        "risk_profile": {"risk_level": "moderate", "max_single_fund_weight": 0.5, "max_theme_weight": 0.4},
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
    }
    payload.update(overrides)
    return payload


def _bundle(payload: dict) -> PortfolioInputBundle:
    positions = payload["portfolio"]["positions"]
    return build_portfolio_input_bundle(
        payload=payload,
        portfolio=payload["portfolio"],
        positions=positions,
        fund_codes=collect_fund_codes(positions),
    )


def _metrics(bundle, payload):
    warnings = missing_data_warnings(
        fund_codes=bundle.fund_codes,
        fund_profiles=bundle.fund_profiles,
        nav_history=bundle.nav_history,
        holdings=bundle.holdings,
    )
    si = SkillInput(task_id="test", step_id="fa", skill_name="fund_analysis", payload=payload)
    return compute_core_metrics(bundle, warnings, si), warnings


# ── position_contribution tests ────────────────────────────────────────────

def test_position_contribution_basic_calculation() -> None:
    payload = _base_payload()
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_position_contribution(bundle, metrics)

    assert "positions" in result
    assert "summary" in result
    positions = result["positions"]
    assert len(positions) == 2

    pos_a = next(p for p in positions if p["fund_code"] == "110011")
    assert pos_a["current_value"] == 80000.0
    assert pos_a["invested_amount"] == 60000.0
    assert pos_a["absolute_pnl"] == 20000.0
    assert abs(pos_a["pnl_pct"] - 0.333333) < 0.001
    assert abs(pos_a["portfolio_weight"] - 0.4) < 0.001
    assert pos_a["pnl_contribution_pct"] is not None


def test_position_contribution_largest_identified() -> None:
    payload = _base_payload()
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_position_contribution(bundle, metrics)

    summary = result["summary"]
    assert summary["largest_value_position"] == "220022"
    assert summary["largest_profit_contributor"] == "110011"


def test_position_contribution_missing_cost_basis() -> None:
    payload = _base_payload()
    for p in payload["portfolio"]["positions"]:
        del p["total_cost"]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_position_contribution(bundle, metrics)

    for pos in result["positions"]:
        assert pos["invested_amount"] is None
        assert pos["absolute_pnl"] is None
        assert pos["pnl_pct"] is None
        assert pos["risk_contribution_hint"] == "low_data"


def test_position_contribution_loss_contributor() -> None:
    payload = _base_payload()
    payload["portfolio"]["positions"][0]["total_cost"] = 100000.0
    payload["portfolio"]["positions"][0]["current_value"] = 70000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_position_contribution(bundle, metrics)

    pos_a = next(p for p in result["positions"] if p["fund_code"] == "110011")
    assert pos_a["absolute_pnl"] == -30000.0
    assert pos_a["pnl_pct"] < 0
    assert result["summary"]["largest_loss_contributor"] == "110011"


# ── profit_protection tests ────────────────────────────────────────────────

def test_profit_protection_high_profit() -> None:
    payload = _base_payload()
    payload["portfolio"]["positions"][0]["total_cost"] = 50000.0
    payload["portfolio"]["positions"][0]["current_value"] = 85000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    item = next(i for i in result["items"] if i["fund_code"] == "110011")
    assert item["profit_level"] in ("high", "very_high")
    assert item["suggested_analysis_action"] in ("watch", "hold_bias", "trim_review", "data_needed")
    assert result["summary"]["has_high_profit_positions"] is True


def test_profit_protection_no_formal_decision() -> None:
    payload = _base_payload()
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    overlap = FORMAL_DECISION_ARTIFACTS & set(result.keys())
    assert not overlap
    for item in result["items"]:
        assert item["suggested_analysis_action"] not in ("BUY", "SELL", "TRIM", "REDUCE", "INCREASE")


def test_profit_protection_transaction_history_insufficient() -> None:
    payload = _base_payload()
    del payload["portfolio"]["positions"][0]["total_cost"]
    del payload["portfolio"]["positions"][1]["total_cost"]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    for item in result["items"]:
        if item["invested_amount"] is None:
            assert item["profit_level"] == "unknown"
            assert item["free_carry_estimate"] == "unknown"


def test_profit_protection_free_carry_with_sells() -> None:
    payload = _base_payload()
    payload["portfolio"]["positions"][0]["total_cost"] = 50000.0
    payload["portfolio"]["positions"][0]["current_value"] = 85000.0
    payload["transactions"] = [
        {"fund_code": "110011", "action": "BUY", "date": "2025-01-01", "amount": 50000},
        {"fund_code": "110011", "action": "SELL", "date": "2026-01-01", "amount": 55000},
    ]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    item = next(i for i in result["items"] if i["fund_code"] == "110011")
    assert item["principal_recovered"] == "likely"
    assert item["free_carry_estimate"] == "likely"


def test_profit_protection_bond_no_false_trigger() -> None:
    payload = _base_payload()
    payload["portfolio"]["positions"][0]["current_value"] = 61000.0
    payload["portfolio"]["positions"][0]["total_cost"] = 60000.0
    payload["portfolio"]["positions"][1]["current_value"] = 101000.0
    payload["portfolio"]["positions"][1]["total_cost"] = 100000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    for item in result["items"]:
        assert item["profit_level"] in ("low", "moderate", "none")


# ── redemption fee blocker/warning tests ───────────────────────────────────

def test_redemption_fee_warning_short_holding_profitable() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": 7, "redemption_fee_pct": 0.005}},
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_redemption_fee_risk(bundle, metrics)

    assert result is not None
    assert result["has_warning"] is True
    assert result["has_blocker"] is False
    fee_items = result["fee_items"]
    assert any(fi["level"] == "warning" for fi in fee_items)


def test_redemption_fee_blocker_short_holding_loss() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": 7, "redemption_fee_pct": 0.015}},
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    payload["portfolio"]["positions"][0]["total_cost"] = 100000.0
    payload["portfolio"]["positions"][0]["current_value"] = 70000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_redemption_fee_risk(bundle, metrics)

    assert result is not None
    assert result["has_blocker"] is True
    fee_items = result["fee_items"]
    assert any(fi["level"] == "blocker" for fi in fee_items)


def test_redemption_fee_blocker_in_analysis_plan() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": 7, "redemption_fee_pct": 0.015}},
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    payload["portfolio"]["positions"][0]["total_cost"] = 100000.0
    payload["portfolio"]["positions"][0]["current_value"] = 70000.0
    bundle = _bundle(payload)
    metrics, warnings = _metrics(bundle, payload)
    from src.skills_runtime.fund_analysis.diagnostics_stage import compute_diagnostics
    diag = compute_diagnostics(bundle, metrics, warnings)
    plan = build_analysis_plan(
        bundle=bundle, metrics=metrics, diagnostics=diag, warnings=warnings,
    )
    assert "redemption_fee_blocker" in plan["analysis_plan"]["blockers"]
    assert plan["analysis_plan"]["decision_support_ready"] is False


def test_redemption_fee_warning_in_plan_warnings() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": 7, "redemption_fee_pct": 0.005}},
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    bundle = _bundle(payload)
    metrics, warnings = _metrics(bundle, payload)
    from src.skills_runtime.fund_analysis.diagnostics_stage import compute_diagnostics
    diag = compute_diagnostics(bundle, metrics, warnings)
    plan = build_analysis_plan(
        bundle=bundle, metrics=metrics, diagnostics=diag, warnings=warnings,
    )
    assert "redemption_fee_warning" in plan["analysis_plan"]["warnings"]


def test_redemption_fee_backward_compatibility() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": 7, "redemption_fee_pct": 0.005}},
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_redemption_fee_risk(bundle, metrics)

    assert result is not None
    assert "affected_funds" in result
    assert "summary" in result
    assert isinstance(result["affected_funds"], list)
    assert len(result["affected_funds"]) > 0
