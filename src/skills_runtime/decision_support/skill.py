"""Decision support skill runtime.

This is the only runtime skill that may produce formal Decision and
ExecutionLedger artifacts. It consumes an already compiled EvidenceGraph from
the host agent and applies local, deterministic contract rules.
"""

from __future__ import annotations

from typing import Any

from src.schemas.decision import ExecutionLedger
from src.schemas.skill import SkillInput, SkillOutput

from .action_policy import _normalized_action
from .context import _dict
from .decision_stage import (
    _build_decision,
    _critique_from_payload,
    _task_from_payload,
)
from .graph_stage import _graph_from_payload
from .status_stage import _SkillContractError, build_failed_output
from .trade_plan_stage import (
    _decision_from_trade,
    select_top_trades,
    validate_and_filter_trades,
)


class DecisionSupportSkill:
    """Host-callable decision support skill."""

    mcp_adapter = None
    tool_registry = None

    def __init__(
        self,
        decision_engine: Any | None = None,
        ledger_builder: Any | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.ledger_builder = ledger_builder

    def run(self, skill_input: SkillInput) -> SkillOutput:
        try:
            if "evidence_graph" not in skill_input.payload:
                raise _SkillContractError(
                    code="INVALID_INPUT",
                    message="DecisionSupportSkill requires payload.evidence_graph",
                )

            graph = _graph_from_payload(skill_input.payload.get("evidence_graph"))

            trade_plan = skill_input.payload.get("trade_plan", {})
            selected_trade_ids = skill_input.payload.get("selected_trade_ids", [])

            if trade_plan and trade_plan.get("suggested_trade_plan"):
                return self._run_trade_plan_path(skill_input, graph, trade_plan, selected_trade_ids)

            return self._run_single_decision_path(skill_input, graph)
        except Exception as exc:
            return build_failed_output(skill_input, exc)

    def _run_trade_plan_path(
        self,
        skill_input: SkillInput,
        graph,
        trade_plan: dict[str, Any],
        selected_trade_ids: list[str],
    ) -> SkillOutput:
        trades = trade_plan["suggested_trade_plan"]
        portfolio_context = _dict(skill_input.payload.get("portfolio_context"))
        risk_profile = _dict(skill_input.payload.get("risk_profile"))
        constraints = _dict(skill_input.payload.get("constraints"))
        time_horizon = skill_input.payload.get("time_horizon", "medium_term")
        is_short_term = time_horizon in ("short_term", "1 month", "3 months")
        has_real_evidence = bool(graph.items)

        validated_trades, output_warnings = validate_and_filter_trades(
            trades=trades,
            selected_trade_ids=selected_trade_ids,
            graph=graph,
            portfolio_context=portfolio_context,
            risk_profile=risk_profile,
            constraints=constraints,
            is_short_term=is_short_term,
            has_real_evidence=has_real_evidence,
        )

        validated_trades = select_top_trades(validated_trades, selected_trade_ids)

        if validated_trades:
            decisions = [
                _decision_from_trade(t, graph, skill_input.payload)
                for t in validated_trades
            ]
            ledger = ExecutionLedger(decisions=decisions)
            return SkillOutput(
                step_id=skill_input.step_id,
                skill_name=skill_input.skill_name,
                artifacts={
                    "execution_ledger": ledger.to_dict(),
                    "decisions": [d.to_dict() for d in decisions],
                    "decision_count": len(decisions),
                    "audit_trail": [
                        entry
                        for d in decisions
                        for entry in d.audit_trail
                    ],
                },
                warnings=output_warnings,
                status="OK" if decisions else "PARTIAL",
            )
        else:
            return SkillOutput(
                step_id=skill_input.step_id,
                skill_name=skill_input.skill_name,
                artifacts={
                    "warnings": output_warnings,
                    "decision": {
                        "action": "WAIT",
                        "execution_amount": 0.0,
                        "trigger_conditions": [
                            "Insufficient suitable trades available",
                            "No trades passed amount validation",
                        ],
                        "invalidating_conditions": [
                            "New suitable trades become available",
                            "Evidence quality improves",
                        ],
                    },
                },
                warnings=output_warnings,
                status="PARTIAL",
            )

    def _run_single_decision_path(
        self,
        skill_input: SkillInput,
        graph,
    ) -> SkillOutput:
        requested_action = _normalized_action(
            skill_input.payload.get("requested_action")
        )

        task = _task_from_payload(skill_input.payload)
        critique_status, critique_issues = _critique_from_payload(
            skill_input.payload, graph
        )
        decision = _build_decision(
            payload=skill_input.payload,
            task=task,
            graph=graph,
            critique_status=critique_status,
            critique_issues=critique_issues,
            requested_action=requested_action,
            skill_input=skill_input,
        )
        ledger = ExecutionLedger(decisions=[decision])
        decision_payload = decision.to_dict()
        ledger_payload = ledger.to_dict()
        return SkillOutput(
            step_id=skill_input.step_id,
            skill_name=skill_input.skill_name,
            artifacts={
                "decision": decision_payload,
                "execution_ledger": ledger_payload,
                "decision_status": decision.action,
                "audit_trail": list(decision.audit_trail),
            },
            status="OK",
        )
