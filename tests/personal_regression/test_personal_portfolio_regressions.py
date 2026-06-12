"""Personal portfolio regression pack tests.

These scenarios are separate from generic E2E fixtures. They represent
recurring Chinese retail mutual-fund portfolio questions and verify the full
deterministic workflow:

fund_analysis -> EvidenceGraph -> optional decision_support -> final report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from tests.end_to_end.helpers import (
    assert_no_execution_fields,
    assert_no_formal_decision_in_output,
)
from tests.helpers.personal_regression_runner import (
    FIXTURES_DIR,
    REQUIRED_EXPECTED_KEYS,
    REQUIRED_FIXTURE_FIELDS,
    PersonalRegressionResult,
    flatten_report_text,
    list_personal_regression_fixtures,
    load_personal_regression_fixture,
    run_personal_regression_fixture,
    section_text,
    validate_personal_regression_result,
)


def _fixture_paths() -> list[Path]:
    return list_personal_regression_fixtures()


def _scenario_ids() -> list[str]:
    return [path.stem for path in _fixture_paths()]


def _run_workflow(scenario_id: str) -> tuple[dict, PersonalRegressionResult, SkillOutput]:
    path = FIXTURES_DIR / f"{scenario_id}.json"
    fixture = load_personal_regression_fixture(path)
    result = run_personal_regression_fixture(fixture, fixture_path=path)
    validate_personal_regression_result(result, fixture["expected_behavior"])
    fa_output = FundAnalysisSkill().run(
        SkillInput(
            task_id=fixture["scenario_id"],
            step_id="personal-fa",
            skill_name="fund_analysis",
            payload=fixture,
        )
    )
    return fixture, result, fa_output


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda p: p.stem)
def test_fixture_shape_and_expected_behavior_contract(path: Path):
    fixture = load_personal_regression_fixture(path)
    missing_fields = REQUIRED_FIXTURE_FIELDS - set(fixture)
    assert not missing_fields, f"{path.name} missing fields: {sorted(missing_fields)}"
    assert fixture["scenario_id"] == path.stem

    eb = fixture.get("expected_behavior", {})
    missing_expected = REQUIRED_EXPECTED_KEYS - set(eb)
    assert not missing_expected, (
        f"{path.name} missing expected_behavior keys: {sorted(missing_expected)}"
    )
    assert eb["expected_no_broker_execution"] is True


def test_personal_regression_pack_has_at_least_fourteen_scenarios():
    assert len(_fixture_paths()) >= 14


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_personal_portfolio_regression_matches_expected_behavior(scenario_id: str):
    fixture, result, fa_output = _run_workflow(scenario_id)
    eb = fixture["expected_behavior"]

    assert_no_formal_decision_in_output(fa_output)
    assert_no_execution_fields(fixture, f"fixture:{scenario_id}")
    assert_no_execution_fields(result.fund_analysis_output, f"fund_analysis:{scenario_id}")
    assert_no_execution_fields(result.evidence_graph, f"evidence:{scenario_id}")
    assert_no_execution_fields(result.final_report, f"report:{scenario_id}")

    for expected_intent in eb["expected_advisory_intents"]:
        assert expected_intent in result.advisory_intents

    summary = result.final_report["workflow_summary"]
    safety = result.final_report["safety_boundary"]
    assert summary["report_status"] == eb["expected_report_status"]
    assert summary["decision_status"] == eb["expected_decision_status"]
    assert safety["formal_decision_source"] == eb["expected_formal_source"]
    assert safety["no_broker_execution"] is True

    section_ids = {
        section.get("id")
        for section in result.final_report.get("user_facing_sections", [])
        if isinstance(section, dict)
    }
    for section_id in eb["expected_required_report_sections"]:
        assert section_id in section_ids

    chinese_summary = " ".join(result.final_report.get("chinese_summary", {}).get("bullets", []))
    for phrase in eb["expected_chinese_summary_contains"]:
        assert phrase in chinese_summary, f"chinese_summary missing phrase: {phrase}"

    direct_answer = section_text(result.final_report, "direct_answer")
    for phrase in eb["expected_direct_answer_contains"]:
        assert phrase in direct_answer, f"direct_answer missing phrase: {phrase}"

    action_boundary = section_text(result.final_report, "action_boundary")
    for phrase in eb["expected_action_boundary_contains"]:
        assert phrase in action_boundary, f"action_boundary missing phrase: {phrase}"

    missing_text = (
        section_text(result.final_report, "evidence_status")
        + " "
        + section_text(result.final_report, "limitations")
    )
    for phrase in eb["expected_missing_data_contains"]:
        assert phrase in missing_text

    full_text = json.dumps(
        [result.fund_analysis_output, result.evidence_graph,
         result.decision_support_output, result.final_report],
        ensure_ascii=False, sort_keys=True, default=str,
    )
    for forbidden in eb["expected_no_fabrication_fields"]:
        assert forbidden not in full_text

    if eb["decision_support_called"]:
        assert result.decision_support_output is not None
        assert_no_execution_fields(result.decision_support_output, f"decision_support:{scenario_id}")
        artifacts = result.decision_support_output.get("artifacts", {})
        ledger = artifacts.get("execution_ledger")
        assert isinstance(ledger, dict)
        ledger_summary = ledger.get("ledger_summary", {})
        assert ledger_summary.get("active_decision_count") == eb["expected_active_decision_count"]
        assert ledger_summary.get("passive_decision_count") == eb["expected_passive_decision_count"]
        assert ledger_summary.get("blocked_decision_count") == eb["expected_blocked_decision_count"]
        assert ledger_summary.get("downgraded_decision_count") == eb["expected_downgraded_decision_count"]

        reason_text = json.dumps(
            [artifacts.get("decision"), artifacts.get("decisions"), ledger],
            ensure_ascii=False, sort_keys=True, default=str,
        )
        for fragment in eb["expected_reason_code_contains"]:
            assert fragment in reason_text

        conflicts = artifacts.get("risk_constraint_conflicts", {})
        assert artifacts.get("evidence_anchor_diagnostics")
        conflict_text = json.dumps(conflicts, ensure_ascii=False, sort_keys=True, default=str)
        for kind in eb["expected_risk_conflict_kinds"]:
            assert kind in conflict_text

        if eb.get("expected_action_outcome") == "allowed":
            decision = artifacts.get("decision", {})
            action = decision.get("action", "")
            assert action in {"BUY", "SELL", "INCREASE", "REDUCE"}, (
                f"expected active action, got {action}"
            )
            amount = decision.get("execution_amount", 0)
            assert amount >= eb.get("expected_min_final_execution_amount", 0)
            assert amount <= eb.get("expected_max_final_execution_amount", float("inf"))
            if eb.get("expected_preserve_requested_action"):
                requested = fixture.get("requested_action", "")
                if requested:
                    assert action == requested, (
                        f"requested_action {requested} not preserved, got {action}"
                    )
    else:
        assert result.decision_support_output is None
        assert summary["decision_status"] == "NO_FORMAL_DECISION"
        assert safety["formal_decision_source"] == "none"


def test_semiconductor_partial_reduce_allowed():
    fixture, result, _ = _run_workflow("semiconductor_profit_recovery_partial_reduce_allowed_zh")
    eb = fixture["expected_behavior"]

    assert eb["decision_support_called"] is True
    assert result.decision_support_output is not None

    ds_artifacts = result.decision_support_output.get("artifacts", {})
    decision = ds_artifacts.get("decision", {})
    action = decision.get("action", "")
    assert action in {"REDUCE", "SELL"}, f"expected REDUCE/SELL, got {action}"

    amount = decision.get("execution_amount", 0)
    assert amount > 0, f"expected positive execution_amount, got {amount}"
    assert amount <= fixture.get("target_trade_amount", float("inf"))

    ledger = ds_artifacts.get("execution_ledger", {})
    ledger_summary = ledger.get("ledger_summary", {}) if isinstance(ledger, dict) else {}
    assert ledger_summary.get("active_decision_count", 0) >= 1
    assert ledger_summary.get("blocked_decision_count", 0) == 0

    assert ds_artifacts.get("evidence_anchor_diagnostics") is not None

    flat = flatten_report_text(result.final_report)
    assert any(kw in flat for kw in ("回收本金", "部分减仓", "盈利保护"))

    assert "broker_order_id" not in json.dumps(result.final_report, ensure_ascii=False)


def test_cash_deployment_partial_buy_allowed():
    fixture, result, _ = _run_workflow("cash_deployment_partial_buy_allowed_with_budget_zh")
    eb = fixture["expected_behavior"]

    assert eb["decision_support_called"] is True
    assert result.decision_support_output is not None

    ds_artifacts = result.decision_support_output.get("artifacts", {})
    decision = ds_artifacts.get("decision", {})
    action = decision.get("action", "")
    assert action in {"BUY", "INCREASE"}, f"expected BUY/INCREASE, got {action}"

    amount = decision.get("execution_amount", 0)
    assert amount > 0, f"expected positive execution_amount, got {amount}"
    assert amount <= fixture.get("target_trade_amount", float("inf"))

    ledger = ds_artifacts.get("execution_ledger", {})
    ledger_summary = ledger.get("ledger_summary", {}) if isinstance(ledger, dict) else {}
    assert ledger_summary.get("active_decision_count", 0) >= 1
    assert ledger_summary.get("blocked_decision_count", 0) == 0

    flat = flatten_report_text(result.final_report)
    assert any(kw in flat for kw in ("安全垫", "可动用资金", "可部署"))

    assert "broker_order_id" not in json.dumps(result.final_report, ensure_ascii=False)


def test_blocked_scenarios_remain_blocked():
    blocked_scenarios = [
        "short_holding_7day_fee_sell_zh",
        "oil_gas_loss_position_rebalance_zh",
    ]
    for scenario_id in blocked_scenarios:
        fixture, result, _ = _run_workflow(scenario_id)
        eb = fixture["expected_behavior"]
        assert eb["expected_action_outcome"] in ("blocked", "downgraded"), (
            f"{scenario_id} should be blocked/downgraded"
        )
        summary = result.final_report["workflow_summary"]
        assert summary["decision_status"] in ("BLOCKED", "DOWNGRADED"), (
            f"{scenario_id} decision_status should be BLOCKED/DOWNGRADED, got {summary['decision_status']}"
        )
        if result.decision_support_output is not None:
            ds_artifacts = result.decision_support_output.get("artifacts", {})
            ledger = ds_artifacts.get("execution_ledger", {})
            ledger_summary = ledger.get("ledger_summary", {}) if isinstance(ledger, dict) else {}
            assert ledger_summary.get("active_decision_count", 0) == 0, (
                f"{scenario_id} should have no active decisions"
            )


def test_mixed_portfolio_report_only_rich():
    fixture, result, _ = _run_workflow("mixed_portfolio_report_only_zh")
    eb = fixture["expected_behavior"]

    assert eb["decision_support_called"] is False
    assert result.decision_support_output is None

    summary = result.final_report["workflow_summary"]
    assert summary["decision_status"] == "NO_FORMAL_DECISION"

    positions = fixture.get("portfolio", {}).get("positions", [])
    assert len(positions) >= 5, "mixed portfolio should have at least 5 positions"

    section_ids = {
        section.get("id")
        for section in result.final_report.get("user_facing_sections", [])
        if isinstance(section, dict)
    }
    for required in ("direct_answer", "portfolio_diagnosis", "evidence_status",
                     "action_boundary", "recommended_next_steps"):
        assert required in section_ids

    flat = flatten_report_text(result.final_report)
    for kw in ("组合", "风险", "现金", "不执行券商下单"):
        assert kw in flat, f"mixed portfolio report missing keyword: {kw}"

    assert "broker_order_id" not in flat
