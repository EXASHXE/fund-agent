"""StateMachine: strategy state transitions based on scores, events, and regime.

Transition rules:
    WAIT → HOLD: favorable event polarity + trend confirmed + score >= 50
    WAIT → WAIT: insufficient evidence (default)
    HOLD → ADD: trend confirmation + low risk + score >= 65
    HOLD → REDUCE: risk signal (negative events or black swan) OR score < 40
    HOLD → HOLD: no change signal (default)
    ADD → REDUCE: significant negative event OR score < 50
    ADD → HOLD: conditions for ADD no longer met (score < 65 or no favorable events)
    ADD → ADD: conditions still hold (default)
    REDUCE → STOP_LOSS: accelerating risk / black swan OR score < 30
    REDUCE → HOLD: risk signal eased (favorable events + score >= 50)
    REDUCE → REDUCE: risk persists (default)
    STOP_LOSS → WAIT: cool-down re-evaluation
    Any → WAIT: regime shift to CRISIS
"""
from __future__ import annotations

from src.analysis.scoring.types import CompositeScore, MarketRegime
from src.strategy.schemas import StrategyState

# Polarity threshold for classifying favorable/negative events
_FAVORABLE_THRESHOLD = 0.2
_NEGATIVE_THRESHOLD = -0.2

# Valid transitions for each state (excluding CRISIS override)
_VALID_TRANSITIONS: dict[StrategyState, list[StrategyState]] = {
    StrategyState.WAIT: [StrategyState.WAIT, StrategyState.HOLD],
    StrategyState.HOLD: [StrategyState.HOLD, StrategyState.ADD, StrategyState.REDUCE, StrategyState.WAIT],
    StrategyState.ADD: [StrategyState.ADD, StrategyState.HOLD, StrategyState.REDUCE],
    StrategyState.REDUCE: [StrategyState.REDUCE, StrategyState.HOLD, StrategyState.STOP_LOSS],
    StrategyState.STOP_LOSS: [StrategyState.STOP_LOSS, StrategyState.WAIT],
}


def _is_black_swan(events: list[dict]) -> bool:
    """Check for black swan or market crash events."""
    for evt in events:
        evt_type = (evt.get("type") or "").lower()
        if evt_type in ("black_swan", "market_crash"):
            return True
    return False


def _has_favorable_events(events: list[dict]) -> bool:
    """Check if any event has positive polarity above threshold."""
    for evt in events:
        polarity = evt.get("polarity", 0) or 0
        if polarity > _FAVORABLE_THRESHOLD:
            return True
    return False


def _has_negative_events(events: list[dict]) -> bool:
    """Check if any event has negative polarity below threshold."""
    for evt in events:
        polarity = evt.get("polarity", 0) or 0
        if polarity < _NEGATIVE_THRESHOLD:
            return True
    return False


class StateMachine:
    """Strategy state machine with rule-based transitions.

    Determines the next StrategyState from current state, composite score,
    events, market regime, and fund data. Follows deterministic rules
    defined in the transition matrix above.
    """

    def transition(
        self,
        current_state: StrategyState,
        composite_score: CompositeScore,
        events: list[dict],
        regime: MarketRegime,
        fund_data: dict,
    ) -> StrategyState:
        """Compute the next state given current conditions.

        Args:
            current_state: Current StrategyState.
            composite_score: Full CompositeScore with all sub-scores and regime.
            events: List of event dicts (with type, polarity, magnitude, date).
            regime: Current MarketRegime.
            fund_data: Raw fund data dict (reserved for future use).

        Returns:
            The next StrategyState after applying transition rules.
        """
        # CRISIS override: any state → WAIT
        if regime == MarketRegime.CRISIS:
            return StrategyState.WAIT

        composite = composite_score.composite
        black_swan = _is_black_swan(events)
        favorable = _has_favorable_events(events)
        negative = _has_negative_events(events)

        # WAIT
        if current_state == StrategyState.WAIT:
            if favorable and composite >= 50:
                return StrategyState.HOLD
            return StrategyState.WAIT

        # HOLD
        if current_state == StrategyState.HOLD:
            if favorable and composite >= 65:
                return StrategyState.ADD
            if black_swan or negative or composite < 40:
                return StrategyState.REDUCE
            return StrategyState.HOLD

        # ADD
        if current_state == StrategyState.ADD:
            if black_swan or negative or composite < 50:
                return StrategyState.REDUCE
            if composite < 65 or not favorable:
                return StrategyState.HOLD
            return StrategyState.ADD

        # REDUCE
        if current_state == StrategyState.REDUCE:
            if black_swan or composite < 30:
                return StrategyState.STOP_LOSS
            if favorable and composite >= 50:
                return StrategyState.HOLD
            return StrategyState.REDUCE

        # STOP_LOSS → WAIT (cool-down)
        if current_state == StrategyState.STOP_LOSS:
            return StrategyState.WAIT

        # Default fallback
        return StrategyState.WAIT

    def get_valid_transitions(self, state: StrategyState) -> list[StrategyState]:
        """Return all possible next states from the given state.

        CRISIS is always a possible transition (via regime override).
        """
        transitions = list(_VALID_TRANSITIONS.get(state, []))
        if StrategyState.WAIT not in transitions:
            transitions.append(StrategyState.WAIT)  # CRISIS override path
        return transitions

    def get_all_states(self) -> list[StrategyState]:
        """Return all possible states."""
        return list(StrategyState)
