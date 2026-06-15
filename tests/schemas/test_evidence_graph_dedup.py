"""Tests for EvidenceGraph bucketed dedup optimization."""

from datetime import datetime

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


def _make_item(
    evidence_id: str,
    claim: str,
    source_type: str = "test",
    direction: str = "neutral",
    related_entities: list | None = None,
    confidence: float = 0.5,
    evidence_type: str = "SoftEvidence",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_type=source_type,
        timestamp=datetime.now(),
        related_entities=related_entities or ["fund:default"],
        claim=claim,
        value={"title": claim},
        confidence_weight=confidence if evidence_type == "SoftEvidence" else 1.0,
        direction=direction,
    )


class TestEvidenceGraphBucketedDedup:
    def test_no_duplicates_unchanged(self):
        items = [
            _make_item("ev1", "Fund A has high risk", "analysis", "neutral", ["fund:A"]),
            _make_item("ev2", "Fund B has low risk", "analysis", "neutral", ["fund:B"]),
        ]
        graph = EvidenceGraph()
        for item in items:
            graph.add(item)
        graph.deduplicate()
        assert len(graph.items) == 2

    def test_exact_duplicate_removed(self):
        items = [
            _make_item("ev1", "Fund A has high risk", "analysis", "neutral", ["fund:A"], confidence=0.7),
            _make_item("ev2", "Fund A has high risk", "analysis", "neutral", ["fund:A"], confidence=0.5),
        ]
        graph = EvidenceGraph()
        for item in items:
            graph.add(item)
        removed = graph.deduplicate()
        assert len(graph.items) == 1
        assert len(removed) == 1

    def test_different_buckets_not_compared(self):
        """Items in different buckets should not be compared for similarity."""
        items = [
            _make_item("ev1", "Similar claim", "news", "neutral", ["fund:A"]),
            _make_item("ev2", "Similar claim", "analysis", "neutral", ["fund:B"]),
        ]
        graph = EvidenceGraph()
        for item in items:
            graph.add(item)
        graph.deduplicate()
        # Different source_type and related_entities → different buckets → not compared
        assert len(graph.items) == 2

    def test_single_item_no_error(self):
        graph = EvidenceGraph()
        graph.add(_make_item("ev1", "Only item"))
        graph.deduplicate()
        assert len(graph.items) == 1

    def test_empty_graph_no_error(self):
        graph = EvidenceGraph()
        graph.deduplicate()
        assert len(graph.items) == 0

    def test_bucketed_dedup_preserves_higher_confidence(self):
        """Within a bucket, the item with higher confidence survives."""
        items = [
            _make_item("ev1", "Same claim text", "test", "neutral", ["fund:X"], confidence=0.3),
            _make_item("ev2", "Same claim text", "test", "neutral", ["fund:X"], confidence=0.9),
        ]
        graph = EvidenceGraph()
        for item in items:
            graph.add(item)
        removed = graph.deduplicate()
        assert "ev1" in removed
        assert "ev2" in graph.items

    def test_bucketed_dedup_equal_confidence_keeps_first(self):
        """When confidence is equal, the first item in the bucket survives."""
        items = [
            _make_item("ev-first", "Duplicate text", "test", "neutral", ["fund:X"], confidence=0.7),
            _make_item("ev-second", "Duplicate text", "test", "neutral", ["fund:X"], confidence=0.7),
        ]
        graph = EvidenceGraph()
        for item in items:
            graph.add(item)
        removed = graph.deduplicate()
        assert "ev-second" in removed
        assert "ev-first" in graph.items

    def test_multiple_buckets_independent(self):
        """Dedup in one bucket does not affect another bucket."""
        items = [
            # Bucket 1: source_type=news, entities=["fund:A"]
            _make_item("ev1", "Bullish on A", "news", "positive", ["fund:A"], confidence=0.8),
            _make_item("ev2", "Bullish on A", "news", "positive", ["fund:A"], confidence=0.5),
            # Bucket 2: source_type=analysis, entities=["fund:B"]
            _make_item("ev3", "Bearish on B", "analysis", "negative", ["fund:B"], confidence=0.6),
            _make_item("ev4", "Bearish on B", "analysis", "negative", ["fund:B"], confidence=0.9),
        ]
        graph = EvidenceGraph()
        for item in items:
            graph.add(item)
        removed = graph.deduplicate()
        assert len(removed) == 2
        assert len(graph.items) == 2

    def test_different_direction_different_bucket(self):
        """Items with different directions are in different buckets."""
        items = [
            _make_item("ev1", "Same claim", "test", "positive", ["fund:X"]),
            _make_item("ev2", "Same claim", "test", "negative", ["fund:X"]),
        ]
        graph = EvidenceGraph()
        for item in items:
            graph.add(item)
        graph.deduplicate()
        # Different direction → different buckets → not compared
        assert len(graph.items) == 2
