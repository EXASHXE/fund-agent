"""Minimal personal fund report with optional decision-support handoff.

Extends the report-only flow (minimal_personal_fund_report_flow.py) with
an optional formal-decision step. The separation is explicit:
- Report output is always produced (analysis only, no executable trading).
- Formal Decision / ExecutionLedger is only produced when --with-decision
  is passed AND the user asks for formal action.

Usage:
    python examples/minimal_personal_fund_report_with_decision_handoff.py
    python examples/minimal_personal_fund_report_with_decision_handoff.py --with-decision

Safety:
- No network calls, no provider SDKs, no OpenCode plugin.
- suggested_rebalance_plan is an analysis artifact, not an executable order.
- Active decisions require evidence anchors.
- DecisionSupportSkill is the only Decision/ExecutionLedger producer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.evidence.validators import compile_evidence_graph

DEFAULT_INPUT = PROJECT_ROOT / "examples" / "runtime_bridge_personal_report_quality_input.json"


def load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Personal fund report with optional decision handoff"
    )
    parser.add_argument(
        "--input", type=str, default=str(DEFAULT_INPUT),
        help="Path to JSON input payload",
    )
    parser.add_argument(
        "--with-decision", action="store_true", default=False,
        help="Also produce formal Decision and ExecutionLedger via DecisionSupportSkill",
    )
    args = parser.parse_args()

    data = load_payload(args.input)
    payload = data.get("payload", data)

    # ---- Step 1: fund_analysis (analysis only) ----
    fa_input = SkillInput(
        task_id="report-with-decision",
        step_id="fund-analysis-1",
        skill_name="fund_analysis",
        payload=payload,
    )
    fa_output = FundAnalysisSkill().run(fa_input)

    report_artifacts = fa_output.artifacts
    result: dict = {
        "status": fa_output.status,
        "data_completeness": report_artifacts.get("data_completeness", {}),
        "analysis_coverage": report_artifacts.get("analysis_coverage", {}),
        "report_quality_gate": report_artifacts.get("report_quality_gate", {}),
        "report_limitations": report_artifacts.get("report_limitations", []),
        "warnings": fa_output.warnings,
        "note": (
            "Report analysis complete. suggested_rebalance_plan is an "
            "analysis artifact, not an executable trading instruction."
        ),
    }

    # ---- Step 2: decision_support (only when requested) ----
    if args.with_decision:
        evidence_items = fa_output.evidence_items
        compile_evidence_graph(evidence_items)

        ds_input = SkillInput(
            task_id="report-with-decision",
            step_id="decision-1",
            skill_name="decision_support",
            payload={
                "evidence_items": evidence_items,
                "portfolio_context": payload.get("portfolio", {}),
                "risk_profile": payload.get("risk_profile", {}),
                "constraints": payload.get("constraints", {}),
            },
            evidence_context=[item.evidence_id for item in evidence_items],
        )
        if isinstance(payload.get("risk_profile"), dict):
            ds_input.payload["risk_profile"] = payload["risk_profile"]
        if isinstance(payload.get("constraints"), dict):
            ds_input.payload["constraints"] = payload["constraints"]

        ds_output = DecisionSupportSkill().run(ds_input)
        result["decisions"] = ds_output.artifacts.get("decisions", [])
        result["execution_ledger"] = ds_output.artifacts.get("execution_ledger", {})
        result["decision_status"] = ds_output.status
        result["note"] = (
            "Report analysis AND formal decision produced. "
            "Active decisions (BUY/SELL/INCREASE/REDUCE) require evidence anchors."
        )

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
