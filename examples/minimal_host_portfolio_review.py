"""Minimal host demo: portfolio review -> evidence -> decision.

The external host owns the data in this example. Everything is in-memory:
no network calls, no provider SDKs, and no internal orchestration runtime.
"""

from __future__ import annotations

import json
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


def main() -> None:
    payload = _mock_portfolio_payload()

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
        objective="personal portfolio review",
    )

    decision_output = DecisionSupportSkill().run(
        SkillInput(
            task_id="portfolio-review-demo",
            step_id="decision-1",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": "personal portfolio review",
                "portfolio_context": payload["portfolio"],
                "risk_profile": payload["risk_profile"],
                "constraints": {
                    "max_buy_amount": 10000.0,
                    "max_sell_amount": 8000.0,
                    "min_trade_amount": 100.0,
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


def _mock_portfolio_payload() -> dict:
    return {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 200000.0,
            "cash_available": 25000.0,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Healthcare Alpha",
                    "current_value": 30000.0,
                    "total_cost": 29000.0,
                    "shares": 12000.0,
                    "target_weight": 0.12,
                    "tags": ["healthcare", "active"],
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Balanced Core",
                    "current_value": 50000.0,
                    "total_cost": 49000.0,
                    "shares": 20000.0,
                    "target_weight": 0.24,
                    "tags": ["core", "balanced"],
                },
                {
                    "fund_code": "161725",
                    "fund_name": "Technology Growth",
                    "current_value": 40000.0,
                    "total_cost": 42000.0,
                    "shares": 18000.0,
                    "target_weight": 0.18,
                    "tags": ["technology", "growth"],
                },
                {
                    "fund_code": "008888",
                    "fund_name": "Dividend Income",
                    "current_value": 30000.0,
                    "total_cost": 30000.0,
                    "shares": 10000.0,
                    "target_weight": 0.16,
                    "tags": ["income", "dividend"],
                },
            ],
        },
        "fund_profiles": {
            "110011": {
                "fund_code": "110011",
                "name": "Healthcare Alpha",
                "fund_type": "active_equity",
                "manager": "Manager A",
                "benchmark": "Healthcare Index",
            },
            "000001": {
                "fund_code": "000001",
                "name": "Balanced Core",
                "fund_type": "balanced",
                "manager": "Manager B",
                "benchmark": "Balanced Index",
            },
            "161725": {
                "fund_code": "161725",
                "name": "Technology Growth",
                "fund_type": "equity",
                "manager": "Manager C",
                "benchmark": "Technology Index",
            },
            "008888": {
                "fund_code": "008888",
                "name": "Dividend Income",
                "fund_type": "income",
                "manager": "Manager D",
                "benchmark": "Dividend Index",
            },
        },
        "nav_history": {
            "110011": _nav(1.0, 1.08, 1.18),
            "000001": _nav(1.0, 1.03, 1.07),
            "161725": _nav(1.0, 0.98, 1.09),
            "008888": _nav(1.0, 1.02, 1.05),
        },
        "holdings": {
            "110011": [
                {"name": "Healthcare A", "weight": 0.6, "industry": "healthcare", "region": "CN"},
                {"name": "Healthcare B", "weight": 0.4, "industry": "healthcare", "region": "US"},
            ],
            "000001": [
                {"name": "Bond Sleeve", "weight": 0.5, "asset_type": "bond", "region": "CN"},
                {"name": "Equity Sleeve", "weight": 0.5, "asset_type": "equity", "region": "CN"},
            ],
            "161725": [
                {"name": "Tech A", "weight": 0.7, "industry": "technology", "region": "US"},
                {"name": "Tech B", "weight": 0.3, "industry": "technology", "region": "CN"},
            ],
            "008888": [
                {"name": "Dividend A", "weight": 1.0, "industry": "dividend", "region": "CN"}
            ],
        },
        "risk_profile": {
            "risk_level": "moderate",
            "max_single_fund_weight": 0.35,
            "max_theme_weight": 0.45,
            "max_trade_pct": 0.1,
            "liquidity_reserve_pct": 0.1,
            "short_term_trade_budget_pct": 0.1,
        },
        "constraints": {
            "min_trade_amount": 100.0,
            "forbidden_actions": [],
        },
    }


def _nav(first: float, middle: float, last: float) -> list[dict]:
    return [
        {"date": "2025-06-01", "nav": first},
        {"date": "2025-12-01", "nav": middle},
        {"date": "2026-06-01", "nav": last},
    ]


if __name__ == "__main__":
    main()
