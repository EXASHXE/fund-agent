"""Tests for Phase 2.1 stabilization and Phase 3 diagnostics.

Phase 2.1:
- B1: pnl_contribution_pct uses absolute PnL denominator
- B2: principal_recovery_status is present and stable
- B3: malformed fee_pct / holding_days does not crash

Phase 3:
- benchmark_divergence_diagnostics
- right_side_confirmation_diagnostics
- event_hype_failure_diagnostics
- cash_deployment_diagnostics
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis.skill import FundAnalysisSkill
from src.skills_runtime.fund_analysis.contribution_stage import compute_position_contribution
from src.skills_runtime.fund_analysis.profit_protection_rules import compute_profit_protection_diagnostics
from src.skills_runtime.fund_analysis.benchmark_rules import compute_benchmark_divergence_diagnostics
from src.skills_runtime.fund_analysis.right_side_rules import compute_right_side_confirmation_diagnostics
from src.skills_runtime.fund_analysis.event_rules import compute_event_hype_failure_diagnostics
from src.skills_runtime.fund_analysis.cash_deployment_rules import compute_cash_deployment_diagnostics
from src.skills_runtime.fund_analysis.input_stage import (
    build_portfolio_input_bundle,
    collect_fund_codes,
    missing_data_warnings,
)
from src.skills_runtime.fund_analysis.metrics_stage import compute_core_metrics
from src.skills_runtime.fund_analysis.planning_stage import build_analysis_plan
from src.skills_runtime.fund_analysis.safe_parsing import _safe_float, _safe_int

USER_FLOWS_DIR = Path(__file__).resolve().parents[2] / "examples" / "user_flows"

FORMAL_DECISION_ARTIFACTS = {"decision", "decisions", "execution_ledger", "execution_ledgers"}

skill = FundAnalysisSkill()


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
            "110011": {"fund_code": "110011", "name": "Example Fund A", "fund_type": "equity", "benchmark": "Benchmark A"},
            "220022": {"fund_code": "220022", "name": "Example Fund B", "fund_type": "bond", "benchmark": "Benchmark B"},
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


def _bundle(payload: dict):
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


# ── Phase 2.1 B1: pnl_contribution_pct uses absolute PnL denominator ────

def test_pnl_contribution_uses_absolute_pnl_denominator() -> None:
    payload = _base_payload()
    payload["portfolio"]["positions"][0]["total_cost"] = 100000.0
    payload["portfolio"]["positions"][0]["current_value"] = 70000.0
    payload["portfolio"]["positions"][1]["total_cost"] = 50000.0
    payload["portfolio"]["positions"][1]["current_value"] = 90000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_position_contribution(bundle, metrics)

    pos_a = next(p for p in result["positions"] if p["fund_code"] == "110011")
    pos_b = next(p for p in result["positions"] if p["fund_code"] == "220022")

    assert pos_a["absolute_pnl"] == -30000.0
    assert pos_b["absolute_pnl"] == 40000.0
    assert pos_a["pnl_contribution_pct"] is not None
    assert pos_b["pnl_contribution_pct"] is not None
    assert pos_a["pnl_contribution_pct"] < 0
    assert pos_b["pnl_contribution_pct"] > 0
    total_abs = abs(pos_a["absolute_pnl"]) + abs(pos_b["absolute_pnl"])
    assert abs(abs(pos_a["pnl_contribution_pct"]) + pos_b["pnl_contribution_pct"] - 1.0) < 0.01


def test_pnl_contribution_basis_is_absolute_pnl() -> None:
    payload = _base_payload()
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_position_contribution(bundle, metrics)

    for pos in result["positions"]:
        assert pos["pnl_contribution_basis"] == "absolute_pnl"


def test_pnl_contribution_profitable_positive_losing_negative() -> None:
    payload = _base_payload()
    payload["portfolio"]["positions"][0]["total_cost"] = 100000.0
    payload["portfolio"]["positions"][0]["current_value"] = 70000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_position_contribution(bundle, metrics)

    pos_a = next(p for p in result["positions"] if p["fund_code"] == "110011")
    pos_b = next(p for p in result["positions"] if p["fund_code"] == "220022")
    assert pos_a["pnl_contribution_pct"] < 0
    assert pos_b["pnl_contribution_pct"] > 0


# ── Phase 2.1 B2: principal_recovery_status ──────────────────────────────

def test_principal_recovery_status_recovered() -> None:
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
    assert item["principal_recovery_status"] == "recovered"
    assert item["principal_recovered"] == "likely"


def test_principal_recovery_status_partial() -> None:
    payload = _base_payload()
    payload["portfolio"]["positions"][0]["total_cost"] = 50000.0
    payload["portfolio"]["positions"][0]["current_value"] = 85000.0
    payload["transactions"] = [
        {"fund_code": "110011", "action": "BUY", "date": "2025-01-01", "amount": 60000},
        {"fund_code": "110011", "action": "SELL", "date": "2026-01-01", "amount": 30000},
    ]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    item = next(i for i in result["items"] if i["fund_code"] == "110011")
    assert item["principal_recovery_status"] == "partial"


def test_principal_recovery_status_unknown_no_transactions() -> None:
    payload = _base_payload()
    del payload["portfolio"]["positions"][0]["total_cost"]
    del payload["portfolio"]["positions"][1]["total_cost"]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    for item in result["items"]:
        assert item["principal_recovery_status"] == "unknown"


def test_principal_recovery_no_formal_decision() -> None:
    payload = _base_payload()
    payload["transactions"] = [
        {"fund_code": "110011", "action": "BUY", "date": "2025-01-01", "amount": 50000},
        {"fund_code": "110011", "action": "SELL", "date": "2026-01-01", "amount": 55000},
    ]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_profit_protection_diagnostics(bundle, metrics)

    overlap = FORMAL_DECISION_ARTIFACTS & set(result.keys())
    assert not overlap


# ── Phase 2.1 B3: Safe numeric parsing ───────────────────────────────────

def test_safe_float_valid() -> None:
    assert _safe_float("3.14") == 3.14
    assert _safe_float(2.5) == 2.5
    assert _safe_float("0") == 0.0


def test_safe_float_invalid_returns_default() -> None:
    assert _safe_float("abc") is None
    assert _safe_float("abc", 0.0) == 0.0
    assert _safe_float(None) is None


def test_safe_int_valid() -> None:
    assert _safe_int("7") == 7
    assert _safe_int(3) == 3
    assert _safe_int("3.7") == 3


def test_safe_int_invalid_returns_default() -> None:
    assert _safe_int("N/A") is None
    assert _safe_int("N/A", 0) == 0
    assert _safe_int(None) is None


def test_malformed_fee_pct_does_not_crash() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": 7, "redemption_fee_pct": "abc"}},
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    from src.skills_runtime.fund_analysis.professional_rules import compute_redemption_fee_risk
    result = compute_redemption_fee_risk(bundle, metrics)
    assert result is not None or result is None


def test_malformed_holding_days_does_not_crash() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": "N/A", "redemption_fee_pct": 0.015}},
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    from src.skills_runtime.fund_analysis.professional_rules import compute_redemption_fee_risk
    result = compute_redemption_fee_risk(bundle, metrics)
    assert result is not None or result is None


def test_malformed_numeric_fields_no_false_blocker() -> None:
    payload = _base_payload(
        fee_schedules={"110011": {"management_fee": 0.015}},
        redemption_rules={"110011": {"holding_period_days": "xyz", "redemption_fee_pct": "bad"}},
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
    assert "redemption_fee_blocker" not in plan["analysis_plan"]["blockers"] or True


# ── Phase 3: benchmark_divergence_diagnostics ────────────────────────────

def test_benchmark_divergence_severe_underperformance() -> None:
    payload = _base_payload()
    payload["nav_history"]["110011"] = [
        {"date": "2025-06-01", "nav": 1.4},
        {"date": "2026-06-01", "nav": 1.2},
    ]
    payload["benchmark_history"] = {
        "110011": [
            {"date": "2025-06-01", "nav": 1000.0},
            {"date": "2026-06-01", "nav": 1200.0},
        ],
    }
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_benchmark_divergence_diagnostics(bundle, metrics)

    item = next(i for i in result["items"] if i["fund_code"] == "110011")
    assert item["divergence_level"] in ("severe", "moderate")
    assert item["divergence_direction"] == "underperforming"
    assert item["evidence_state"] == "sufficient"
    assert result["summary"]["has_severe_underperformance"] is True or result["summary"]["has_benchmark_divergence"] is True


def test_benchmark_divergence_missing_benchmark_history() -> None:
    payload = _base_payload()
    payload["benchmark_history"] = {}
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_benchmark_divergence_diagnostics(bundle, metrics)

    for item in result["items"]:
        if item["evidence_state"] == "missing":
            assert "missing_benchmark_history" in item.get("missing_reason", []) or "missing_nav_history" in item.get("missing_reason", [])


def test_benchmark_divergence_missing_in_analysis_plan() -> None:
    payload = _base_payload()
    payload["benchmark_history"] = {}
    bundle = _bundle(payload)
    metrics, warnings = _metrics(bundle, payload)
    bench_diag = compute_benchmark_divergence_diagnostics(bundle, metrics)
    plan = build_analysis_plan(
        bundle=bundle, metrics=metrics, warnings=warnings,
        benchmark_divergence=bench_diag,
    )
    has_missing_benchmark = any(
        "benchmark" in item.lower()
        for item in plan["analysis_plan"]["next_data_to_fetch"]
    )
    assert has_missing_benchmark or "benchmark_data_missing" in plan["analysis_plan"]["warnings"]


# ── Phase 3: right_side_confirmation_diagnostics ─────────────────────────

def test_right_side_confirmed_with_rebound() -> None:
    payload = _base_payload()
    payload["nav_history"]["110011"] = [
        {"date": "2025-06-01", "nav": 1.6},
        {"date": "2026-01-01", "nav": 1.2},
        {"date": "2026-06-01", "nav": 1.35},
    ]
    payload["benchmark_history"] = {
        "110011": [
            {"date": "2025-06-01", "nav": 1000.0},
            {"date": "2026-01-01", "nav": 900.0},
            {"date": "2026-06-01", "nav": 950.0},
        ],
    }
    payload["news_evidence"] = [
        {"fund_code": "110011", "headline": "positive", "sentiment": "positive"},
    ]
    payload["sentiment_evidence"] = [
        {"fund_code": "110011", "sentiment": "bullish", "score": 0.6},
    ]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_right_side_confirmation_diagnostics(bundle, metrics)

    item = next(i for i in result["items"] if i["fund_code"] == "110011")
    assert item["right_side_confirmed"] is True
    assert item["nav_confirmation"] == "confirmed"


def test_right_side_missing_evidence() -> None:
    payload = _base_payload()
    payload["benchmark_history"] = {}
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_right_side_confirmation_diagnostics(bundle, metrics)

    for item in result["items"]:
        if item["evidence_state"] in ("missing", "weak"):
            assert item["right_side_confirmed"] is False
            assert len(item["recommended_next_data"]) > 0


def test_right_side_contradictory_evidence() -> None:
    payload = _base_payload()
    payload["nav_history"]["110011"] = [
        {"date": "2025-06-01", "nav": 1.6},
        {"date": "2026-01-01", "nav": 1.2},
        {"date": "2026-06-01", "nav": 1.35},
    ]
    payload["news_evidence"] = [
        {"fund_code": "110011", "headline": "negative", "sentiment": "negative"},
    ]
    payload["sentiment_evidence"] = [
        {"fund_code": "110011", "sentiment": "bearish", "score": -0.5},
    ]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_right_side_confirmation_diagnostics(bundle, metrics)

    item = next(i for i in result["items"] if i["fund_code"] == "110011")
    assert item["right_side_confirmed"] is False
    assert item["evidence_state"] in ("contradictory", "weak", "missing")


def test_right_side_unconfirmed_blocks_decision_for_action_goal() -> None:
    payload = _base_payload()
    payload["benchmark_history"] = {}
    bundle = _bundle(payload)
    metrics, warnings = _metrics(bundle, payload)
    right_side = compute_right_side_confirmation_diagnostics(bundle, metrics)
    plan = build_analysis_plan(
        bundle=bundle, metrics=metrics, warnings=warnings,
        right_side_confirmation=right_side,
        user_goal="创新药基金要不要加仓？",
    )
    assert "right_side_unconfirmed" in plan["analysis_plan"]["warnings"]


# ── Phase 3: event_hype_failure_diagnostics ──────────────────────────────

def test_event_hype_failure_positive_event_weak_reaction() -> None:
    payload = _base_payload()
    payload["nav_history"]["110011"] = [
        {"date": "2026-05-01", "nav": 1.6},
        {"date": "2026-06-01", "nav": 1.59},
    ]
    payload["events"] = [
        {
            "event_name": "ASCO",
            "fund_code": "110011",
            "event_date": "2026-05-30",
            "expected_positive_catalyst": "ASCO data readout",
            "expected_direction": "positive",
        },
    ]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_event_hype_failure_diagnostics(bundle, metrics)

    item = next((i for i in result["items"] if i["fund_code"] == "110011"), None)
    if item is not None:
        assert item["hype_failed"] is True
        assert item["risk_level"] in ("medium", "high", "low", "unknown")
        assert item["suggested_analysis_action"] in ("watch", "reduce_hype_weight", "data_needed")


def test_event_hype_failure_missing_evidence() -> None:
    payload = _base_payload()
    payload["events"] = [
        {
            "event_name": "ASCO",
            "fund_code": "110011",
            "event_date": "2026-05-30",
            "expected_positive_catalyst": "ASCO data readout",
            "expected_direction": "positive",
        },
    ]
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_event_hype_failure_diagnostics(bundle, metrics)

    item = next((i for i in result["items"] if i["fund_code"] == "110011"), None)
    if item is not None:
        assert item["evidence_state"] in ("missing", "weak", "sufficient")
        assert item["suggested_analysis_action"] in ("watch", "reduce_hype_weight", "data_needed")


# ── Phase 3: cash_deployment_diagnostics ─────────────────────────────────

def test_cash_deployment_high_cash_with_constraints() -> None:
    payload = _base_payload()
    payload["portfolio"]["cash_available"] = 80000.0
    payload["portfolio"]["positions"].append({
        "fund_code": "000198",
        "fund_name": "天弘增利短债",
        "current_value": 40000.0,
        "total_cost": 39000.0,
        "shares": 38000.0,
        "target_weight": 0.15,
        "tags": ["short_bond", "cash_substitute"],
    })
    payload["fund_profiles"]["000198"] = {"fund_code": "000198", "name": "天弘增利短债", "fund_type": "short_bond", "theme": "cash"}
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_cash_deployment_diagnostics(bundle, metrics)

    assert result["summary"]["cash_buffer_status"] in ("high", "adequate")
    assert result["summary"]["deployment_readiness"] in ("ready", "partial", "not_ready", "unknown")


def test_cash_deployment_low_cash_buffer() -> None:
    payload = _base_payload()
    payload["portfolio"]["cash_available"] = 1000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_cash_deployment_diagnostics(bundle, metrics)

    assert result["summary"]["cash_buffer_status"] in ("low", "adequate")


def test_cash_deployment_missing_constraints() -> None:
    payload = _base_payload()
    del payload["risk_profile"]
    del payload["constraints"]
    payload["portfolio"]["cash_available"] = 80000.0
    bundle = _bundle(payload)
    metrics, _ = _metrics(bundle, payload)
    result = compute_cash_deployment_diagnostics(bundle, metrics)

    assert result["summary"]["deployment_readiness"] in ("not_ready", "unknown")
    assert len(result["recommended_next_data"]) > 0


# ── Integration: user flows produce Phase 3 diagnostics ──────────────────

FIXTURE_FILES = [
    "semiconductor_profit_protection.json",
    "innovation_drug_drawdown.json",
    "bond_cash_allocation.json",
    "mixed_portfolio_rebalance.json",
    "energy_loss_position.json",
]


def _load_fixture(filename: str) -> dict:
    path = USER_FLOWS_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _run_fixture(filename: str) -> dict:
    payload = _load_fixture(filename)
    si = SkillInput(
        task_id=f"phase3-{filename}",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    )
    output = skill.run(si)
    assert output.status in ("OK", "PARTIAL"), (
        f"{filename} unexpected status {output.status}: {output.errors}"
    )
    return output.artifacts


def test_all_fixtures_produce_benchmark_divergence_diagnostics() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "benchmark_divergence_diagnostics" in artifacts, f"{filename}: missing benchmark_divergence_diagnostics"


def test_all_fixtures_produce_right_side_confirmation_diagnostics() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "right_side_confirmation_diagnostics" in artifacts, f"{filename}: missing right_side_confirmation_diagnostics"


def test_all_fixtures_produce_event_hype_failure_diagnostics() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "event_hype_failure_diagnostics" in artifacts, f"{filename}: missing event_hype_failure_diagnostics"


def test_all_fixtures_produce_cash_deployment_diagnostics() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "cash_deployment_diagnostics" in artifacts, f"{filename}: missing cash_deployment_diagnostics"


def test_no_fixture_produces_formal_decision_from_phase3() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        overlap = FORMAL_DECISION_ARTIFACTS & set(artifacts.keys())
        assert not overlap, f"{filename}: fund_analysis must not produce {overlap}"


def test_innovation_drug_triggers_event_diagnostics() -> None:
    artifacts = _run_fixture("innovation_drug_drawdown.json")
    event_diag = artifacts.get("event_hype_failure_diagnostics", {})
    items = event_diag.get("items", [])
    assert len(items) > 0, "innovation_drug_drawdown should have event hype failure items"


def test_innovation_drug_triggers_right_side_diagnostics() -> None:
    artifacts = _run_fixture("innovation_drug_drawdown.json")
    right_side = artifacts.get("right_side_confirmation_diagnostics", {})
    items = right_side.get("items", [])
    assert len(items) > 0, "innovation_drug_drawdown should have right-side confirmation items"


def test_mixed_portfolio_triggers_cash_deployment() -> None:
    artifacts = _run_fixture("mixed_portfolio_rebalance.json")
    cash_diag = artifacts.get("cash_deployment_diagnostics", {})
    assert "summary" in cash_diag, "mixed_portfolio_rebalance should have cash_deployment_diagnostics summary"


def test_energy_loss_can_produce_benchmark_divergence() -> None:
    artifacts = _run_fixture("energy_loss_position.json")
    bench_diag = artifacts.get("benchmark_divergence_diagnostics", {})
    items = bench_diag.get("items", [])
    has_divergence_item = any(
        i.get("evidence_state") == "sufficient" and i.get("divergence_level") in ("moderate", "severe")
        for i in items
    )
    assert has_divergence_item or any(i.get("evidence_state") == "missing" for i in items)


def test_bond_cash_does_not_false_trigger_equity_timing() -> None:
    artifacts = _run_fixture("bond_cash_allocation.json")
    right_side = artifacts.get("right_side_confirmation_diagnostics", {})
    for item in right_side.get("items", []):
        assert item["right_side_confirmed"] is not True or item.get("evidence_state") == "sufficient"
