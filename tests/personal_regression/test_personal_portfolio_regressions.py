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
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.workflow.advisory_intent import classify_advisory_intent
from src.skills_runtime.workflow.evidence_bridge import (
    WorkflowEvidenceGraphResult,
    build_evidence_graph_from_workflow,
    resolve_evidence_source_refs,
)
from src.tools.workflow.final_report import compose_advisory_workflow_report
from tests.end_to_end.helpers import (
    assert_no_execution_fields,
    assert_no_formal_decision_in_output,
)


FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "personal_portfolio_regressions"
)

REQUIRED_EXPECTED_KEYS = {
    "expected_advisory_intents",
    "decision_support_called",
    "expected_report_status",
    "expected_decision_status",
    "expected_formal_source",
    "expected_active_decision_count",
    "expected_passive_decision_count",
    "expected_blocked_decision_count",
    "expected_downgraded_decision_count",
    "expected_reason_code_contains",
    "expected_risk_conflict_kinds",
    "expected_required_report_sections",
    "expected_chinese_summary_contains",
    "expected_direct_answer_contains",
    "expected_action_boundary_contains",
    "expected_missing_data_contains",
    "expected_no_fabrication_fields",
    "expected_no_broker_execution",
}

REQUIRED_FIXTURE_FIELDS = {
    "scenario_id",
    "user_question",
    "user_context",
    "portfolio",
    "nav_history",
    "fund_profiles",
    "risk_profile",
    "constraints",
    "expected_behavior",
}


def _fixture_paths() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.json"))


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _scenario_ids() -> list[str]:
    return [path.stem for path in _fixture_paths()]


def _run_fund_analysis(fixture: dict[str, Any]) -> SkillOutput:
    return FundAnalysisSkill().run(
        SkillInput(
            task_id=fixture["scenario_id"],
            step_id="personal-fa",
            skill_name="fund_analysis",
            payload=fixture,
        )
    )


def _build_evidence(
    fixture: dict[str, Any],
    fund_analysis_output: SkillOutput,
) -> WorkflowEvidenceGraphResult:
    return build_evidence_graph_from_workflow(
        fund_analysis_output=fund_analysis_output.to_dict(),
        host_news_evidence=fixture.get("news_evidence", []),
        host_sentiment_evidence=fixture.get("sentiment_evidence", []),
        host_benchmark_evidence=fixture.get("benchmark_history", {}),
        host_fee_evidence=fixture.get("fee_schedules", {}),
        host_redemption_evidence=fixture.get("redemption_rules", {}),
        include_diagnostics=True,
    )


def _run_decision_support(
    fixture: dict[str, Any],
    fund_analysis_output: SkillOutput,
    evidence_result: WorkflowEvidenceGraphResult,
) -> SkillOutput:
    fa_artifacts = fund_analysis_output.to_dict().get("artifacts", {})
    payload: dict[str, Any] = {
        "evidence_graph": evidence_result.graph.to_dict(),
        "requested_amount": fixture.get("target_trade_amount")
        or fixture.get("requested_amount", 0),
        "portfolio_context": fixture.get("portfolio", {}),
        "risk_profile": fixture.get("risk_profile", {}),
        "constraints": fixture.get("constraints", {}),
        "time_horizon": fixture.get("time_horizon", "medium_term"),
        "objective": fixture.get("user_question", ""),
        "deterministic": True,
    }
    if fixture.get("requested_action"):
        payload["requested_action"] = fixture["requested_action"]

    trade_plan = fixture.get("requested_trade_plan") or fixture.get("trade_plan")
    if trade_plan:
        resolved_plan, _ = resolve_evidence_source_refs(
            trade_plan,
            evidence_result.graph,
        )
        payload["trade_plan"] = resolved_plan
        payload["selected_trade_ids"] = fixture.get("selected_trade_ids", [])

    for key in (
        "analysis_plan",
        "evidence_gap_diagnostics",
        "profit_protection_diagnostics",
        "benchmark_divergence_diagnostics",
        "right_side_confirmation_diagnostics",
        "event_hype_failure_diagnostics",
        "cash_deployment_diagnostics",
        "redemption_fee_risk",
        "position_contribution",
    ):
        value = fa_artifacts.get(key)
        if value:
            payload[key] = value

    return DecisionSupportSkill().run(
        SkillInput(
            task_id=fixture["scenario_id"],
            step_id="personal-ds",
            skill_name="decision_support",
            payload=payload,
        )
    )


def _classify_intents(fixture: dict[str, Any]) -> list[str]:
    return classify_advisory_intent(
        host_intent_hint=fixture.get("user_intent_hint")
        or fixture.get("user_intent"),
        user_question=fixture.get("user_question"),
        requested_action=fixture.get("requested_action"),
    )


def _compose_report(
    fixture: dict[str, Any],
    fund_analysis_output: SkillOutput,
    decision_support_output: SkillOutput | None,
    evidence_result: WorkflowEvidenceGraphResult,
    advisory_intents: list[str],
) -> dict[str, Any]:
    fa_dict = fund_analysis_output.to_dict()
    fa_artifacts = fa_dict.get("artifacts", {})
    missing_data = {}
    if isinstance(fa_artifacts, dict):
        missing_data = fa_artifacts.get("evidence_gap_diagnostics", {})
    return compose_advisory_workflow_report(
        scenario_id=fixture["scenario_id"],
        fund_analysis_output=fa_dict,
        decision_support_output=(
            decision_support_output.to_dict() if decision_support_output else None
        ),
        evidence_graph_diagnostics=evidence_result.to_dict(),
        missing_data_diagnostics=missing_data,
        language=fixture.get("language", "zh-CN"),
        advisory_intents=advisory_intents,
    )


def _run_workflow(scenario_id: str):
    fixture = _load_fixture(FIXTURES_DIR / f"{scenario_id}.json")
    intents = _classify_intents(fixture)
    fund_analysis_output = _run_fund_analysis(fixture)
    evidence_result = _build_evidence(fixture, fund_analysis_output)
    eb = fixture["expected_behavior"]
    decision_support_output = (
        _run_decision_support(fixture, fund_analysis_output, evidence_result)
        if eb["decision_support_called"]
        else None
    )
    report = _compose_report(
        fixture,
        fund_analysis_output,
        decision_support_output,
        evidence_result,
        intents,
    )
    return fixture, intents, fund_analysis_output, evidence_result, decision_support_output, report


def _section_text(report: dict[str, Any], section_id: str) -> str:
    for section in report.get("user_facing_sections", []):
        if isinstance(section, dict) and section.get("id") == section_id:
            return " ".join(str(item) for item in section.get("bullets", []))
    return ""


def _serialized_output_text(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda p: p.stem)
def test_fixture_shape_and_expected_behavior_contract(path: Path):
    fixture = _load_fixture(path)
    missing_fields = REQUIRED_FIXTURE_FIELDS - set(fixture)
    assert not missing_fields, f"{path.name} missing fields: {sorted(missing_fields)}"
    assert fixture["scenario_id"] == path.stem

    eb = fixture.get("expected_behavior", {})
    missing_expected = REQUIRED_EXPECTED_KEYS - set(eb)
    assert not missing_expected, (
        f"{path.name} missing expected_behavior keys: {sorted(missing_expected)}"
    )
    assert eb["expected_no_broker_execution"] is True


def test_personal_regression_pack_has_at_least_twelve_scenarios():
    assert len(_fixture_paths()) >= 12


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_personal_portfolio_regression_matches_expected_behavior(scenario_id: str):
    fixture, intents, fa_output, evidence_result, ds_output, report = _run_workflow(scenario_id)
    eb = fixture["expected_behavior"]

    assert_no_formal_decision_in_output(fa_output)
    assert_no_execution_fields(fixture, f"fixture:{scenario_id}")
    assert_no_execution_fields(fa_output.to_dict(), f"fund_analysis:{scenario_id}")
    assert_no_execution_fields(evidence_result.to_dict(), f"evidence:{scenario_id}")
    assert_no_execution_fields(report, f"report:{scenario_id}")

    for expected_intent in eb["expected_advisory_intents"]:
        assert expected_intent in intents

    summary = report["workflow_summary"]
    safety = report["safety_boundary"]
    assert summary["report_status"] == eb["expected_report_status"]
    assert summary["decision_status"] == eb["expected_decision_status"]
    assert safety["formal_decision_source"] == eb["expected_formal_source"]
    assert safety["no_broker_execution"] is True

    section_ids = {
        section.get("id")
        for section in report.get("user_facing_sections", [])
        if isinstance(section, dict)
    }
    for section_id in eb["expected_required_report_sections"]:
        assert section_id in section_ids

    chinese_summary = " ".join(report.get("chinese_summary", {}).get("bullets", []))
    for phrase in eb["expected_chinese_summary_contains"]:
        assert phrase in chinese_summary

    direct_answer = _section_text(report, "direct_answer")
    for phrase in eb["expected_direct_answer_contains"]:
        assert phrase in direct_answer

    action_boundary = _section_text(report, "action_boundary")
    for phrase in eb["expected_action_boundary_contains"]:
        assert phrase in action_boundary

    missing_text = (
        _section_text(report, "evidence_status")
        + " "
        + _section_text(report, "limitations")
    )
    for phrase in eb["expected_missing_data_contains"]:
        assert phrase in missing_text

    full_text = _serialized_output_text(fa_output.to_dict(), evidence_result.to_dict(), ds_output.to_dict() if ds_output else None, report)
    for forbidden in eb["expected_no_fabrication_fields"]:
        assert forbidden not in full_text

    if eb["decision_support_called"]:
        assert ds_output is not None
        assert_no_execution_fields(ds_output.to_dict(), f"decision_support:{scenario_id}")
        artifacts = ds_output.artifacts or {}
        ledger = artifacts.get("execution_ledger")
        assert isinstance(ledger, dict)
        ledger_summary = ledger.get("ledger_summary", {})
        assert ledger_summary.get("active_decision_count") == eb["expected_active_decision_count"]
        assert ledger_summary.get("passive_decision_count") == eb["expected_passive_decision_count"]
        assert ledger_summary.get("blocked_decision_count") == eb["expected_blocked_decision_count"]
        assert ledger_summary.get("downgraded_decision_count") == eb["expected_downgraded_decision_count"]

        reason_text = _serialized_output_text(
            artifacts.get("decision"),
            artifacts.get("decisions"),
            ledger,
        )
        for fragment in eb["expected_reason_code_contains"]:
            assert fragment in reason_text

        conflicts = artifacts.get("risk_constraint_conflicts", {})
        assert artifacts.get("evidence_anchor_diagnostics")
        conflict_text = _serialized_output_text(conflicts)
        for kind in eb["expected_risk_conflict_kinds"]:
            assert kind in conflict_text
    else:
        assert ds_output is None
        assert summary["decision_status"] == "NO_FORMAL_DECISION"
        assert safety["formal_decision_source"] == "none"
