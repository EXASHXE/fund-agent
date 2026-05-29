"""StrategyAdvisor: generates StrategyAdvice from scores, KG, events, and state machine."""
from __future__ import annotations

import networkx as nx

from legacy.analysis.scoring.types import CompositeScore, MarketRegime
from legacy.strategy.schemas import StrategyAction, StrategyState, StrategyAdvice
from legacy.strategy.state_machine import StateMachine
from legacy.strategy.stop_logic import StopLogic


def _state_to_action(state: StrategyState) -> StrategyAction:
    """Map StrategyState to StrategyAction."""
    mapping = {
        StrategyState.WAIT: StrategyAction.WAIT,
        StrategyState.HOLD: StrategyAction.HOLD,
        StrategyState.ADD: StrategyAction.ADD,
        StrategyState.REDUCE: StrategyAction.REDUCE,
        StrategyState.STOP_LOSS: StrategyAction.STOP_LOSS,
    }
    return mapping.get(state, StrategyAction.HOLD)


def _score_to_risk_level(composite: float) -> str:
    """Convert composite score to risk level string."""
    if composite >= 75:
        return "low"
    elif composite >= 50:
        return "medium"
    elif composite >= 30:
        return "high"
    else:
        return "extreme"


def _score_to_time_horizon(composite: float) -> str:
    """Convert composite score to time horizon."""
    if composite >= 65:
        return "long"
    elif composite >= 40:
        return "medium"
    else:
        return "short"


def _compute_confidence(composite_score: CompositeScore, events: list[dict]) -> float:
    """Compute confidence based on score and event quality."""
    # Base confidence from composite score (0-100 → 0-1)
    base = composite_score.composite / 100.0

    # Event quality bonus/penalty
    if events:
        avg_polarity = sum(abs(evt.get("polarity", 0) or 0) for evt in events) / len(events)
        avg_magnitude = sum(abs(evt.get("magnitude", 0) or 0) for evt in events) / len(events)
        event_bonus = (avg_polarity + avg_magnitude) * 0.25
        base = min(1.0, base + event_bonus)

    return round(base, 2)


def _rules_position_suggestion(state: StrategyState, composite_score: CompositeScore, confidence: float) -> str:
    """Generate position_suggestion using rules-based fallback (no LLM)."""
    composite = composite_score.composite

    if state == StrategyState.HOLD:
        return "维持当前仓位"
    elif state == StrategyState.ADD:
        if confidence >= 0.6:
            return f"关注加仓机会，当前评分 {composite}"
        return "可适量加仓"
    elif state == StrategyState.REDUCE:
        return "建议适当减仓"
    elif state == StrategyState.STOP_LOSS:
        return "触发止损信号，考虑减仓至零"
    elif state == StrategyState.WAIT:
        return "等待更明确的信号"
    else:
        return "维持当前仓位"


def _build_reasons(state: StrategyState, composite_score: CompositeScore, events: list[dict]) -> list[str]:
    """Build evidence reasons list from state, score, and events."""
    reasons = []

    regime = composite_score.regime
    composite = composite_score.composite
    risk_level = _score_to_risk_level(composite)

    reasons.append(f"市场状态: {regime.value}")
    reasons.append(f"综合评分为 {composite}（风险等级: {risk_level}）")

    if events:
        positive_count = sum(1 for e in events if (e.get("polarity", 0) or 0) > 0.2)
        negative_count = sum(1 for e in events if (e.get("polarity", 0) or 0) < -0.2)
        reasons.append(f"近期事件: {len(events)} 条（正面 {positive_count}，负面 {negative_count}）")

    if state == StrategyState.HOLD:
        reasons.append("当前趋势稳定，维持持有")
    elif state == StrategyState.ADD:
        reasons.append("趋势确认且风险较低，存在加仓机会")
    elif state == StrategyState.REDUCE:
        reasons.append("检测到风险信号或评分恶化")
    elif state == StrategyState.STOP_LOSS:
        reasons.append("风险加速或极端事件触发止损")
    elif state == StrategyState.WAIT:
        reasons.append("等待更多证据信号")

    return reasons


def _build_trigger_events(state: StrategyState, valid_transitions: dict) -> list[str]:
    """Build list of trigger events to watch for state changes."""
    triggers = []
    # valid_transitions is {state_value: [next_state_values]}
    all_targets: set[str] = set()
    for targets in valid_transitions.values():
        all_targets.update(targets)

    if "reduce" in all_targets or "stop_loss" in all_targets:
        triggers.append("评分跌破关键阈值")
        triggers.append("重大负面事件出现")
    if "add" in all_targets:
        triggers.append("趋势确认信号")
        triggers.append("评分持续上升")
    if "wait" in all_targets:
        triggers.append("市场状态变化")
        triggers.append("风险偏好转变")

    return triggers


class StrategyAdvisor:
    """Generate StrategyAdvice using state machine and stop logic.

    Combines: regime detection (from CompositeScore), state transitions,
    stop-loss/take-profit computation, and position suggestions using
    either LLM (if provided) or rules-based fallback.
    """

    def __init__(self, llm_client: object | None = None):
        self._llm_client = llm_client
        self.state_machine = StateMachine()
        self.stop_logic = StopLogic()

    def generate_advice(
        self,
        fund_code: str,
        fund_data: dict,
        composite_score: CompositeScore,
        kg: nx.DiGraph,
        events: list[dict],
        current_state: StrategyState | None = None,
        llm_client: object | None = None,
    ) -> StrategyAdvice:
        """Generate a StrategyAdvice for a fund.

        Pipeline:
        1. Detect regime from composite_score.regime
        2. Transition state machine
        3. Compute stop_loss / take_profit
        4. Generate position_suggestion (rules fallback)
        5. Build evidence reasons list
        6. Return StrategyAdvice
        """
        # 1. Detect regime (already in CompositeScore)
        regime = composite_score.regime

        # 2. Transition state machine
        cs = current_state or StrategyState.WAIT
        new_state = self.state_machine.transition(cs, composite_score, events, regime, fund_data)

        # 3. Compute stop_loss / take_profit
        stop_loss_pct = self.stop_logic.compute_stop_loss(regime, fund_data)
        take_profit_pct = self.stop_logic.compute_take_profit(regime, fund_data)

        # 4. Confidence
        confidence = _compute_confidence(composite_score, events)

        # 5. Position suggestion (rules fallback)
        position_suggestion = _rules_position_suggestion(new_state, composite_score, confidence)

        # 6. Risk level and time horizon
        risk_level = _score_to_risk_level(composite_score.composite)
        time_horizon = _score_to_time_horizon(composite_score.composite)

        # 7. Action (map state to action)
        action = _state_to_action(new_state)

        # 8. Build valid transitions dict
        valid_states = self.state_machine.get_valid_transitions(new_state)
        valid_transitions = {new_state.value: [s.value for s in valid_states]}

        # 9. Build reasons
        reasons = _build_reasons(new_state, composite_score, events)

        # 10. Build trigger events
        trigger_events = _build_trigger_events(new_state, valid_transitions)

        return StrategyAdvice(
            action=action,
            confidence=confidence,
            risk_level=risk_level,
            reasons=reasons,
            trigger_events=trigger_events,
            position_suggestion=position_suggestion,
            time_horizon=time_horizon,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            state=new_state,
            valid_transitions=valid_transitions,
        )
