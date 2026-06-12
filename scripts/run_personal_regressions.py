#!/usr/bin/env python3
"""Run deterministic personal portfolio regression fixtures.

No network, provider SDKs, broker execution, or LLM calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


FIXTURES_DIR = ROOT / "examples" / "personal_portfolio_regressions"
FORBIDDEN_EXECUTION_FIELDS = {
    "broker_order_id",
    "order_id",
    "order_status",
    "filled_quantity",
    "fill_price",
    "execution_venue",
    "submitted_at",
    "broker",
    "exchange_order_id",
}


def load_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fixture_paths(scenario: str | None = None) -> list[Path]:
    if scenario:
        path = FIXTURES_DIR / f"{scenario}.json"
        if not path.exists():
            raise SystemExit(f"Scenario not found: {scenario}")
        return [path]
    return sorted(FIXTURES_DIR.glob("*.json"))


def classify_intents(fixture: dict[str, Any]) -> list[str]:
    return classify_advisory_intent(
        host_intent_hint=fixture.get("user_intent_hint") or fixture.get("user_intent"),
        user_question=fixture.get("user_question"),
        requested_action=fixture.get("requested_action"),
    )


def run_fund_analysis(fixture: dict[str, Any]) -> SkillOutput:
    return FundAnalysisSkill().run(
        SkillInput(
            task_id=fixture["scenario_id"],
            step_id="personal-fa",
            skill_name="fund_analysis",
            payload=fixture,
        )
    )


def build_evidence(
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


def run_decision_support(
    fixture: dict[str, Any],
    fund_analysis_output: SkillOutput,
    evidence_result: WorkflowEvidenceGraphResult,
) -> SkillOutput:
    fa_artifacts = fund_analysis_output.to_dict().get("artifacts", {})
    payload: dict[str, Any] = {
        "evidence_graph": evidence_result.graph.to_dict(),
        "requested_amount": fixture.get("target_trade_amount") or fixture.get("requested_amount", 0),
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
        resolved_plan, _ = resolve_evidence_source_refs(trade_plan, evidence_result.graph)
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


def compose_report(
    fixture: dict[str, Any],
    fund_analysis_output: SkillOutput,
    decision_support_output: SkillOutput | None,
    evidence_result: WorkflowEvidenceGraphResult,
    intents: list[str],
) -> dict[str, Any]:
    fa_dict = fund_analysis_output.to_dict()
    fa_artifacts = fa_dict.get("artifacts", {})
    missing_data = fa_artifacts.get("evidence_gap_diagnostics", {}) if isinstance(fa_artifacts, dict) else {}
    return compose_advisory_workflow_report(
        scenario_id=fixture["scenario_id"],
        fund_analysis_output=fa_dict,
        decision_support_output=decision_support_output.to_dict() if decision_support_output else None,
        evidence_graph_diagnostics=evidence_result.to_dict(),
        missing_data_diagnostics=missing_data,
        language=fixture.get("language", "zh-CN"),
        advisory_intents=intents,
    )


def section_text(report: dict[str, Any], section_id: str) -> str:
    for section in report.get("user_facing_sections", []):
        if isinstance(section, dict) and section.get("id") == section_id:
            return " ".join(str(item) for item in section.get("bullets", []))
    return ""


def contains_forbidden_execution_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in FORBIDDEN_EXECUTION_FIELDS or contains_forbidden_execution_field(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(contains_forbidden_execution_field(item) for item in value)
    return False


def serialized(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)


def assert_expected(
    fixture: dict[str, Any],
    intents: list[str],
    fa_output: SkillOutput,
    evidence_result: WorkflowEvidenceGraphResult,
    ds_output: SkillOutput | None,
    report: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    eb = fixture["expected_behavior"]

    for expected in eb["expected_advisory_intents"]:
        if expected not in intents:
            failures.append(f"missing intent {expected}")

    summary = report.get("workflow_summary", {})
    safety = report.get("safety_boundary", {})
    checks = {
        "report_status": (summary.get("report_status"), eb["expected_report_status"]),
        "decision_status": (summary.get("decision_status"), eb["expected_decision_status"]),
        "formal_source": (safety.get("formal_decision_source"), eb["expected_formal_source"]),
    }
    for name, (actual, expected) in checks.items():
        if actual != expected:
            failures.append(f"{name}: expected {expected}, got {actual}")

    if safety.get("no_broker_execution") is not True:
        failures.append("safety_boundary.no_broker_execution is not true")
    for label, value in (
        ("fixture", fixture),
        ("fund_analysis", fa_output.to_dict()),
        ("evidence", evidence_result.to_dict()),
        ("decision_support", ds_output.to_dict() if ds_output else None),
        ("report", report),
    ):
        if contains_forbidden_execution_field(value):
            failures.append(f"forbidden execution field in {label}")

    section_ids = {
        section.get("id")
        for section in report.get("user_facing_sections", [])
        if isinstance(section, dict)
    }
    for section_id in eb["expected_required_report_sections"]:
        if section_id not in section_ids:
            failures.append(f"missing report section {section_id}")

    phrase_sources = {
        "chinese_summary": " ".join(report.get("chinese_summary", {}).get("bullets", [])),
        "direct_answer": section_text(report, "direct_answer"),
        "action_boundary": section_text(report, "action_boundary"),
        "missing_data": section_text(report, "evidence_status") + " " + section_text(report, "limitations"),
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
                failures.append(f"{source_name} missing phrase {phrase}")

    output_text = serialized(
        fa_output.to_dict(),
        evidence_result.to_dict(),
        ds_output.to_dict() if ds_output else None,
        report,
    )
    for field in eb["expected_no_fabrication_fields"]:
        if field in output_text:
            failures.append(f"fabrication field present: {field}")

    if eb["decision_support_called"]:
        if ds_output is None:
            failures.append("decision_support was not called")
        else:
            artifacts = ds_output.artifacts or {}
            ledger = artifacts.get("execution_ledger", {})
            ledger_summary = ledger.get("ledger_summary", {}) if isinstance(ledger, dict) else {}
            for key, expected_key in (
                ("active_decision_count", "expected_active_decision_count"),
                ("passive_decision_count", "expected_passive_decision_count"),
                ("blocked_decision_count", "expected_blocked_decision_count"),
                ("downgraded_decision_count", "expected_downgraded_decision_count"),
            ):
                if ledger_summary.get(key) != eb[expected_key]:
                    failures.append(f"{key}: expected {eb[expected_key]}, got {ledger_summary.get(key)}")
            reason_text = serialized(artifacts.get("decision"), artifacts.get("decisions"), ledger)
            for fragment in eb["expected_reason_code_contains"]:
                if fragment not in reason_text:
                    failures.append(f"reason code fragment missing: {fragment}")
            conflict_text = serialized(artifacts.get("risk_constraint_conflicts", {}))
            for kind in eb["expected_risk_conflict_kinds"]:
                if kind not in conflict_text:
                    failures.append(f"risk conflict missing: {kind}")
    elif ds_output is not None:
        failures.append("decision_support was called for report-only scenario")

    return failures


def run_scenario(path: Path) -> dict[str, Any]:
    fixture = load_fixture(path)
    intents = classify_intents(fixture)
    fa_output = run_fund_analysis(fixture)
    evidence_result = build_evidence(fixture, fa_output)
    eb = fixture["expected_behavior"]
    ds_output = run_decision_support(fixture, fa_output, evidence_result) if eb["decision_support_called"] else None
    report = compose_report(fixture, fa_output, ds_output, evidence_result, intents)
    failures = assert_expected(fixture, intents, fa_output, evidence_result, ds_output, report)
    ds_artifacts = ds_output.artifacts if ds_output else {}
    ledger_summary = (
        ds_artifacts.get("execution_ledger", {}).get("ledger_summary", {})
        if isinstance(ds_artifacts, dict)
        else {}
    )
    reason_codes = ledger_summary.get("reason_code_counts", {})
    direct_bullets = section_text(report, "direct_answer").split("。")
    return {
        "scenario_id": fixture["scenario_id"],
        "passed": not failures,
        "failures": failures,
        "advisory_intents": intents,
        "report_status": report["workflow_summary"]["report_status"],
        "decision_status": report["workflow_summary"]["decision_status"],
        "formal_source": report["safety_boundary"]["formal_decision_source"],
        "direct_answer": [item.strip() for item in direct_bullets if item.strip()][:4],
        "blockers_reason_codes": reason_codes,
        "no_broker_execution": report["safety_boundary"]["no_broker_execution"],
    }


def print_pretty(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print(
        f"Personal regressions: {summary['passed_count']}/{summary['scenario_count']} passed; "
        f"failed={summary['failed_count']}; no_broker_execution={summary['no_broker_execution']}"
    )
    for result in payload["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"\n[{status}] {result['scenario_id']}")
        print(f"  intents: {', '.join(result['advisory_intents'])}")
        print(
            f"  report={result['report_status']} decision={result['decision_status']} "
            f"formal_source={result['formal_source']}"
        )
        print(f"  direct_answer: {' / '.join(result['direct_answer'])}")
        if result["blockers_reason_codes"]:
            print(f"  reason_codes: {result['blockers_reason_codes']}")
        if result["failures"]:
            for failure in result["failures"]:
                print(f"  - {failure}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", help="Run one scenario_id")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    parser.add_argument("--pretty", action="store_true", help="Print readable summary")
    args = parser.parse_args(argv)

    paths = fixture_paths(args.scenario)
    results = [run_scenario(path) for path in paths]
    failed = [result for result in results if not result["passed"]]
    payload = {
        "summary": {
            "scenario_count": len(results),
            "passed_count": len(results) - len(failed),
            "failed_count": len(failed),
            "no_broker_execution": all(result["no_broker_execution"] for result in results),
        },
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_pretty(payload)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
