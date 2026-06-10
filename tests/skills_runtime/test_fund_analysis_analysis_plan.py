"""Tests for fund_analysis analysis_plan and evidence_gap_diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

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
from src.skills_runtime.fund_analysis.planning_stage import build_analysis_plan

USER_FLOWS_DIR = Path(__file__).resolve().parents[2] / "examples" / "user_flows"

FORMAL_DECISION_ARTIFACTS = {
    "decision",
    "decisions",
    "execution_ledger",
    "execution_ledgers",
}


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
        task_id="analysis-plan-test",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    )


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


def _run_plan(payload: dict, user_goal: str | None = None, run_diagnostics: bool = False) -> dict:
    bundle = _bundle(payload)
    warnings = _warnings(bundle)
    skill_input = _skill_input(payload)
    metrics = compute_core_metrics(bundle, warnings, skill_input)
    optional = build_optional_summaries(bundle, metrics, skill_input, warnings)
    diagnostics: dict = {}
    if run_diagnostics:
        from src.skills_runtime.fund_analysis.diagnostics_stage import compute_diagnostics
        diagnostics = compute_diagnostics(bundle, metrics, warnings)
    return build_analysis_plan(
        bundle=bundle,
        metrics=metrics,
        optional=optional,
        diagnostics=diagnostics,
        warnings=warnings,
        user_goal=user_goal,
    )


def test_missing_holdings_blocks_decision_support() -> None:
    payload = _base_payload()
    del payload["portfolio"]["positions"]
    payload["portfolio"]["positions"] = []

    from src.skills_runtime.fund_analysis.planning_stage import _build_evidence_gap_diagnostics
    from src.skills_runtime.fund_analysis.context import PortfolioInputBundle

    empty_bundle = PortfolioInputBundle(
        payload=payload,
        portfolio=payload["portfolio"],
        positions=[],
        fund_codes=[],
        fund_profiles=payload.get("fund_profiles", {}),
        nav_history=payload.get("nav_history", {}),
        holdings=payload.get("holdings", {}),
        risk_profile=payload.get("risk_profile", {}),
        constraints=payload.get("constraints", {}),
        transactions=[],
        dca_plans={},
        market_scenario={},
        benchmarks={},
        benchmark_history={},
        peer_group={},
        factor_exposures={},
        manager_profiles={},
        fee_schedules={},
        redemption_rules={},
        research_planning=False,
        nav_data={},
        as_of_date="2026-06-01",
    )

    gap = _build_evidence_gap_diagnostics(empty_bundle, None, None)
    assert gap["missing_holdings"] is True
    plan = build_analysis_plan(
        bundle=empty_bundle,
        metrics=None,
        optional=None,
        diagnostics={},
        warnings=[],
    )
    assert plan["analysis_plan"]["decision_support_ready"] is False
    assert "missing_holdings" in plan["analysis_plan"]["missing_inputs"]


def test_holdings_present_no_transactions() -> None:
    payload = _base_payload()
    result = _run_plan(payload)

    plan = result["analysis_plan"]
    gap = result["evidence_gap_diagnostics"]

    assert "holdings" in plan["available_inputs"]
    assert gap["missing_transaction_history"] is True
    assert "missing_transaction_history" in plan["missing_inputs"]
    assert plan["decision_support_ready"] is False
    assert any("transaction" in item.lower() for item in plan["next_data_to_fetch"])


def test_missing_recent_news_recommends_news_research() -> None:
    payload = _base_payload()
    result = _run_plan(payload)

    plan = result["analysis_plan"]
    gap = result["evidence_gap_diagnostics"]

    assert gap["missing_recent_news"] is True
    assert "news_research" in plan["recommended_skill_sequence"]
    assert plan["decision_support_ready"] is False
    assert "missing_recent_news" in plan["blockers"]


def test_missing_benchmark_data_recommends_mcp_capability() -> None:
    payload = _base_payload()
    result = _run_plan(payload)

    plan = result["analysis_plan"]
    gap = result["evidence_gap_diagnostics"]

    assert gap["missing_benchmark_data"] is True
    assert "benchmark_price_history" in plan["recommended_mcp_capabilities"]
    assert any("benchmark" in item.lower() for item in plan["next_data_to_fetch"])


def test_missing_sentiment_with_action_goal_recommends_sentiment_analysis() -> None:
    payload = _base_payload()
    result = _run_plan(payload, user_goal="半导体盈利很多，要不要减仓？")

    plan = result["analysis_plan"]
    assert "sentiment_analysis" in plan["recommended_skill_sequence"]


def test_missing_sentiment_without_action_goal_does_not_recommend_sentiment() -> None:
    payload = _base_payload()
    result = _run_plan(payload, user_goal="帮我看看组合结构")

    plan = result["analysis_plan"]
    assert "sentiment_analysis" not in plan["recommended_skill_sequence"]


def test_conservative_decision_support_readiness() -> None:
    payload = _base_payload()
    result = _run_plan(payload)

    plan = result["analysis_plan"]
    assert plan["decision_support_ready"] is False


def test_sufficient_evidence_decision_support_ready() -> None:
    payload = _base_payload(
        fee_schedules={
            "110011": {"management_fee": 0.015},
            "220022": {"management_fee": 0.01},
        },
        redemption_rules={
            "110011": {"holding_period_days": 7, "redemption_fee_pct": 0.001},
            "220022": {"holding_period_days": 7, "redemption_fee_pct": 0.001},
        },
    )
    result = _run_plan(payload)

    plan = result["analysis_plan"]
    gap = result["evidence_gap_diagnostics"]

    assert gap["missing_recent_news"] is True
    assert plan["decision_support_ready"] is False


def test_analysis_plan_does_not_contain_formal_decision_artifacts() -> None:
    payload = _base_payload()
    result = _run_plan(payload)

    plan = result["analysis_plan"]
    assert not (FORMAL_DECISION_ARTIFACTS & set(plan))


def test_evidence_gap_diagnostics_has_expected_keys() -> None:
    payload = _base_payload()
    result = _run_plan(payload)

    gap = result["evidence_gap_diagnostics"]
    expected_keys = {
        "missing_holdings",
        "missing_transaction_history",
        "missing_fund_metadata",
        "missing_fee_schedule",
        "missing_nav_history",
        "missing_benchmark_data",
        "missing_recent_news",
        "missing_sentiment",
        "missing_holdings_detail",
        "missing_user_constraints",
        "missing_risk_preference",
        "details",
    }
    assert expected_keys <= set(gap.keys())


def test_evidence_gap_details_have_severity_and_code() -> None:
    payload = _base_payload()
    result = _run_plan(payload)

    details = result["evidence_gap_diagnostics"]["details"]
    assert isinstance(details, list)
    assert len(details) > 0
    for detail in details:
        assert "code" in detail
        assert "severity" in detail
        assert "recommended_next_data" in detail


def test_redemption_fee_blocker_detected() -> None:
    payload = _base_payload(
        fee_schedules={
            "110011": {"management_fee": 0.015},
        },
        redemption_rules={
            "110011": {"holding_period_days": 30, "redemption_fee_pct": 0.015},
        },
        transactions=[
            {"fund_code": "110011", "action": "BUY", "date": "2026-05-28", "amount": 30000},
        ],
    )
    payload["portfolio"]["positions"][0]["total_cost"] = 100000.0
    payload["portfolio"]["positions"][0]["current_value"] = 70000.0
    result = _run_plan(payload, run_diagnostics=True)

    plan = result["analysis_plan"]
    assert "redemption_fee_blocker" in plan["blockers"]
    assert plan["decision_support_ready"] is False


class TestUserFlowFixtures:
    USER_FLOW_FILES = [
        "semiconductor_profit_protection.json",
        "innovation_drug_drawdown.json",
        "bond_cash_allocation.json",
        "mixed_portfolio_rebalance.json",
        "energy_loss_position.json",
    ]

    @staticmethod
    def _load_fixture(filename: str) -> dict:
        path = USER_FLOWS_DIR / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def test_all_fixture_files_exist(self) -> None:
        for filename in self.USER_FLOW_FILES:
            path = USER_FLOWS_DIR / filename
            assert path.exists(), f"Missing fixture: {filename}"

    def test_all_fixtures_are_valid_json(self) -> None:
        for filename in self.USER_FLOW_FILES:
            data = self._load_fixture(filename)
            assert isinstance(data, dict)

    def test_all_fixtures_have_required_top_level_keys(self) -> None:
        required_keys = {
            "user_question",
            "portfolio",
            "fund_profiles",
            "nav_history",
            "fee_schedules",
            "redemption_rules",
            "benchmarks",
            "benchmark_history",
            "news_evidence",
            "sentiment_evidence",
            "constraints",
        }
        for filename in self.USER_FLOW_FILES:
            data = self._load_fixture(filename)
            missing = required_keys - set(data.keys())
            assert not missing, f"{filename} missing keys: {missing}"

    def test_all_fixtures_have_portfolio_positions(self) -> None:
        for filename in self.USER_FLOW_FILES:
            data = self._load_fixture(filename)
            portfolio = data.get("portfolio", {})
            positions = portfolio.get("positions", [])
            assert isinstance(positions, list), f"{filename} positions not a list"
            assert len(positions) > 0, f"{filename} has no positions"

    def test_no_fixture_depends_on_network_or_credentials(self) -> None:
        for filename in self.USER_FLOW_FILES:
            data = self._load_fixture(filename)
            text = json.dumps(data)
            assert "api_key" not in text.lower()
            assert "password" not in text.lower()
            assert "secret" not in text.lower()
            assert "token" not in text.lower()
