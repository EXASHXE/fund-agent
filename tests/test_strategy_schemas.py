"""Test strategy schemas: StrategyAction, StrategyState, StrategyAdvice."""
import pytest

from src.strategy.schemas import StrategyAction, StrategyState, StrategyAdvice


class TestStrategyAction:
    """StrategyAction enum: possible investment actions."""

    def test_has_six_actions(self):
        assert len(StrategyAction) == 6

    def test_action_values(self):
        assert StrategyAction.HOLD.value == "hold"
        assert StrategyAction.ADD.value == "add"
        assert StrategyAction.REDUCE.value == "reduce"
        assert StrategyAction.SWITCH.value == "switch"
        assert StrategyAction.WAIT.value == "wait"
        assert StrategyAction.STOP_LOSS.value == "stop_loss"


class TestStrategyState:
    """StrategyState enum: state machine states."""

    def test_has_five_states(self):
        assert len(StrategyState) == 5

    def test_state_values(self):
        assert StrategyState.WAIT.value == "wait"
        assert StrategyState.HOLD.value == "hold"
        assert StrategyState.ADD.value == "add"
        assert StrategyState.REDUCE.value == "reduce"
        assert StrategyState.STOP_LOSS.value == "stop_loss"


class TestStrategyAdvice:
    """StrategyAdvice dataclass: structured investment advice."""

    def test_construct_with_all_fields(self):
        advice = StrategyAdvice(
            action=StrategyAction.HOLD,
            confidence=0.75,
            risk_level="medium",
            reasons=["趋势确认", "评分稳定"],
            trigger_events=["评分跌破50", "重大负面事件"],
            position_suggestion="维持当前仓位",
            time_horizon="medium",
            stop_loss_pct=15.0,
            take_profit_pct=25.0,
            state=StrategyState.HOLD,
            valid_transitions={
                "hold": ["wait", "add", "reduce"],
            },
        )
        assert advice.action == StrategyAction.HOLD
        assert advice.confidence == 0.75
        assert advice.risk_level == "medium"
        assert advice.reasons == ["趋势确认", "评分稳定"]
        assert advice.trigger_events == ["评分跌破50", "重大负面事件"]
        assert advice.position_suggestion == "维持当前仓位"
        assert advice.time_horizon == "medium"
        assert advice.stop_loss_pct == 15.0
        assert advice.take_profit_pct == 25.0
        assert advice.state == StrategyState.HOLD
        assert advice.valid_transitions == {"hold": ["wait", "add", "reduce"]}

    def test_optional_fields_default_to_none(self):
        advice = StrategyAdvice(
            action=StrategyAction.WAIT,
            confidence=0.0,
            risk_level="low",
            reasons=[],
            trigger_events=[],
            position_suggestion="等待信号",
            time_horizon="short",
            state=StrategyState.WAIT,
            valid_transitions={},
        )
        assert advice.stop_loss_pct is None
        assert advice.take_profit_pct is None

    def test_confidence_clamped_between_zero_and_one(self):
        advice = StrategyAdvice(
            action=StrategyAction.ADD,
            confidence=0.85,
            risk_level="low",
            reasons=["加仓信号"],
            trigger_events=[],
            position_suggestion="加仓10%",
            time_horizon="medium",
            state=StrategyState.ADD,
            valid_transitions={"add": ["hold", "reduce"]},
        )
        assert 0.0 <= advice.confidence <= 1.0

    def test_risk_level_accepts_valid_values(self):
        valid_levels = ["low", "medium", "high", "extreme"]
        for level in valid_levels:
            advice = StrategyAdvice(
                action=StrategyAction.HOLD,
                confidence=0.5,
                risk_level=level,
                reasons=[],
                trigger_events=[],
                position_suggestion="持有",
                time_horizon="medium",
                state=StrategyState.HOLD,
                valid_transitions={},
            )
            assert advice.risk_level == level
