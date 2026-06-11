"""Minimal host integration: call FundAnalysisSkill directly.

This example demonstrates how an external host or agent can call
FundAnalysisSkill with structured portfolio data and retrieve
deterministic analysis artifacts. No network, no credentials, no
provider SDKs, no broker execution.

Usage:
    python examples/host_integration/minimal_fund_analysis_runtime_call.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill


def main() -> int:
    payload = {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 150000.0,
            "cash_available": 15000.0,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Example Equity Fund",
                    "current_value": 80000.0,
                    "total_cost": 65000.0,
                    "shares": 50000.0,
                    "target_weight": 0.5,
                    "tags": ["equity", "growth"],
                },
                {
                    "fund_code": "220022",
                    "fund_name": "Example Bond Fund",
                    "current_value": 55000.0,
                    "total_cost": 50000.0,
                    "shares": 45000.0,
                    "target_weight": 0.4,
                    "tags": ["bond", "income"],
                },
            ],
        },
        "fund_profiles": {
            "110011": {
                "fund_code": "110011",
                "name": "Example Equity Fund",
                "fund_type": "equity",
                "benchmark": "CSI300",
            },
            "220022": {
                "fund_code": "220022",
                "name": "Example Bond Fund",
                "fund_type": "bond",
                "benchmark": "CBAI",
            },
        },
        "nav_history": {
            "110011": [
                {"date": "2025-06-01", "nav": 1.3},
                {"date": "2026-06-01", "nav": 1.6},
            ],
            "220022": [
                {"date": "2025-06-01", "nav": 1.10},
                {"date": "2026-06-01", "nav": 1.22},
            ],
        },
        "fee_schedules": {
            "110011": {"management_fee": 0.015},
            "220022": {"management_fee": 0.005},
        },
        "redemption_rules": {
            "110011": {"holding_period_days": 7, "redemption_fee_pct": 0.015},
            "220022": {"holding_period_days": 0, "redemption_fee_pct": 0.0},
        },
        "risk_profile": {"risk_level": "moderate", "max_single_fund_weight": 0.5},
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
    }

    skill_input = SkillInput(
        task_id="host-fund-analysis",
        step_id="fund-analysis-1",
        skill_name="fund_analysis",
        payload=payload,
    )

    output = FundAnalysisSkill().run(skill_input)
    artifacts = output.artifacts

    result = {
        "status": output.status,
        "has_analysis_plan": "analysis_plan" in artifacts,
        "has_evidence_gap_diagnostics": "evidence_gap_diagnostics" in artifacts,
        "has_position_contribution": "position_contribution" in artifacts,
        "has_report_sections": "report_sections" in artifacts,
        "has_portfolio_summary": "portfolio_summary" in artifacts,
        "has_formal_decision": any(
            k in artifacts for k in ("decision", "decisions", "execution_ledger")
        ),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    assert result["has_analysis_plan"], "Missing analysis_plan artifact"
    assert result["has_evidence_gap_diagnostics"], "Missing evidence_gap_diagnostics"
    assert result["has_position_contribution"], "Missing position_contribution"
    assert result["has_report_sections"], "Missing report_sections"
    assert result["has_portfolio_summary"], "Missing portfolio_summary"
    assert not result["has_formal_decision"], "fund_analysis must not emit formal decisions"
    return 0


if __name__ == "__main__":
    sys.exit(main())
