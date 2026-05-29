"""Tests for event taxonomy and scoring types."""
import pytest
from legacy.events.taxonomy import (
    EventType, EventCategory, EVENT_HIERARCHY,
    ClassifiedEvent, get_event_type, classify_event,
)
from legacy.events.extractor import extract_events_from_text
from legacy.analysis.scoring.types import ScoreComponent, MarketRegime, CompositeScore, score_level


class TestEventTaxonomy:
    def test_event_types_exist(self):
        assert EventType.EARNINGS_SURPRISE.value == "earnings_surprise"
        assert EventType.RATE_CHANGE.value == "rate_change"
        assert EventType.POLICY_SHIFT.value == "policy_shift"
        assert EventType.BLACK_SWAN.value == "black_swan"

    def test_event_categories(self):
        assert EventCategory.FUNDAMENTAL.value == "fundamental"
        assert EventCategory.POLICY.value == "policy"
        assert EventCategory.MARKET.value == "market"

    def test_hierarchy_covers_all_types(self):
        all_types_in_hierarchy = []
        for category, types in EVENT_HIERARCHY.items():
            all_types_in_hierarchy.extend(types)
        for et in EventType:
            assert et in all_types_in_hierarchy, f"{et} not in hierarchy"

    def test_get_event_type(self):
        et = get_event_type("earnings_surprise")
        assert et == EventType.EARNINGS_SURPRISE

    def test_get_event_type_unknown(self):
        et = get_event_type("nonexistent_type")
        assert et == EventType.OTHER

    def test_classify_rate_change(self):
        result = classify_event("美联储宣布加息25个基点")
        assert result.event_type == EventType.RATE_CHANGE
        assert result.polarity < 0

    def test_classify_earnings(self):
        result = classify_event("贵州茅台业绩超预期")
        assert result.event_type == EventType.EARNINGS_SURPRISE
        assert result.polarity > 0

    def test_classify_unknown_text(self):
        result = classify_event("今天天气不错")
        assert result.event_type == EventType.OTHER

    def test_classify_black_swan(self):
        result = classify_event("市场黑天鹅事件")
        assert result.event_type == EventType.BLACK_SWAN
        assert result.polarity < -0.5

    def test_extract_events_from_text(self):
        events = extract_events_from_text("美联储宣布加息25个基点")
        assert len(events) == 1
        assert events[0].event_type == EventType.RATE_CHANGE

    def test_extract_events_empty_text(self):
        events = extract_events_from_text("")
        assert len(events) == 0


class TestScoringTypes:
    def test_score_component_creation(self):
        sc = ScoreComponent(
            score=75.0,
            detail={"sharpe": 80, "sortino": 70},
            weights={"sharpe": 0.3, "sortino": 0.2},
            confidence=0.85,
        )
        assert sc.score == 75.0
        assert sc.confidence == 0.85

    def test_market_regime_enum(self):
        assert MarketRegime.NORMAL.value == "normal"
        assert MarketRegime.HIGH_VOLATILITY.value == "high_volatility"
        assert MarketRegime.TRENDING.value == "trending"
        assert MarketRegime.CRISIS.value == "crisis"

    def test_market_regime_weights_normal(self):
        weights = MarketRegime.NORMAL.weights()
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert weights["quant"] == 0.40
        assert weights["event"] == 0.15

    def test_market_regime_weights_high_volatility(self):
        weights = MarketRegime.HIGH_VOLATILITY.weights()
        assert weights["event"] > MarketRegime.NORMAL.weights()["event"]

    def test_market_regime_weights_crisis(self):
        weights = MarketRegime.CRISIS.weights()
        assert weights["event"] == 0.40
        assert weights["quant"] == 0.15

    def test_composite_score_creation(self):
        sc = ScoreComponent(score=80, detail={}, weights={}, confidence=0.9)
        cs = CompositeScore(
            quant_score=ScoreComponent(score=80, detail={}, weights={}, confidence=0.9),
            fundamental_score=ScoreComponent(score=65, detail={}, weights={}, confidence=0.7),
            event_score=ScoreComponent(score=50, detail={}, weights={}, confidence=0.6),
            position_score=ScoreComponent(score=70, detail={}, weights={}, confidence=0.85),
            timing_score=ScoreComponent(score=55, detail={}, weights={}, confidence=0.5),
            weights_used={"quant": 0.4, "fundamental": 0.2, "event": 0.15, "position": 0.15, "timing": 0.10},
            composite=68.5,
            level="yellow",
            regime=MarketRegime.NORMAL,
        )
        assert cs.composite == 68.5
        assert cs.level == "yellow"
        assert cs.regime == MarketRegime.NORMAL

    def test_score_level_function(self):
        assert score_level(80) == "green"
        assert score_level(50) == "yellow"
        assert score_level(30) == "orange"
        assert score_level(10) == "red"
        assert score_level(75) == "green"