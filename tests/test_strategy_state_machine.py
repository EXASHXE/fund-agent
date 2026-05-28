"""Test StateMachine: strategy state transitions based on scores, events, regime.

Transition rules (per spec):
    WAIT → HOLD: favorable event polarity + trend confirmed + score >= 50
    WAIT → WAIT: insufficient evidence
    HOLD → ADD: trend confirmation + low risk + score >= 65
    HOLD → REDUCE: risk signal (deteriorating scores or negative events) OR score < 40
    HOLD → WAIT: regime change / insufficient data
    ADD → HOLD: profit target approached OR risk increasing
    ADD → REDUCE: significant negative event OR score drops below 50
    REDUCE → STOP_LOSS: accelerating risk / black swan OR score < 30
    REDUCE → HOLD: risk signal eased
    STOP_LOSS → WAIT: conditions re-evaluated after cool-down
    Any → WAIT: regime shift to CRISIS
"""
from __future__ import annotations

import pytest

from src.analysis.scoring.types import (
    CompositeScore, ScoreComponent, MarketRegime, score_level,
)
from src.strategy.schemas import StrategyState
from src.strategy.state_machine import StateMachine


# ----------------------------------------------------------------
# Helpers for building test fixtures
# ----------------------------------------------------------------
def _sc(c: float) -> ScoreComponent:
    """Create a ScoreComponent with given score."""
    return ScoreComponent(
        score=c,
        detail={},
        weights={"dummy": 1.0},
        confidence=0.8,
    )


def _cs(composite: float, regime: MarketRegime = MarketRegime.NORMAL) -> CompositeScore:
    """Create a CompositeScore with all sub-scores set to composite value."""
    return CompositeScore(
        quant_score=_sc(composite),
        fundamental_score=_sc(composite),
        event_score=_sc(composite),
        position_score=_sc(composite),
        timing_score=_sc(composite),
        weights_used=regime.weights(),
        composite=composite,
        level=score_level(composite),
        regime=regime,
    )


def _favorable_events() -> list[dict]:
    return [
        {"type": "earnings_surprise", "polarity": 0.7, "magnitude": 0.6, "date": "2026-05-25"},
        {"type": "fund_flow", "polarity": 0.5, "magnitude": 0.4, "date": "2026-05-24"},
    ]


def _negative_events() -> list[dict]:
    return [
        {"type": "rate_change", "polarity": -0.7, "magnitude": 0.6, "date": "2026-05-25"},
        {"type": "outflow", "polarity": -0.6, "magnitude": 0.5, "date": "2026-05-24"},
    ]


def _black_swan_events() -> list[dict]:
    return [
        {"type": "black_swan", "polarity": -0.9, "magnitude": 0.9, "date": "2026-05-25"},
    ]


def _neutral_events() -> list[dict]:
    return [
        {"type": "routine", "polarity": 0.0, "magnitude": 0.1, "date": "2026-05-25"},
    ]


# ----------------------------------------------------------------
# WAIT → HOLD
# ----------------------------------------------------------------
class TestWaitToHold:
    """WAIT → HOLD: favorable event polarity + trend confirmed + score >= 50."""

    def test_transitions_to_hold_with_favorable_events_and_high_score(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.WAIT,
            _cs(55.0, MarketRegime.TRENDING),
            _favorable_events(),
            MarketRegime.TRENDING,
            {},
        )
        assert result == StrategyState.HOLD

    def test_stays_wait_when_score_below_50(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.WAIT,
            _cs(45.0, MarketRegime.TRENDING),
            _favorable_events(),
            MarketRegime.TRENDING,
            {},
        )
        assert result == StrategyState.WAIT

    def test_stays_wait_when_no_favorable_events(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.WAIT,
            _cs(55.0),
            _neutral_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.WAIT

    def test_stays_wait_with_no_events(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.WAIT,
            _cs(55.0),
            [],
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.WAIT

    def test_transitions_to_hold_even_in_normal_regime_with_sufficient_score_and_favorable(self):
        """Trending condition can be met in any regime if score >= 50 and favorable events."""
        sm = StateMachine()
        result = sm.transition(
            StrategyState.WAIT,
            _cs(52.0, MarketRegime.NORMAL),
            _favorable_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.HOLD


# ----------------------------------------------------------------
# HOLD transitions
# ----------------------------------------------------------------
class TestHoldToAdd:
    """HOLD → ADD: trend confirmation + low risk + score >= 65."""

    def test_transitions_to_add_when_conditions_met(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.HOLD,
            _cs(68.0, MarketRegime.TRENDING),
            _favorable_events(),
            MarketRegime.TRENDING,
            {},
        )
        assert result == StrategyState.ADD

    def test_stays_hold_when_score_below_65(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.HOLD,
            _cs(60.0, MarketRegime.TRENDING),
            _favorable_events(),
            MarketRegime.TRENDING,
            {},
        )
        assert result == StrategyState.HOLD

    def test_stays_hold_when_no_favorable_events(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.HOLD,
            _cs(70.0, MarketRegime.TRENDING),
            _neutral_events(),
            MarketRegime.TRENDING,
            {},
        )
        assert result == StrategyState.HOLD


class TestHoldToReduce:
    """HOLD → REDUCE: risk signal OR score < 40."""

    def test_transitions_to_reduce_on_negative_events(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.HOLD,
            _cs(55.0),
            _negative_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.REDUCE

    def test_transitions_to_reduce_on_low_score(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.HOLD,
            _cs(35.0),
            _neutral_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.REDUCE

    def test_transitions_to_reduce_on_black_swan(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.HOLD,
            _cs(55.0),
            _black_swan_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.REDUCE


# ----------------------------------------------------------------
# ADD transitions
# ----------------------------------------------------------------
class TestAddToReduce:
    """ADD → REDUCE: significant negative event OR score < 50."""

    def test_transitions_to_reduce_on_negative_events(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.ADD,
            _cs(70.0),
            _negative_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.REDUCE

    def test_transitions_to_reduce_on_low_score(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.ADD,
            _cs(45.0),
            _favorable_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.REDUCE

    def test_stays_add_when_conditions_normal(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.ADD,
            _cs(70.0),
            _favorable_events(),
            MarketRegime.TRENDING,
            {},
        )
        assert result == StrategyState.ADD


class TestAddToHold:
    """ADD → HOLD: risk increasing."""

    def test_transitions_to_hold_on_risk_signal(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.ADD,
            _cs(60.0),
            _neutral_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.HOLD


# ----------------------------------------------------------------
# REDUCE transitions
# ----------------------------------------------------------------
class TestReduceToStopLoss:
    """REDUCE → STOP_LOSS: accelerating risk / black swan OR score < 30."""

    def test_transitions_to_stop_loss_on_black_swan(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.REDUCE,
            _cs(45.0),
            _black_swan_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.STOP_LOSS

    def test_transitions_to_stop_loss_on_very_low_score(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.REDUCE,
            _cs(25.0),
            _neutral_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.STOP_LOSS

    def test_stays_reduce_when_moderate(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.REDUCE,
            _cs(45.0),
            _neutral_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.REDUCE


class TestReduceToHold:
    """REDUCE → HOLD: risk signal eased (favorable events + score >= 50)."""

    def test_transitions_to_hold_when_risk_eased(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.REDUCE,
            _cs(55.0, MarketRegime.TRENDING),
            _favorable_events(),
            MarketRegime.TRENDING,
            {},
        )
        assert result == StrategyState.HOLD


# ----------------------------------------------------------------
# STOP_LOSS transitions
# ----------------------------------------------------------------
class TestStopLossToWait:
    """STOP_LOSS → WAIT: conditions re-evaluated after cool-down."""

    def test_transitions_to_wait_from_stop_loss(self):
        sm = StateMachine()
        result = sm.transition(
            StrategyState.STOP_LOSS,
            _cs(40.0),
            _neutral_events(),
            MarketRegime.NORMAL,
            {},
        )
        assert result == StrategyState.WAIT


# ----------------------------------------------------------------
# Crisis override
# ----------------------------------------------------------------
class TestCrisisOverride:
    """Any state → WAIT when regime shifts to CRISIS."""

    @pytest.mark.parametrize("state", list(StrategyState))
    def test_all_states_transition_to_wait_in_crisis(self, state):
        sm = StateMachine()
        result = sm.transition(
            state,
            _cs(50.0),
            _neutral_events(),
            MarketRegime.CRISIS,
            {},
        )
        assert result == StrategyState.WAIT


# ----------------------------------------------------------------
# Valid transitions
# ----------------------------------------------------------------
class TestValidTransitions:
    """StateMachine.get_valid_transitions() returns all possible next states."""

    def test_wait_valid_transitions(self):
        sm = StateMachine()
        transitions = sm.get_valid_transitions(StrategyState.WAIT)
        assert StrategyState.WAIT in transitions
        assert StrategyState.HOLD in transitions

    def test_hold_valid_transitions(self):
        sm = StateMachine()
        transitions = sm.get_valid_transitions(StrategyState.HOLD)
        assert StrategyState.ADD in transitions
        assert StrategyState.REDUCE in transitions
        assert StrategyState.WAIT in transitions

    def test_add_valid_transitions(self):
        sm = StateMachine()
        transitions = sm.get_valid_transitions(StrategyState.ADD)
        assert StrategyState.HOLD in transitions
        assert StrategyState.REDUCE in transitions

    def test_reduce_valid_transitions(self):
        sm = StateMachine()
        transitions = sm.get_valid_transitions(StrategyState.REDUCE)
        assert StrategyState.STOP_LOSS in transitions
        assert StrategyState.HOLD in transitions

    def test_stop_loss_valid_transitions(self):
        sm = StateMachine()
        transitions = sm.get_valid_transitions(StrategyState.STOP_LOSS)
        assert StrategyState.WAIT in transitions

    def test_crisis_valid_transitions_for_all(self):
        sm = StateMachine()
        for state in StrategyState:
            transitions = sm.get_valid_transitions(state)
            assert StrategyState.WAIT in transitions
