"""Tests for Phase 4 strategy decision model contracts."""

from legacy.strategy.schemas import StrategyAction, StrategyAdvice, StrategyState


def test_trigger_point_evaluates_numeric_context():
    from legacy.strategy.models import TriggerPoint

    trigger = TriggerPoint(
        metric="composite_score",
        operator="<=",
        threshold=60,
        description="评分跌破60",
    )

    assert trigger.is_triggered({"composite_score": 59.9}) is True
    assert trigger.is_triggered({"composite_score": 61}) is False
    assert trigger.is_triggered({"missing": 59}) is False


def test_strategy_decision_from_advice_preserves_execution_contract():
    from legacy.strategy.models import StrategyDecision

    advice = StrategyAdvice(
        action=StrategyAction.HOLD,
        confidence=0.72,
        risk_level="medium",
        reasons=["趋势稳定", "组合风险可控"],
        trigger_events=["评分跌破60", "重大负面事件"],
        position_suggestion="维持当前仓位",
        time_horizon="medium",
        stop_loss_pct=15.0,
        take_profit_pct=25.0,
        state=StrategyState.HOLD,
        valid_transitions={"hold": ["add", "reduce"]},
    )

    decision = StrategyDecision.from_advice(
        fund_code="000001",
        final_score=72.5,
        advice=advice,
        target_weight_pct=18.0,
        adjust_amount=0,
    )
    payload = decision.to_evidence()

    assert decision.action == StrategyAction.HOLD
    assert decision.action_plan.target_weight_pct == 18.0
    assert payload["strategy_advice"]["action"] == "hold"
    assert payload["strategy_advice"]["valid_transitions"] == {"hold": ["add", "reduce"]}
    assert payload["action_plan"]["triggers"][0]["description"] == "评分跌破60"
