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

from tests.helpers.personal_regression_runner import (
    FIXTURES_DIR,
    PersonalRegressionResult,
    flatten_report_text,
    list_personal_regression_fixtures,
    load_personal_regression_fixture,
    run_personal_regression_fixture,
    section_text,
    validate_personal_regression_result,
)


def fixture_paths(scenario: str | None = None) -> list[Path]:
    if scenario:
        path = FIXTURES_DIR / f"{scenario}.json"
        if not path.exists():
            raise SystemExit(f"Scenario not found: {scenario}")
        return [path]
    return list_personal_regression_fixtures()


def run_scenario(path: Path) -> dict[str, Any]:
    fixture = load_personal_regression_fixture(path)
    result = run_personal_regression_fixture(fixture, fixture_path=path)
    failures = validate_personal_regression_result(result, fixture["expected_behavior"])

    ds_artifacts = result.decision_support_output.get("artifacts", {}) if result.decision_support_output else {}
    ledger_summary = (
        ds_artifacts.get("execution_ledger", {}).get("ledger_summary", {})
        if isinstance(ds_artifacts, dict)
        else {}
    )
    reason_codes = ledger_summary.get("reason_code_counts", {})
    direct_bullets = section_text(result.final_report, "direct_answer").split("。")
    return {
        "scenario_id": fixture["scenario_id"],
        "passed": not failures,
        "failures": [f"{f['check']}: expected {f.get('expected')}, got {f.get('got')}" for f in failures],
        "advisory_intents": result.advisory_intents,
        "report_status": result.final_report["workflow_summary"]["report_status"],
        "decision_status": result.final_report["workflow_summary"]["decision_status"],
        "formal_source": result.final_report["safety_boundary"]["formal_decision_source"],
        "direct_answer": [item.strip() for item in direct_bullets if item.strip()][:4],
        "blockers_reason_codes": reason_codes,
        "no_broker_execution": result.final_report["safety_boundary"]["no_broker_execution"],
        "quality_gate": result.quality_gate,
        "workflow_trace": result.workflow_trace,
    }


def print_pretty(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print(
        f"Personal regressions: {summary['passed_count']}/{summary['scenario_count']} passed; "
        f"failed={summary['failed_count']}; no_broker_execution={summary['no_broker_execution']}"
    )
    for result in payload["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        qg = result.get("quality_gate", {})
        gate_status = "PASS" if qg.get("passed", True) else "FAIL"
        gate_fails = qg.get("summary", {}).get("fail_count", 0) if qg else 0
        gate_warns = qg.get("summary", {}).get("warn_count", 0) if qg else 0
        print(
            f"\n[{status}] {result['scenario_id']} | "
            f"report={result['report_status']} decision={result['decision_status']} "
            f"gate={gate_status} fails={gate_fails} warns={gate_warns}"
        )
        print(f"  intents: {', '.join(result['advisory_intents'])}")
        print(f"  formal_source={result['formal_source']}")
        print(f"  direct_answer: {' / '.join(result['direct_answer'])}")
        if result["blockers_reason_codes"]:
            print(f"  reason_codes: {result['blockers_reason_codes']}")
        if result["failures"]:
            for failure in result["failures"]:
                print(f"  - {failure}")


def print_trace(payload: dict[str, Any]) -> None:
    for result in payload["results"]:
        trace = result.get("workflow_trace", {})
        if not trace:
            continue
        print(f"\n=== {result['scenario_id']} ===")
        for event in trace.get("events", []):
            seq = event.get("sequence", "?")
            etype = event.get("type", "?")
            msg = event.get("message", "")
            details = event.get("details", {})
            detail_str = f" {details}" if details else ""
            print(f"  [{seq}] {etype}: {msg}{detail_str}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", help="Run one scenario_id")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    parser.add_argument("--pretty", action="store_true", help="Print readable summary")
    parser.add_argument("--show-trace", action="store_true", help="Print compact stage trace")
    parser.add_argument("--emit-trace", metavar="PATH", help="Write JSONL trace to file")
    parser.add_argument("--gate-only", action="store_true", help="Print gate results and exit nonzero on fail")
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

    if args.emit_trace:
        trace_path = Path(args.emit_trace)
        lines: list[str] = []
        for result in results:
            trace = result.get("workflow_trace", {})
            for event in trace.get("events", []):
                lines.append(json.dumps(event, ensure_ascii=False, sort_keys=True))
        trace_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.gate_only:
        gate_failures = []
        for result in results:
            qg = result.get("quality_gate", {})
            if not qg.get("passed", True):
                gate_failures.append(result["scenario_id"])
        if gate_failures:
            print(f"Gate FAILED for: {', '.join(gate_failures)}")
            for result in results:
                qg = result.get("quality_gate", {})
                for check in qg.get("checks", []):
                    if check["status"] == "FAIL":
                        print(f"  {result['scenario_id']}: {check['id']} - {check['message']}")
            return 1
        print(f"All {len(results)} scenarios passed quality gate")
        return 0

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.show_trace:
        print_trace(payload)
    else:
        print_pretty(payload)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
