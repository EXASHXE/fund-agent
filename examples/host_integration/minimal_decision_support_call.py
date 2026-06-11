"""Minimal host integration: call DecisionSupportSkill directly.

This example demonstrates how an external host or agent can call
DecisionSupportSkill with an EvidenceGraph and fund_analysis artifacts
to produce a formal Decision with reason_codes and blocked_by.
No network, no credentials, no provider SDKs, no broker execution.

Usage:
    python examples/host_integration/minimal_decision_support_call.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill


def main() -> int:
    evidence_graph = {
        "items": {
            "ev-1": {
                "evidence_id": "ev-1",
                "evidence_type": "HardEvidence",
                "source_type": "fund_analysis",
                "timestamp": "2026-06-01T00:00:00",
                "related_entities": ["fund:110011"],
                "claim": "Equity fund shows strong positive return",
                "value": {"score": 0.8},
                "confidence_weight": 1.0,
                "direction": "positive",
                "provenance": {"tool": "fund_analysis"},
            },
        },
        "edges": [],
    }

    payload = {
        "evidence_graph": evidence_graph,
        "requested_action": "BUY",
        "objective": "review fund for potential buy",
        "time_horizon": "medium_term",
        "deterministic": True,
        "task_id": "host-decision-demo",
        "step_id": "decision-1",
        "portfolio_context": {"total_value": 150000.0, "cash_available": 15000.0},
        "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1},
        "constraints": {"min_trade_amount": 100.0, "forbidden_actions": []},
        "risk_budget": {"risk_budget": 5000.0},
        "critique_status": "PASS",
        "analysis_plan": {
            "available_inputs": ["holdings", "transactions", "fund_metadata"],
            "missing_inputs": ["recent_news"],
            "blockers": [],
            "warnings": [],
            "decision_support_ready": True,
        },
        "evidence_gap_diagnostics": {
            "missing_recent_news": True,
            "missing_sentiment": True,
        },
    }

    skill_input = SkillInput(
        task_id="host-decision-demo",
        step_id="decision-1",
        skill_name="decision_support",
        payload=payload,
    )

    output = DecisionSupportSkill().run(skill_input)
    decision = output.artifacts.get("decision", {})

    result = {
        "status": output.status,
        "action": decision.get("action"),
        "has_decision_reason_codes": isinstance(decision.get("decision_reason_codes"), list),
        "has_blocked_by": isinstance(decision.get("blocked_by"), list),
        "has_evidence_state": isinstance(decision.get("evidence_state"), str),
        "has_trigger_conditions": isinstance(decision.get("trigger_conditions"), list),
        "has_audit_trail": isinstance(decision.get("audit_trail"), list),
        "has_execution_ledger": "execution_ledger" in output.artifacts,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    assert result["has_decision_reason_codes"], "Missing decision_reason_codes"
    assert result["has_blocked_by"], "Missing blocked_by"
    assert result["has_evidence_state"], "Missing evidence_state"
    assert result["has_trigger_conditions"], "Missing trigger_conditions"
    assert result["has_audit_trail"], "Missing audit_trail"
    assert result["has_execution_ledger"], "Missing execution_ledger"
    return 0


if __name__ == "__main__":
    sys.exit(main())
