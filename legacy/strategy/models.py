"""Phase 4 strategy decision contracts.

These models sit above StrategyAdvice and are shaped for report evidence and
agent-to-agent handoff. They do not replace the state machine schemas; they
package execution intent, triggers, and risk-budget effects in one place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from legacy.strategy.schemas import StrategyAction, StrategyAdvice


_OPERATORS = {
    ">": lambda actual, expected: actual > expected,
    ">=": lambda actual, expected: actual >= expected,
    "<": lambda actual, expected: actual < expected,
    "<=": lambda actual, expected: actual <= expected,
    "==": lambda actual, expected: actual == expected,
    "!=": lambda actual, expected: actual != expected,
}


@dataclass
class TriggerPoint:
    """A measurable condition that can change a strategy decision."""

    metric: str
    operator: str
    threshold: float | int | str
    description: str
    confidence: float = 0.5

    def is_triggered(self, context: dict[str, Any]) -> bool:
        actual = context.get(self.metric)
        if actual is None or self.operator not in _OPERATORS:
            return False
        try:
            return bool(_OPERATORS[self.operator](actual, self.threshold))
        except TypeError:
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "description": self.description,
            "confidence": self.confidence,
        }


@dataclass
class ActionPlan:
    """Execution plan produced from a strategy decision."""

    target_weight_pct: float | None = None
    adjust_amount: float | None = None
    entry_plan: list[str] = field(default_factory=list)
    risk_budget_impact: dict[str, Any] = field(default_factory=dict)
    triggers: list[TriggerPoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_weight_pct": self.target_weight_pct,
            "adjust_amount": self.adjust_amount,
            "entry_plan": list(self.entry_plan),
            "risk_budget_impact": dict(self.risk_budget_impact),
            "triggers": [trigger.to_dict() for trigger in self.triggers],
        }


@dataclass
class StrategyDecision:
    """Final strategy decision contract for one fund."""

    fund_code: str
    action: StrategyAction
    final_score: float
    confidence: float
    risk_level: str
    rationale: list[str]
    action_plan: ActionPlan = field(default_factory=ActionPlan)
    strategy_advice: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_advice(
        cls,
        fund_code: str,
        final_score: float,
        advice: StrategyAdvice,
        target_weight_pct: float | None = None,
        adjust_amount: float | None = None,
    ) -> "StrategyDecision":
        triggers = [
            TriggerPoint(
                metric="manual_review",
                operator="==",
                threshold=True,
                description=description,
                confidence=advice.confidence,
            )
            for description in advice.trigger_events
        ]
        action_plan = ActionPlan(
            target_weight_pct=target_weight_pct,
            adjust_amount=adjust_amount,
            entry_plan=[advice.position_suggestion] if advice.position_suggestion else [],
            triggers=triggers,
        )
        strategy_advice = {
            "action": advice.action.value,
            "confidence": advice.confidence,
            "risk_level": advice.risk_level,
            "reasons": list(advice.reasons),
            "trigger_events": list(advice.trigger_events),
            "position_suggestion": advice.position_suggestion,
            "time_horizon": advice.time_horizon,
            "stop_loss_pct": advice.stop_loss_pct,
            "take_profit_pct": advice.take_profit_pct,
            "state": advice.state.value,
            "valid_transitions": dict(advice.valid_transitions),
        }
        return cls(
            fund_code=fund_code,
            action=advice.action,
            final_score=final_score,
            confidence=advice.confidence,
            risk_level=advice.risk_level,
            rationale=list(advice.reasons),
            action_plan=action_plan,
            strategy_advice=strategy_advice,
        )

    def to_evidence(self) -> dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "action": self.action.value,
            "final_score": self.final_score,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "rationale": list(self.rationale),
            "action_plan": self.action_plan.to_dict(),
            "strategy_advice": dict(self.strategy_advice),
        }
