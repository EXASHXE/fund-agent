"""Stage-level tests for the fund_analysis runtime pipeline."""

from __future__ import annotations

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis.input_stage import (
    build_portfolio_input_bundle,
    collect_fund_codes,
    missing_data_warnings,
)
from src.skills_runtime.fund_analysis.metrics_stage import compute_core_metrics
from src.skills_runtime.fund_analysis.optional_data_stage import (
    build_optional_summaries,
)
from src.skills_runtime.fund_analysis.report_stage import (
    assemble_analysis_report_and_artifacts,
)

FORMAL_DECISION_ARTIFACTS = {
    "decision",
    "decisions",
    "execution_ledger",
    "execution_ledgers",
}


def test_build_portfolio_input_bundle_preserves_payload_fields() -> None:
    payload = _payload()
    bundle = _bundle(payload)

    assert bundle.payload is payload
    assert bundle.portfolio is payload["portfolio"]
    assert bundle.positions is payload["portfolio"]["positions"]
    assert bundle.fund_codes == ["110011", "220022"]
    assert bundle.fund_profiles == payload["fund_profiles"]
    assert bundle.nav_history == payload["nav_history"]
    assert bundle.holdings == payload["holdings"]
    assert bundle.risk_profile == payload["risk_profile"]
    assert bundle.constraints == payload["constraints"]
    assert bundle.transactions == []
    assert bundle.dca_plans == {}
    assert bundle.market_scenario == {}
    assert bundle.research_planning is False
    assert bundle.nav_data == {"110011": 1.6, "220022": 1.25}
    assert bundle.as_of_date == "2026-06-01"


def test_compute_core_metrics_returns_expected_structures() -> None:
    payload = _payload()
    bundle = _bundle(payload)
    warnings = _warnings(bundle)

    metrics = compute_core_metrics(bundle, warnings, _skill_input(payload))

    assert metrics.position_weights
    assert metrics.concentration
    assert metrics.exposures
    assert metrics.industry_exposure
    assert metrics.fund_metrics
    assert isinstance(metrics.risk_flags, list)
    assert metrics.pnl_summary is not None
    assert metrics.trade_budget is not None
    assert metrics.normalized_transactions == []
    assert metrics.ledger_summary is None
    assert metrics.cost_basis_summary is None
    assert metrics.reconciliation is None
    assert metrics.trading_flags == []
    assert metrics.scenario_flags == []
    assert metrics.portfolio_summary["position_count"] == 2


def test_build_optional_summaries_returns_none_when_optional_data_absent() -> None:
    payload = _payload()
    bundle = _bundle(payload)
    warnings = _warnings(bundle)
    metrics = compute_core_metrics(bundle, warnings, _skill_input(payload))

    optional = build_optional_summaries(
        bundle,
        metrics,
        _skill_input(payload),
        warnings,
    )

    assert optional.benchmark_summary is None
    assert optional.peer_summary is None
    assert optional.fee_summary is None
    assert optional.redemption_summary is None
    assert optional.factor_summary is None
    assert optional.manager_summary is None
    assert optional.query_plan is None


def test_build_optional_summaries_surfaces_fee_and_redemption_data() -> None:
    payload = _payload(
        fee_schedules={
            "110011": {"management_fee": 0.015, "custody_fee": 0.002},
            "220022": {"total_expense_ratio": 0.01},
        },
        redemption_rules={
            "110011": {"lockup_days": 30, "redemption_fee_pct": 0.005},
            "220022": {"holding_period_days": 7},
        },
    )
    bundle = _bundle(payload)
    warnings = _warnings(bundle)
    metrics = compute_core_metrics(bundle, warnings, _skill_input(payload))

    optional = build_optional_summaries(
        bundle,
        metrics,
        _skill_input(payload),
        warnings,
    )

    assert optional.fee_summary is not None
    assert optional.fee_summary["funds_with_fees"] == ["110011", "220022"]
    assert optional.redemption_summary is not None
    assert optional.redemption_summary["funds_with_rules"] == ["110011", "220022"]


def test_assemble_analysis_report_and_artifacts_includes_report_outputs() -> None:
    payload = _payload()
    bundle = _bundle(payload)
    warnings = _warnings(bundle)
    skill_input = _skill_input(payload)
    metrics = compute_core_metrics(bundle, warnings, skill_input)
    optional = build_optional_summaries(bundle, metrics, skill_input, warnings)

    artifacts_bundle = assemble_analysis_report_and_artifacts(
        bundle=bundle,
        metrics=metrics,
        optional=optional,
        source_of_truth="host_portfolio",
        derived_snapshot=None,
        reconciliation_report=None,
        warnings=warnings,
    )
    artifacts = artifacts_bundle.artifacts

    assert artifacts["portfolio_summary"]
    assert artifacts["position_summary"]
    assert artifacts["fund_analysis_report"]
    assert artifacts["report_sections"]
    assert artifacts["report_outline"]
    assert artifacts["report_quality_gate"]
    assert "warnings" in artifacts
    assert not (FORMAL_DECISION_ARTIFACTS & set(artifacts))


def _bundle(payload: dict):
    positions = payload["portfolio"]["positions"]
    return build_portfolio_input_bundle(
        payload=payload,
        portfolio=payload["portfolio"],
        positions=positions,
        fund_codes=collect_fund_codes(positions),
    )


def _warnings(bundle) -> list[str]:
    return missing_data_warnings(
        fund_codes=bundle.fund_codes,
        fund_profiles=bundle.fund_profiles,
        nav_history=bundle.nav_history,
        holdings=bundle.holdings,
    )


def _skill_input(payload: dict) -> SkillInput:
    return SkillInput(
        task_id="fund-analysis-stage-test",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    )


def _payload(**overrides) -> dict:
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
                    "total_cost": 75000.0,
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
            "110011": {
                "fund_code": "110011",
                "name": "Example Fund A",
                "fund_type": "equity",
            },
            "220022": {
                "fund_code": "220022",
                "name": "Example Fund B",
                "fund_type": "bond",
            },
        },
        "nav_history": {
            "110011": [
                {"date": "2025-06-01", "nav": 1.4},
                {"date": "2026-06-01", "nav": 1.6},
            ],
            "220022": [
                {"date": "2025-06-01", "nav": 1.15},
                {"date": "2026-06-01", "nav": 1.25},
            ],
        },
        "holdings": {
            "110011": [{"name": "Stock A", "weight": 0.08, "industry": "tech"}],
            "220022": [{"name": "Bond B", "weight": 0.05, "industry": "govt"}],
        },
        "risk_profile": {
            "risk_level": "moderate",
            "max_single_fund_weight": 0.5,
            "max_theme_weight": 0.4,
            "max_trade_pct": 0.1,
            "liquidity_reserve_pct": 0.1,
            "short_term_trade_budget_pct": 0.1,
        },
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
    }
    payload.update(overrides)
    return payload
