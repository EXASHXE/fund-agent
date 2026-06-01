"""External host portfolio review flow without ResearchOS."""

from __future__ import annotations

import json
import sys

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.tools.evidence.validators import compile_evidence_graph


def test_external_host_can_run_portfolio_review_to_decision_without_research_os():
    before = set(sys.modules)
    fund_output, decision_output = _run_flow()
    newly_imported = set(sys.modules) - before

    assert fund_output.status == "OK"
    assert "fund_analysis_report" in fund_output.artifacts
    assert "decision" not in fund_output.artifacts
    assert "execution_ledger" not in fund_output.artifacts
    assert decision_output.status == "OK"
    assert "decision" in decision_output.artifacts
    assert "execution_ledger" in decision_output.artifacts
    assert "src.core.research_os" not in newly_imported


def test_external_host_portfolio_review_result_is_json_serializable():
    fund_output, decision_output = _run_flow()

    json.dumps(
        {
            "fund": fund_output.to_dict(),
            "decision": decision_output.to_dict(),
        }
    )


def test_only_decision_support_outputs_decision_and_execution_ledger():
    fund_output, decision_output = _run_flow()

    assert "decision" not in fund_output.artifacts
    assert "execution_ledger" not in fund_output.artifacts
    assert decision_output.artifacts["decision"]["version"] == "decision-contract.v2"
    assert decision_output.artifacts["execution_ledger"]["version"] == "execution-ledger.v1"


def _run_flow():
    payload = _portfolio_payload()
    fund_output = FundAnalysisSkill().run(
        SkillInput(
            task_id="portfolio-review",
            step_id="fund-analysis",
            skill_name="fund_analysis",
            payload=payload,
        )
    )
    compile_result = compile_evidence_graph(fund_output.evidence_items)
    decision_output = DecisionSupportSkill().run(
        SkillInput(
            task_id="portfolio-review",
            step_id="decision",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": "personal portfolio review",
                "portfolio_context": payload["portfolio"],
                "risk_profile": payload["risk_profile"],
                "constraints": {
                    "max_buy_amount": 8000.0,
                    "min_trade_amount": 100.0,
                },
                "target_trade_amount": 12000.0,
                "time_horizon": "6 months",
            },
        )
    )
    return fund_output, decision_output


def _portfolio_payload() -> dict:
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
                    "target_weight": 0.12,
                    "tags": ["healthcare"],
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Balanced Core",
                    "current_value": 50000.0,
                    "total_cost": 49000.0,
                    "target_weight": 0.24,
                    "tags": ["core"],
                },
                {
                    "fund_code": "161725",
                    "fund_name": "Technology Growth",
                    "current_value": 40000.0,
                    "total_cost": 42000.0,
                    "target_weight": 0.18,
                    "tags": ["technology"],
                },
            ],
        },
        "fund_profiles": {
            "110011": {"fund_code": "110011", "name": "Healthcare Alpha", "fund_type": "active"},
            "000001": {"fund_code": "000001", "name": "Balanced Core", "fund_type": "balanced"},
            "161725": {"fund_code": "161725", "name": "Technology Growth", "fund_type": "equity"},
        },
        "nav_history": {
            "110011": _nav(1.0, 1.08, 1.18),
            "000001": _nav(1.0, 1.03, 1.07),
            "161725": _nav(1.0, 0.98, 1.09),
        },
        "holdings": {
            "110011": [{"name": "A", "weight": 1.0, "industry": "healthcare"}],
            "000001": [{"name": "B", "weight": 1.0, "industry": "balanced"}],
            "161725": [{"name": "C", "weight": 1.0, "industry": "technology"}],
        },
        "risk_profile": {
            "risk_level": "moderate",
            "max_single_fund_weight": 0.35,
            "max_theme_weight": 0.45,
            "max_trade_pct": 0.1,
            "liquidity_reserve_pct": 0.1,
            "short_term_trade_budget_pct": 0.1,
        },
        "constraints": {"min_trade_amount": 100.0},
    }


def _nav(first: float, middle: float, last: float) -> list[dict]:
    return [
        {"date": "2025-06-01", "nav": first},
        {"date": "2025-12-01", "nav": middle},
        {"date": "2026-06-01", "nav": last},
    ]
