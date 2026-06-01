"""Minimal host demo: trade plan -> decisions.

Loads a portfolio JSON payload (default: examples/portfolio_review_200k.json),
runs FundAnalysisSkill, compiles evidence, extracts the suggested rebalance
plan, and passes the first 2 trade legs to DecisionSupportSkill to produce
formal Decision and ExecutionLedger artifacts.

No network calls, no provider SDKs, no ResearchOS.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.evidence.validators import compile_evidence_graph


def load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run trade plan to decisions from a JSON payload."
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to portfolio JSON payload. Defaults to examples/portfolio_review_200k.json.",
    )
    args = parser.parse_args()

    json_path = (
        args.file
        or os.environ.get("TRADE_PLAN_JSON")
        or str(PROJECT_ROOT / "examples" / "portfolio_review_200k.json")
    )

    payload = load_payload(json_path)

    fund_output = FundAnalysisSkill().run(
        SkillInput(
            task_id="trade-plan-demo",
            step_id="fund-analysis-1",
            skill_name="fund_analysis",
            payload=payload,
        )
    )

    artifacts = fund_output.artifacts

    compile_result = compile_evidence_graph(fund_output.evidence_items)

    rebalance_plan = artifacts.get("suggested_rebalance_plan")
    trade_plan = rebalance_plan if rebalance_plan and rebalance_plan.get("suggested_trade_plan") else {}
    selected_trade_ids: list[str] = []
    if trade_plan:
        raw_trades = trade_plan.get("suggested_trade_plan", [])
        for i, trade in enumerate(raw_trades):
            if not trade.get("trade_id"):
                trade["trade_id"] = f"trade-{i}"
        selected_trade_ids = [
            t.get("trade_id", f"trade-{i}")
            for i, t in enumerate(raw_trades[:min(2, len(raw_trades))])
        ]

    portfolio = payload.get("portfolio", {})
    risk_profile = payload.get("risk_profile", {})
    constraints = payload.get("constraints", {})

    decision_output = DecisionSupportSkill().run(
        SkillInput(
            task_id="trade-plan-demo",
            step_id="decision-1",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": "review portfolio",
                "portfolio_context": portfolio,
                "risk_profile": risk_profile,
                "constraints": constraints,
                "time_horizon": "medium_term",
                "trade_plan": trade_plan,
                "selected_trade_ids": selected_trade_ids,
            },
        )
    )

    decisions = decision_output.artifacts.get("decisions", [])
    if not isinstance(decisions, list):
        decisions = []
    execution_ledger = decision_output.artifacts.get("execution_ledger")

    result = {
        "fund_analysis_status": fund_output.status,
        "portfolio_summary": artifacts.get("portfolio_summary"),
        "exposure_summary": artifacts.get("exposure_summary"),
        "risk_flags": artifacts.get("risk_flags"),
        "short_term_trade_budget": artifacts.get("short_term_trade_budget"),
        "suggested_rebalance_plan": rebalance_plan,
        "evidence_compile_report": compile_result.report.to_dict(),
        "decisions": decisions,
        "execution_ledger": execution_ledger,
        "warnings": artifacts.get("warnings", []),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
