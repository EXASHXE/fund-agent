"""Production personal portfolio regression runner.

Deterministic workflow runner for personal portfolio regression fixtures.
No network, provider SDKs, broker execution, or LLM.

This module is the canonical implementation; the compatibility wrapper
under ``tests/`` and ``src.fund_agent.regression`` are thin re-exports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.workflow.advisory_intent import classify_advisory_intent
from src.skills_runtime.workflow.evidence_bridge import (
    WorkflowEvidenceGraphResult,
    build_evidence_graph_from_workflow,
    resolve_evidence_source_refs,
)
from src.skills_runtime.workflow.workflow_trace import WorkflowTrace
from src.tools.workflow.advisory_quality_gate import evaluate_advisory_quality_gate
from src.tools.workflow.final_report import compose_advisory_workflow_report
from src.tools.workflow.report_safety import FORBIDDEN_EXECUTION_FIELDS


FIXTURES_DIR = (
    Path(__file__).resolve().parents[3]
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


@dataclass
class PersonalRegressionResult:
    scenario_id: str
    fixture_path: str
    advisory_intents: list[str]
    fund_analysis_output: dict
    evidence_graph: dict
    decision_support_output: dict | None
    final_report: dict
    workflow_trace: dict | None = None
    quality_gate: dict | None = None
    checks: list[dict] = field(default_factory=list)
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_personal_regression_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def list_personal_regression_fixtures(root: Path | None = None) -> list[Path]:
    return sorted((root or FIXTURES_DIR).glob("*.json"))


def run_personal_regression_fixture(
    fixture: dict[str, Any],
    fixture_path: Path | None = None,
) -> PersonalRegressionResult:
    scenario_id = fixture["scenario_id"]
    eb = fixture["expected_behavior"]

    trace = WorkflowTrace(scenario_id=scenario_id)
    trace.add_event("input_loaded", f"Loaded personal regression fixture: {scenario_id}")

    intents = _classify_intents(fixture)
    trace.add_event("intent_classified", f"Intents: {', '.join(intents)}", {"intents": intents})

    trace.add_event("fund_analysis_started", "Starting fund_analysis")
    fa_output = _run_fund_analysis(fixture)
    trace.add_event("fund_analysis_completed", "fund_analysis completed", {"status": fa_output.status})

    trace.add_event("evidence_graph_started", "Building evidence graph")
    evidence_result = _build_evidence(fixture, fa_output)
    trace.add_event("evidence_graph_built", "Evidence graph built", {"item_count": len(evidence_result.graph.items)})

    ds_output = None
    if eb["decision_support_called"]:
        trace.add_event("decision_support_started", "Starting decision_support")
        ds_output = _run_decision_support(fixture, fa_output, evidence_result)
        trace.add_event("decision_support_completed", "decision_support completed", {"status": ds_output.status})
    else:
        trace.add_event("decision_support_skipped", "decision_support skipped (report-only)")

    trace.add_event("final_report_started", "Composing final report")
    report = _compose_report(
        fixture, fa_output, ds_output, evidence_result, intents,
    )
    trace.add_event("final_report_composed", "Final report composed", {
        "report_status": report.get("workflow_summary", {}).get("report_status"),
        "decision_status": report.get("workflow_summary", {}).get("decision_status"),
    })

    trace.add_event("quality_gate_started", "Evaluating quality gate")
    quality_gate = evaluate_advisory_quality_gate(
        fund_analysis_output=fa_output.to_dict(),
        evidence_graph=evidence_result.to_dict(),
        decision_support_output=ds_output.to_dict() if ds_output else None,
        final_report=report,
        expected_behavior=eb,
        language=fixture.get("language", "zh-CN"),
    )
    trace.add_event("quality_gate_evaluated", "Quality gate evaluated", {
        "passed": quality_gate["passed"],
        "fail_count": quality_gate["summary"]["fail_count"],
        "warn_count": quality_gate["summary"]["warn_count"],
    })

    trace.add_event("workflow_completed", f"Workflow completed: {scenario_id}")

    return PersonalRegressionResult(
        scenario_id=scenario_id,
        fixture_path=str(fixture_path) if fixture_path else "",
        advisory_intents=intents,
        fund_analysis_output=fa_output.to_dict(),
        evidence_graph=evidence_result.to_dict(),
        decision_support_output=ds_output.to_dict() if ds_output else None,
        final_report=report,
        workflow_trace=trace.to_dict(),
        quality_gate=quality_gate,
    )


def validate_personal_regression_result(
    result: PersonalRegressionResult,
    expected_behavior: dict,
) -> list[dict]:
    failures: list[dict] = []
    eb = expected_behavior

    for expected in eb["expected_advisory_intents"]:
        if expected not in result.advisory_intents:
            failures.append({"check": "advisory_intent", "expected": expected, "got": result.advisory_intents})

    summary = result.final_report.get("workflow_summary", {})
    safety = result.final_report.get("safety_boundary", {})

    for name, actual, expected in (
        ("report_status", summary.get("report_status"), eb["expected_report_status"]),
        ("decision_status", summary.get("decision_status"), eb["expected_decision_status"]),
        ("formal_source", safety.get("formal_decision_source"), eb["expected_formal_source"]),
    ):
        if actual != expected:
            failures.append({"check": name, "expected": expected, "got": actual})

    if safety.get("no_broker_execution") is not True:
        failures.append({"check": "no_broker_execution", "expected": True, "got": False})

    for label, value in (
        ("fixture", _load_fixture_if_path(result.fixture_path)),
        ("fund_analysis", result.fund_analysis_output),
        ("evidence", result.evidence_graph),
        ("decision_support", result.decision_support_output),
        ("report", result.final_report),
    ):
        if value and _contains_forbidden_execution_field(value):
            failures.append({"check": "forbidden_execution_field", "location": label})

    section_ids = {
        section.get("id")
        for section in result.final_report.get("user_facing_sections", [])
        if isinstance(section, dict)
    }
    for section_id in eb["expected_required_report_sections"]:
        if section_id not in section_ids:
            failures.append({"check": "required_section", "expected": section_id})

    phrase_sources = {
        "chinese_summary": " ".join(result.final_report.get("chinese_summary", {}).get("bullets", [])),
        "direct_answer": section_text(result.final_report, "direct_answer"),
        "action_boundary": section_text(result.final_report, "action_boundary"),
        "missing_data": section_text(result.final_report, "evidence_status") + " " + section_text(result.final_report, "limitations"),
    }
    phrase_expectations = {
        "chinese_summary": eb["expected_chinese_summary_contains"],
        "direct_answer": eb["expected_direct_answer_contains"],
        "action_boundary": eb["expected_action_boundary_contains"],
        "missing_data": eb["expected_missing_data_contains"],
    }
    for source_name, phrases in phrase_expectations.items():
        text = phrase_sources[source_name]
        for phrase in phrases:
            if phrase not in text:
                failures.append({"check": "phrase", "source": source_name, "expected": phrase})

    output_text = _serialized(
        result.fund_analysis_output,
        result.evidence_graph,
        result.decision_support_output,
        result.final_report,
    )
    for forbidden in eb["expected_no_fabrication_fields"]:
        if forbidden in output_text:
            failures.append({"check": "no_fabrication", "field": forbidden})

    if eb["decision_support_called"]:
        if result.decision_support_output is None:
            failures.append({"check": "decision_support_called", "expected": True, "got": False})
        else:
            ds_artifacts = result.decision_support_output.get("artifacts", {})
            ledger = ds_artifacts.get("execution_ledger", {})
            ledger_summary = ledger.get("ledger_summary", {}) if isinstance(ledger, dict) else {}
            for key, expected_key in (
                ("active_decision_count", "expected_active_decision_count"),
                ("passive_decision_count", "expected_passive_decision_count"),
                ("blocked_decision_count", "expected_blocked_decision_count"),
                ("downgraded_decision_count", "expected_downgraded_decision_count"),
            ):
                if ledger_summary.get(key) != eb[expected_key]:
                    failures.append({"check": key, "expected": eb[expected_key], "got": ledger_summary.get(key)})

            reason_text = _serialized(
                ds_artifacts.get("decision"),
                ds_artifacts.get("decisions"),
                ledger,
            )
            for fragment in eb["expected_reason_code_contains"]:
                if fragment not in reason_text:
                    failures.append({"check": "reason_code", "expected": fragment})

            conflicts = ds_artifacts.get("risk_constraint_conflicts", {})
            conflict_text = _serialized(conflicts)
            for kind in eb["expected_risk_conflict_kinds"]:
                if kind not in conflict_text:
                    failures.append({"check": "risk_conflict", "expected": kind})

            if eb.get("expected_action_outcome") == "allowed":
                decision = ds_artifacts.get("decision", {})
                action = decision.get("action", "")
                if action not in {"BUY", "SELL", "INCREASE", "REDUCE"}:
                    failures.append({"check": "allowed_action", "expected": "active", "got": action})
                amount = decision.get("execution_amount", 0)
                min_amt = eb.get("expected_min_final_execution_amount", 0)
                max_amt = eb.get("expected_max_final_execution_amount", float("inf"))
                if amount < min_amt or amount > max_amt:
                    failures.append({"check": "execution_amount_bounds", "amount": amount, "min": min_amt, "max": max_amt})
                if eb.get("expected_preserve_requested_action"):
                    requested = fixture_from_result(result).get("requested_action", "")
                    if requested and action != requested:
                        failures.append({"check": "preserve_requested_action", "expected": requested, "got": action})
    else:
        if result.decision_support_output is not None:
            failures.append({"check": "decision_support_not_called", "expected": None, "got": "present"})

    result.checks = failures
    result.ok = not failures
    result.errors = [f"{f['check']}: expected {f.get('expected')}, got {f.get('got')}" for f in failures]
    return failures


def flatten_report_text(
    report: dict[str, Any],
    section_ids: list[str] | None = None,
) -> str:
    parts: list[str] = []

    for section in report.get("user_facing_sections", []):
        if not isinstance(section, dict):
            continue
        sid = section.get("id", "")
        if section_ids and sid not in section_ids:
            continue
        for bullet in section.get("bullets", []):
            parts.append(str(bullet))

    chinese = report.get("chinese_summary", {})
    if isinstance(chinese, dict):
        if not section_ids or "chinese_summary" in section_ids:
            for bullet in chinese.get("bullets", []):
                parts.append(str(bullet))

    workflow = report.get("workflow_summary", {})
    if isinstance(workflow, dict):
        if not section_ids or "workflow_summary" in section_ids:
            for key, val in workflow.items():
                parts.append(f"{key}: {val}")

    safety = report.get("safety_boundary", {})
    if isinstance(safety, dict):
        if not section_ids or "safety_boundary" in section_ids:
            for key, val in safety.items():
                parts.append(f"{key}: {val}")

    return " ".join(parts)


def section_text(report: dict[str, Any], section_id: str) -> str:
    for section in report.get("user_facing_sections", []):
        if isinstance(section, dict) and section.get("id") == section_id:
            return " ".join(str(item) for item in section.get("bullets", []))
    return ""


def _classify_intents(fixture: dict[str, Any]) -> list[str]:
    return classify_advisory_intent(
        host_intent_hint=fixture.get("user_intent_hint") or fixture.get("user_intent"),
        user_question=fixture.get("user_question"),
        requested_action=fixture.get("requested_action"),
    )


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
        "target_trade_amount": fixture.get("target_trade_amount")
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


def _serialized(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)


def _contains_forbidden_execution_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in FORBIDDEN_EXECUTION_FIELDS or _contains_forbidden_execution_field(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_execution_field(item) for item in value)
    return False


def _load_fixture_if_path(path_str: str) -> dict | None:
    if not path_str:
        return None
    try:
        return load_personal_regression_fixture(Path(path_str))
    except Exception:
        return None


def fixture_from_result(result: PersonalRegressionResult) -> dict[str, Any]:
    if result.fixture_path:
        return load_personal_regression_fixture(Path(result.fixture_path))
    return {}
