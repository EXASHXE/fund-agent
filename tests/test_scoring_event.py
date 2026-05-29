"""Test EventScoreCalculator: event-based scoring with time decay and KG impact chains."""
import math
from datetime import date, timedelta

import networkx as nx
import pytest

from legacy.analysis.scoring.types import ScoreComponent
from src.graph.builder import KnowledgeGraphBuilder
from src.graph.schema import (
    EventNode, KGEdge, KGEdgeType,
    FundNode, StockNode,
)


@pytest.fixture
def kg_builder():
    return KnowledgeGraphBuilder()


@pytest.fixture
def graph_with_event_chain():
    """Build a KG with fund, stock, and event nodes plus impact edges."""
    G = nx.DiGraph()

    # Fund
    fund = FundNode(code="110011", name="测试基金", fund_type="混合")
    G.add_node("fund:110011", data=fund)

    # Stock
    stock = StockNode(code="600519", name="贵州茅台", sector="食品饮料", industry="食品饮料")
    G.add_node("stock:600519", data=stock)
    holds_edge = KGEdge(source="fund:110011", target="stock:600519", edge_type=KGEdgeType.HOLDS, weight=15.0)
    G.add_edge("fund:110011", "stock:600519", edge_data=holds_edge)

    # Event
    event = EventNode(event_id="evt_001", event_type="earnings_surprise", date="2026-05-25", polarity=0.8, magnitude=0.7)
    G.add_node("event:evt_001", data=event)
    impact_edge = KGEdge(source="event:evt_001", target="stock:600519", edge_type=KGEdgeType.IMPACTS, polarity=0.8, magnitude=0.7)
    G.add_edge("event:evt_001", "stock:600519", edge_data=impact_edge)

    return G


@pytest.fixture
def empty_graph():
    return nx.DiGraph()


class TestEventScoreCompute:
    """Core event score computation."""

    def test_returns_score_component(self, graph_with_event_chain):
        """Should return a valid ScoreComponent."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator()
        events = [
            {"id": "evt_001", "polarity": 0.8, "magnitude": 0.7, "date": "2026-05-25", "type": "earnings_surprise"},
        ]
        result = calc.compute("110011", events, graph_with_event_chain)

        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100
        assert isinstance(result.detail, dict)
        assert 0 <= result.confidence <= 1.0

    def test_no_events_fallback(self):
        """Empty events list returns default score with low confidence."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator()
        result = calc.compute("110011", [], nx.DiGraph())

        assert result.score == 50.0
        assert result.confidence == 0.1
        assert result.detail.get("no_events") is True

    def test_positive_events_raise_score(self, graph_with_event_chain):
        """Positive polarity events should push score above 50."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator()
        events = [
            {"id": "evt_001", "polarity": 0.8, "magnitude": 0.7, "date": "2026-05-25", "type": "earnings_surprise"},
        ]
        result = calc.compute("110011", events, graph_with_event_chain)
        assert result.score > 50.0

    def test_negative_events_lower_score(self):
        """Negative polarity events should push score below 50."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        G = nx.DiGraph()
        fund = FundNode(code="110011", name="测试", fund_type="混合")
        G.add_node("fund:110011", data=fund)
        stock = StockNode(code="000001", name="平安银行", sector="银行", industry="银行")
        G.add_node("stock:000001", data=stock)
        holds = KGEdge(source="fund:110011", target="stock:000001", edge_type=KGEdgeType.HOLDS, weight=10.0)
        G.add_edge("fund:110011", "stock:000001", edge_data=holds)
        event = EventNode(event_id="evt_neg", event_type="market_crash", date="2026-05-25", polarity=-0.9, magnitude=0.9)
        G.add_node("event:evt_neg", data=event)
        impact = KGEdge(source="event:evt_neg", target="stock:000001", edge_type=KGEdgeType.IMPACTS, polarity=-0.9, magnitude=0.9)
        G.add_edge("event:evt_neg", "stock:000001", edge_data=impact)

        calc = EventScoreCalculator()
        events = [
            {"id": "evt_neg", "polarity": -0.9, "magnitude": 0.9, "date": "2026-05-25"},
        ]
        result = calc.compute("110011", events, G)
        assert result.score < 50.0

    def test_time_decay_reduces_impact(self, graph_with_event_chain):
        """Older events should have less impact due to exponential decay."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator(lambda_decay=0.2)
        today = date.today().isoformat()

        # Recent event
        events_recent = [
            {"id": "evt_001", "polarity": 0.8, "magnitude": 0.7, "date": today},
        ]
        # Old event
        old_date = (date.today() - timedelta(days=30)).isoformat()
        events_old = [
            {"id": "evt_001", "polarity": 0.8, "magnitude": 0.7, "date": old_date},
        ]

        recent_result = calc.compute("110011", events_recent, graph_with_event_chain)
        old_result = calc.compute("110011", events_old, graph_with_event_chain)

        # Recent should have score closer to 100 (more impact)
        assert recent_result.score > old_result.score

    def test_multiple_events_aggregated(self, graph_with_event_chain):
        """Multiple events should be aggregated."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        # Add second event
        stock2 = StockNode(code="000858", name="五粮液", sector="食品饮料", industry="食品饮料")
        graph_with_event_chain.add_node("stock:000858", data=stock2)
        holds2 = KGEdge(source="fund:110011", target="stock:000858", edge_type=KGEdgeType.HOLDS, weight=10.0)
        graph_with_event_chain.add_edge("fund:110011", "stock:000858", edge_data=holds2)
        event2 = EventNode(event_id="evt_002", event_type="earnings_surprise", date="2026-05-25", polarity=0.6, magnitude=0.5)
        graph_with_event_chain.add_node("event:evt_002", data=event2)
        impact2 = KGEdge(source="event:evt_002", target="stock:000858", edge_type=KGEdgeType.IMPACTS, polarity=0.6, magnitude=0.5)
        graph_with_event_chain.add_edge("event:evt_002", "stock:000858", edge_data=impact2)

        calc = EventScoreCalculator()
        events = [
            {"id": "evt_001", "polarity": 0.8, "magnitude": 0.7, "date": "2026-05-25"},
            {"id": "evt_002", "polarity": 0.6, "magnitude": 0.5, "date": "2026-05-25"},
        ]
        result = calc.compute("110011", events, graph_with_event_chain)

        assert result.score > 50.0
        # Confidence should increase with more events
        assert result.confidence >= 0.3

    def test_confidence_scales_with_event_count(self):
        """More events should yield higher confidence."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator()
        events_1 = [{"polarity": 0.5, "magnitude": 0.5, "date": "2026-05-25"}]
        events_5 = [{"polarity": 0.5, "magnitude": 0.5, "date": "2026-05-25"} for _ in range(5)]

        r1 = calc.compute("110011", events_1, nx.DiGraph())
        r5 = calc.compute("110011", events_5, nx.DiGraph())

        assert r5.confidence > r1.confidence

    def test_no_kg_events_still_scored(self):
        """Events without KG nodes are scored using direct polarity/magnitude."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator()
        events = [
            {"polarity": 0.7, "magnitude": 0.8, "date": "2026-05-25"},
            {"polarity": -0.5, "magnitude": 0.6, "date": "2026-05-24"},
        ]
        result = calc.compute("110011", events, nx.DiGraph())

        assert isinstance(result, ScoreComponent)
        assert 0 <= result.score <= 100
        # Positive + negative mix should be near 50
        assert result.confidence > 0.1

    def test_detail_contains_contributions(self, graph_with_event_chain):
        """Detail dict should list per-event contributions."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator()
        events = [
            {"id": "evt_001", "polarity": 0.8, "magnitude": 0.7, "date": "2026-05-25"},
        ]
        result = calc.compute("110011", events, graph_with_event_chain)

        assert "contributions" in result.detail
        assert len(result.detail["contributions"]) == 1

    def test_missing_polarity_defaults_to_zero(self):
        """Events without polarity should default to 0."""
        from legacy.analysis.scoring.event_score import EventScoreCalculator

        calc = EventScoreCalculator()
        events = [{"magnitude": 0.8, "date": "2026-05-25"}]
        result = calc.compute("110011", events, nx.DiGraph())

        assert result.score == 50.0  # zero contribution → neutral
