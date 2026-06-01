"""Minimal host demo: portfolio review -> evidence -> decision.

The external host owns the data in this example. Everything is in-memory:
no network calls, no provider SDKs, and no internal orchestration runtime.

Loads portfolio data from examples/portfolio_review_200k.json by default.
Override with PORTFOLIO_JSON env var or --file argument.
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
from src.tools.evidence.review import review_evidence_graph
from src.tools.evidence.validators import compile_evidence_graph


def load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run portfolio review from a JSON payload."
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
        or os.environ.get("PORTFOLIO_JSON")
        or str(PROJECT_ROOT / "examples" / "portfolio_review_200k.json")
    )

    payload = load_payload(json_path)
    objective = payload.pop("objective", "personal portfolio review")

    fund_output = FundAnalysisSkill().run(
        SkillInput(
            task_id="portfolio-review-demo",
            step_id="fund-analysis-1",
            skill_name="fund_analysis",
            payload=payload,
        )
    )

    compile_result = compile_evidence_graph(fund_output.evidence_items)
    review_result = review_evidence_graph(
        compile_result.graph,
        objective=objective,
    )

    decision_output = DecisionSupportSkill().run(
        SkillInput(
            task_id="portfolio-review-demo",
            step_id="decision-1",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": objective,
                "portfolio_context": payload["portfolio"],
                "risk_profile": payload["risk_profile"],
                "constraints": {
                    "max_buy_amount": 10000.0,
                    "max_sell_amount": 8000.0,
                    "min_trade_amount": payload.get("constraints", {}).get(
                        "min_trade_amount", 100.0
                    ),
                },
                "target_trade_amount": 9000.0,
                "time_horizon": "6 months",
                "critique_status": "PASS"
                if review_result.status == "PASS"
                else "RETRY",
                "critique_issues": review_result.issues,
            },
        )
    )

    result = {
        "fund_analysis_report": fund_output.artifacts.get("fund_analysis_report"),
        "evidence_compile_report": compile_result.report.to_dict(),
        "evidence_review": review_result.to_dict(),
        "decision": decision_output.artifacts.get("decision"),
        "execution_ledger": decision_output.artifacts.get("execution_ledger"),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
