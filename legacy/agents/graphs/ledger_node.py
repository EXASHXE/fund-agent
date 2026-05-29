"""Ledger Agent Node — Final thesis and execution ledger generation.

Produces FinalThesis (structured research conclusions) and ExecutionLedger
(trade-ready decisions) from complete research state, aligned with
decision-contract.v2 schema.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from legacy.agents.state import FundResearchState

logger = logging.getLogger(__name__)


def ledger_agent_node(state: FundResearchState) -> dict:
    """Generate FinalThesis and ExecutionLedger from complete research state.

    Reads all strategies, critic report, and fund data from state.
    For each fund with a strategy, produces a decision-contract.v2 entry.

    Args:
        state: FundResearchState with strategies, critic_report, and iteration.

    Returns:
        Dict with final_thesis, execution_ledger, and phase='complete'.
    """
    strategies = state.get("strategies", {})
    critic_report = state.get("critic_report", {})
    iteration = state.get("iteration", 1)
    funds_data = state.get("funds_data", {})

    decisions: list[dict[str, Any]] = []
    for code, strategy in strategies.items():
        # Handle both object and dict strategy formats
        if isinstance(strategy, dict):
            action = strategy.get("action", "HOLD")
            execution_amount = strategy.get("execution_amount", 0.0)
            rationale = strategy.get("rationale", [])
            triggers = strategy.get("triggers", [])
            time_horizon = strategy.get("time_horizon", "1 month")
            risk_budget = strategy.get("risk_budget", 0.05)
            fund_name = funds_data.get(code, {}).get("name", code)
        else:
            action = getattr(strategy, "action", "HOLD")
            if hasattr(action, "value"):
                action = action.value
            execution_amount = getattr(strategy, "execution_amount", 0.0)
            rationale = getattr(strategy, "rationale", [])
            triggers = getattr(strategy, "triggers", [])
            time_horizon = getattr(strategy, "time_horizon", "1 month")
            risk_budget = getattr(strategy, "risk_budget", 0.05)
            fund_name = funds_data.get(code, {}).get("name", code)

        decision = {
            "decision_id": f"decision_{code}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "fund_code": code,
            "fund_name": fund_name,
            "action": action,
            "execution_amount": execution_amount,
            "rationale_anchor": rationale if isinstance(rationale, list) else [str(rationale)],
            "trigger_conditions": triggers if isinstance(triggers, list) else [str(triggers)],
            "invalidating_conditions": [
                "score drops below 40",
                "black swan event",
                "regime changes to CRISIS",
            ],
            "time_horizon": time_horizon,
            "risk_budget": risk_budget,
            "audit_trail": [],
            "version": "decision-contract.v2",
        }
        decisions.append(decision)

    return {
        "final_thesis": {
            "thesis_id": f"thesis_{datetime.now().strftime('%Y%m%d')}",
            "generated_at": datetime.now().isoformat(),
            "summary": f"Research complete after {iteration} iteration(s) across {len(funds_data)} fund(s)",
            "confidence": 0.8 if critic_report.get("passed") else 0.5,
            "decisions": decisions,
        },
        "execution_ledger": {
            "version": "execution-ledger.v1",
            "generated_at": datetime.now().isoformat(),
            "decisions": decisions,
        },
        "phase": "complete",
    }
