"""Test StrategyAdvisor: generates StrategyAdvice from scores, KG, and events."""
import networkx as nx
import pytest

from src.analysis.scoring.types import (
    CompositeScore, ScoreComponent, MarketRegime, score_level,
)
from src.strategy.schemas import StrategyAction, StrategyState, StrategyAdvice
from src.strategy.advisor import StrategyAdvisor


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def _sc(score: float) -> ScoreComponent:
    return ScoreComponent(score=score, detail={}, weights={"d": 1.0}, confidence=0.8)


def _cs(composite: float, regime: MarketRegime = MarketRegime.NORMAL) -> CompositeScore:
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


@pytest.fixture
def kg() -> nx.DiGraph:
    """Minimal knowledge graph with a fund node."""
    G = nx.DiGraph()
    G.add_node("fund:110011")
    return G


@pytest.fixture
def fund_data() -> dict:
    return {"code": "110011", "name": "测试基金", "fund_type": "混合型"}


@pytest.fixture
def favorable_events() -> list[dict]:
    return [
        {"type": "earnings_surprise", "polarity": 0.7, "magnitude": 0.6, "date": "2026-05-25"},
        {"type": "fund_flow", "polarity": 0.5, "magnitude": 0.4, "date": "2026-05-24"},
    ]


@pytest.fixture
def negative_events() -> list[dict]:
    return [
        {"type": "rate_change", "polarity": -0.7, "magnitude": 0.6, "date": "2026-05-25"},
    ]


class TestGenerateAdvice:
    """StrategyAdvisor.generate_advice() produces StrategyAdvice with rules-based fallbacks."""

    def test_returns_strategy_advice(self, fund_data, kg, favorable_events):
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(65.0, MarketRegime.TRENDING),
            kg=kg,
            events=favorable_events,
        )
        assert isinstance(result, StrategyAdvice)
        assert isinstance(result.action, StrategyAction)
        assert isinstance(result.state, StrategyState)
        assert 0.0 <= result.confidence <= 1.0
        assert result.stop_loss_pct is not None
        assert result.take_profit_pct is not None
        assert len(result.reasons) > 0
        assert len(result.position_suggestion) > 0
        assert result.time_horizon in ("short", "medium", "long")

    def test_rules_fallback_hold_position_suggestion(self, fund_data, kg, favorable_events):
        """HOLD state → position_suggestion uses rules fallback."""
        advisor = StrategyAdvisor()
        # Score=55, favorable events → HOLD (from WAIT default)
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(55.0, MarketRegime.TRENDING),
            kg=kg,
            events=favorable_events,
            current_state=StrategyState.WAIT,
        )
        assert result.state == StrategyState.HOLD
        assert "维持当前仓位" in result.position_suggestion

    def test_rules_fallback_add_position_suggestion(self, fund_data, kg, favorable_events):
        """ADD state with high confidence → position_suggestion mentions adding."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(70.0, MarketRegime.TRENDING),
            kg=kg,
            events=favorable_events,
            current_state=StrategyState.HOLD,
        )
        assert result.state == StrategyState.ADD
        assert "加仓" in result.position_suggestion or result.confidence >= 0.6

    def test_rules_fallback_reduce_position_suggestion(self, fund_data, kg, negative_events):
        """REDUCE state → position_suggestion mentions reducing."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(35.0),
            kg=kg,
            events=negative_events,
            current_state=StrategyState.HOLD,
        )
        assert result.state == StrategyState.REDUCE
        assert "减仓" in result.position_suggestion

    def test_rules_fallback_stop_loss_position_suggestion(self, fund_data, kg, negative_events):
        """STOP_LOSS state → position_suggestion mentions stop loss."""
        advisor = StrategyAdvisor()
        # Score < 30 triggers STOP_LOSS from REDUCE
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(25.0),
            kg=kg,
            events=negative_events,
            current_state=StrategyState.REDUCE,
        )
        assert result.state == StrategyState.STOP_LOSS
        assert "止损" in result.position_suggestion

    def test_rules_fallback_wait_position_suggestion(self, fund_data, kg):
        """WAIT state → position_suggestion mentions waiting."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(30.0),
            kg=kg,
            events=[],
            current_state=StrategyState.WAIT,
        )
        assert result.state == StrategyState.WAIT
        assert "等待" in result.position_suggestion

    def test_stop_loss_and_take_profit_set(self, fund_data, kg, favorable_events):
        """Stop loss and take profit should be computed from regime."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(65.0, MarketRegime.TRENDING),
            kg=kg,
            events=favorable_events,
        )
        # TRENDING: stop_loss=12%, take_profit=30%
        assert result.stop_loss_pct == 12.0
        assert result.take_profit_pct == 30.0

    def test_reasons_include_score_info(self, fund_data, kg, favorable_events):
        """Reasons should include evidence about the score and regime."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(65.0, MarketRegime.TRENDING),
            kg=kg,
            events=favorable_events,
        )
        reasons_text = " ".join(result.reasons)
        assert "65" in reasons_text  # score mentioned
        assert "TRENDING" in reasons_text or "trending" in reasons_text.lower()

    def test_valid_transitions_populated(self, fund_data, kg, favorable_events):
        """valid_transitions should be populated from StateMachine."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(65.0, MarketRegime.TRENDING),
            kg=kg,
            events=favorable_events,
        )
        assert len(result.valid_transitions) > 0
        # HOLD can go to WAIT: check in the value list for the current state key
        state_key = result.state.value
        assert "wait" in result.valid_transitions.get(state_key, [])

    def test_trigger_events_populated(self, fund_data, kg, favorable_events):
        """Trigger events should include what to watch for."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(65.0, MarketRegime.TRENDING),
            kg=kg,
            events=favorable_events,
        )
        assert len(result.trigger_events) > 0

    def test_crisis_regime_forces_wait(self, fund_data, kg, favorable_events):
        """CRISIS regime should override to WAIT regardless of other conditions."""
        advisor = StrategyAdvisor()
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(75.0),
            kg=kg,
            events=favorable_events,
            current_state=StrategyState.HOLD,
        )
        # Not crisis, should be ADD (high score + favorable)
        assert result.state != StrategyState.WAIT

        # Now with CRISIS regime
        result_crisis = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(75.0, MarketRegime.CRISIS),
            kg=kg,
            events=favorable_events,
            current_state=StrategyState.HOLD,
        )
        assert result_crisis.state == StrategyState.WAIT

    def test_llm_client_accepted(self, fund_data, kg, favorable_events):
        """Should accept llm_client without error."""
        advisor = StrategyAdvisor(llm_client=None)
        result = advisor.generate_advice(
            fund_code="110011",
            fund_data=fund_data,
            composite_score=_cs(65.0),
            kg=kg,
            events=favorable_events,
            llm_client=None,
        )
        assert isinstance(result, StrategyAdvice)
