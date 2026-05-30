"""Tests for EvidenceGraph — unified evidence store with dedup, conflict detection, and hybrid upgrades."""

from __future__ import annotations

from datetime import datetime

import pytest
from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_hard(
    evidence_id: str,
    claim: str = "Hard evidence claim",
    entities: list[str] | None = None,
    direction: str = "neutral",
    **overrides: object,
) -> EvidenceItem:
    """Build a valid HardEvidence item with overridable fields."""
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type="HardEvidence",
        source_type=str(overrides.pop("source_type", "test_tool")),
        timestamp=datetime.now(),
        related_entities=entities or ["fund:110011"],
        claim=claim,
        value=overrides.pop("value", 42.0),
        confidence_weight=1.0,
        direction=direction,
        **overrides,  # type: ignore[arg-type]
    )


def _make_soft(
    evidence_id: str,
    claim: str = "Soft evidence claim",
    entities: list[str] | None = None,
    direction: str = "neutral",
    confidence: float = 0.5,
    **overrides: object,
) -> EvidenceItem:
    """Build a valid SoftEvidence item with overridable fields."""
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type="SoftEvidence",
        source_type=str(overrides.pop("source_type", "finnhub")),
        timestamp=datetime.now(),
        related_entities=entities or ["fund:110011"],
        claim=claim,
        value=overrides.pop("value", {"title": claim}),
        confidence_weight=confidence,
        direction=direction,
        provenance={"source": "finnhub"},
        **overrides,  # type: ignore[arg-type]
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Basic CRUD, filtering, and counting
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphBasic:
    """Core CRUD: add, get, add_edge, filtering (by_entity, by_type), counts."""

    def test_add_item(self):
        """Adding an item stores it in the graph."""
        graph = EvidenceGraph()
        item = _make_hard("ev-001")
        graph.add(item)
        assert "ev-001" in graph.items
        assert graph.items["ev-001"] is item

    def test_add_returns_id(self):
        """add() returns the evidence_id."""
        graph = EvidenceGraph()
        item = _make_hard("ev-001")
        result = graph.add(item)
        assert result == "ev-001"

    def test_add_overwrites_existing(self):
        """Adding an item with the same ID overwrites the old one."""
        graph = EvidenceGraph()
        first = _make_hard("ev-001", claim="first", value=1)
        second = _make_hard("ev-001", claim="second", value=2)
        graph.add(first)
        graph.add(second)
        assert graph.items["ev-001"].claim == "second"
        assert graph.items["ev-001"].value == 2

    def test_get_existing(self):
        """get() returns the item when it exists."""
        graph = EvidenceGraph()
        item = _make_hard("ev-001")
        graph.add(item)
        assert graph.get("ev-001") is item

    def test_get_missing(self):
        """get() returns None when the ID does not exist."""
        graph = EvidenceGraph()
        assert graph.get("nonexistent") is None

    def test_add_edge(self):
        """add_edge stores a (from_id, to_id, edge_type) tuple."""
        graph = EvidenceGraph()
        graph.add_edge("ev-001", "ev-002")
        assert len(graph.edges) == 1
        assert graph.edges[0] == ("ev-001", "ev-002", "supports")

    def test_add_edge_multiple(self):
        """Multiple edges are accumulated."""
        graph = EvidenceGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("a", "c")
        assert len(graph.edges) == 3

    def test_by_entity(self):
        """by_entity returns items matching the given entity."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-001", entities=["fund:110011"]))
        graph.add(_make_hard("ev-002", entities=["fund:110022"]))
        graph.add(_make_soft("ev-003", entities=["fund:110011", "stock:600519"]))

        results = graph.by_entity("fund:110011")
        assert len(results) == 2
        assert {r.evidence_id for r in results} == {"ev-001", "ev-003"}

    def test_by_entity_no_match(self):
        """by_entity returns empty list when no items match."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-001", entities=["fund:110011"]))
        assert graph.by_entity("stock:999999") == []

    def test_by_type_hard(self):
        """by_type filters by evidence type."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-001"))
        graph.add(_make_soft("ev-002"))
        results = graph.by_type("HardEvidence")
        assert len(results) == 1
        assert results[0].evidence_id == "ev-001"

    def test_by_type_soft(self):
        """by_type returns SoftEvidence items."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-001"))
        graph.add(_make_soft("ev-002"))
        graph.add(_make_soft("ev-003"))
        results = graph.by_type("SoftEvidence")
        assert len(results) == 2

    def test_by_type_empty(self):
        """by_type returns empty list when type does not exist."""
        graph = EvidenceGraph()
        assert graph.by_type("HybridEvidence") == []

    def test_hard_evidence_count(self):
        """hard_evidence_count returns accurate count."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-001"))
        graph.add(_make_hard("ev-002"))
        graph.add(_make_soft("ev-003"))
        assert graph.hard_evidence_count() == 2

    def test_soft_evidence_count(self):
        """soft_evidence_count returns accurate count."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-001"))
        graph.add(_make_soft("ev-002"))
        graph.add(_make_soft("ev-003"))
        assert graph.soft_evidence_count() == 2

    def test_hybrid_evidence_count_initial_zero(self):
        """hybrid_evidence_count returns 0 when no HybridEvidence exists."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-001"))
        assert graph.hybrid_evidence_count() == 0


# ═══════════════════════════════════════════════════════════════════════════
#  HybridEvidence upgrade
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphUpgrade:
    """upgrade_to_hybrid: SoftEvidence → HybridEvidence promotion."""

    def test_upgrade_soft_to_hybrid_success(self):
        """Valid upgrade changes type and boosts confidence."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-soft", claim="Market is bullish", confidence=0.5))
        graph.add(_make_hard("ev-hard1"))
        graph.add(_make_hard("ev-hard2"))

        result = graph.upgrade_to_hybrid("ev-soft", ["ev-hard1", "ev-hard2"])
        assert result is not None
        assert result.evidence_id == "ev-soft"
        assert result.evidence_type == "HybridEvidence"

    def test_upgrade_confidence_boost(self):
        """Confidence is boosted by 30%."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-soft", claim="test", confidence=0.5))
        graph.add(_make_hard("ev-hard1"))
        graph.add(_make_hard("ev-hard2"))

        graph.upgrade_to_hybrid("ev-soft", ["ev-hard1", "ev-hard2"])
        item = graph.get("ev-soft")
        assert item is not None
        # 0.5 * 1.3 = 0.65
        assert item.confidence_weight == pytest.approx(0.65)

    def test_upgrade_confidence_capped(self):
        """Confidence boost is capped at 0.95."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-soft", claim="test", confidence=0.8))
        graph.add(_make_hard("ev-hard1"))
        graph.add(_make_hard("ev-hard2"))

        graph.upgrade_to_hybrid("ev-soft", ["ev-hard1", "ev-hard2"])
        item = graph.get("ev-soft")
        assert item is not None
        # 0.8 * 1.3 = 1.04, capped at 0.95
        assert item.confidence_weight == pytest.approx(0.95)

    def test_upgrade_not_soft_returns_none(self):
        """Non-SoftEvidence items cannot be upgraded."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-hard1"))
        graph.add(_make_hard("ev-hard2"))
        graph.add(_make_hard("ev-hard-target"))

        result = graph.upgrade_to_hybrid("ev-hard-target", ["ev-hard1", "ev-hard2"])
        assert result is None
        # Type unchanged
        item = graph.get("ev-hard-target")
        assert item is not None
        assert item.evidence_type == "HardEvidence"

    def test_upgrade_with_one_supporting_id(self):
        """One supporting ID provides 2-source corroboration and upgrades."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-soft", claim="test"))
        graph.add(_make_hard("ev-hard1"))

        result = graph.upgrade_to_hybrid("ev-soft", ["ev-hard1"])
        assert result is not None
        assert result.evidence_type == "HybridEvidence"

    def test_upgrade_empty_supporting_list(self):
        """Empty supporting list prevents upgrade."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-soft", claim="test"))

        result = graph.upgrade_to_hybrid("ev-soft", [])
        assert result is None

    def test_upgrade_missing_supporting_id(self):
        """Missing supporting ID in the graph prevents upgrade."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-soft", claim="test"))
        graph.add(_make_hard("ev-hard1"))
        # ev-hard2 does not exist

        result = graph.upgrade_to_hybrid("ev-soft", ["ev-hard1", "ev-nonexistent"])
        assert result is None

    def test_upgrade_soft_id_not_found(self):
        """Nonexistent soft_id returns None."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-hard1"))
        graph.add(_make_hard("ev-hard2"))

        result = graph.upgrade_to_hybrid("ev-nonexistent", ["ev-hard1", "ev-hard2"])
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
#  Deduplication
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphDedup:
    """deduplicate: near-duplicate claim detection and removal."""

    def test_dedup_identical_claims_same_entities(self):
        """Identical claims on same entities — one is removed."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-a", claim="Fund is performing well", confidence=0.7))
        graph.add(_make_soft("ev-b", claim="Fund is performing well", confidence=0.5))

        removed = graph.deduplicate()
        assert len(removed) == 1
        # Only 1 item remains
        assert len(graph.items) == 1

    def test_dedup_higher_confidence_kept(self):
        """The item with higher confidence survives."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-high", claim="Identical claim", confidence=0.9))
        graph.add(_make_soft("ev-low", claim="Identical claim", confidence=0.3))

        removed = graph.deduplicate()
        assert "ev-low" in removed
        assert "ev-high" in graph.items
        assert "ev-low" not in graph.items

    def test_dedup_keeps_remaining_item(self):
        """After dedup, the surviving item is the one with higher confidence."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-a", claim="Same claim text", confidence=0.6))
        graph.add(_make_soft("ev-b", claim="Same claim text", confidence=0.9))

        removed = graph.deduplicate()
        assert "ev-a" in removed
        surviving = graph.get("ev-b")
        assert surviving is not None
        assert surviving.confidence_weight == 0.9

    def test_dedup_equal_confidence_keeps_first(self):
        """When confidence is equal, the earlier-added (first) item survives."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-first", claim="Duplicate text", confidence=0.7))
        graph.add(_make_soft("ev-second", claim="Duplicate text", confidence=0.7))

        removed = graph.deduplicate()
        assert "ev-second" in removed  # equal → later is removed
        assert "ev-first" in graph.items

    def test_dedup_different_claims_preserved(self):
        """Different claims on same entities are not deduped."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-a", claim="Fund is performing well", entities=["f1"]))
        graph.add(_make_soft("ev-b", claim="Fund has high risk", entities=["f1"]))

        removed = graph.deduplicate()
        assert removed == []
        assert len(graph.items) == 2

    def test_dedup_different_entities(self):
        """Same claim on different entities is NOT deduped."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-a", claim="Positive outlook", entities=["fund:110011"]))
        graph.add(_make_soft("ev-b", claim="Positive outlook", entities=["fund:110022"]))

        removed = graph.deduplicate()
        assert removed == []
        assert len(graph.items) == 2

    def test_dedup_empty_claims(self):
        """Empty claims produce 0 similarity — not deduped."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-a", claim="", entities=["f1"]))
        graph.add(_make_soft("ev-b", claim="", entities=["f1"]))

        removed = graph.deduplicate()
        assert removed == []

    def test_dedup_no_duplicates(self):
        """No duplicates returns empty list."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1", claim="Alpha is positive"))
        graph.add(_make_soft("ev-2", claim="Beta is negative"))
        graph.add(_make_soft("ev-3", claim="Sortino is strong"))

        removed = graph.deduplicate()
        assert removed == []
        assert len(graph.items) == 3

    def test_dedup_partial_word_overlap_below_threshold(self):
        """Low word overlap (< 0.85) is NOT deduped."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-a", claim="Fund performance is strong and growing", entities=["f1"]))
        graph.add(_make_soft("ev-b", claim="Manager has changed investment strategy", entities=["f1"]))

        removed = graph.deduplicate()
        assert removed == []

    def test_dedup_multiple_duplicates(self):
        """Multiple duplicate pairs are all resolved."""
        graph = EvidenceGraph()
        # Pair 1: same claim on "f1"
        graph.add(_make_soft("ev-a1", claim="Bullish on f1", entities=["f1"], confidence=0.8))
        graph.add(_make_soft("ev-a2", claim="Bullish on f1", entities=["f1"], confidence=0.5))
        # Pair 2: same claim on "f2"
        graph.add(_make_soft("ev-b1", claim="Bearish on f2", entities=["f2"], confidence=0.6))
        graph.add(_make_soft("ev-b2", claim="Bearish on f2", entities=["f2"], confidence=0.9))

        removed = graph.deduplicate()
        assert len(removed) == 2
        assert len(graph.items) == 2


# ═══════════════════════════════════════════════════════════════════════════
#  Conflict detection
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphConflicts:
    """detect_conflicts: opposite-direction evidence on shared entities."""

    def test_conflict_positive_vs_negative(self):
        """Positive vs negative on same entity is a conflict."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-pos", claim="Bullish", direction="positive"))
        graph.add(_make_soft("ev-neg", claim="Bearish", direction="negative"))

        conflicts = graph.detect_conflicts()
        assert len(conflicts) == 1
        assert ("ev-pos", "ev-neg") in conflicts or ("ev-neg", "ev-pos") in conflicts

    def test_conflict_same_direction_no_conflict(self):
        """Same direction on shared entity is NOT a conflict."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-a", claim="Bullish", direction="positive"))
        graph.add(_make_soft("ev-b", claim="Very bullish", direction="positive"))

        conflicts = graph.detect_conflicts()
        assert conflicts == []

    def test_conflict_different_entities_no_conflict(self):
        """Different entities, even with opposite directions, is NOT a conflict."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-a", claim="A good", entities=["fund:A"], direction="positive"))
        graph.add(_make_hard("ev-b", claim="B bad", entities=["fund:B"], direction="negative"))

        conflicts = graph.detect_conflicts()
        assert conflicts == []

    def test_conflict_neutral_no_conflict(self):
        """Neutral direction does not conflict with anything."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-neutral", claim="Neutral fact", direction="neutral"))
        graph.add(_make_soft("ev-pos", claim="Bullish", direction="positive"))

        conflicts = graph.detect_conflicts()
        assert conflicts == []

    def test_conflict_empty_graph(self):
        """Empty graph has no conflicts."""
        graph = EvidenceGraph()
        assert graph.detect_conflicts() == []

    def test_conflict_multiple_shared_entities(self):
        """Conflict detected when items share any entity and differ in direction."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-pos", claim="Positive", entities=["fund:A", "fund:B"], direction="positive"))
        graph.add(_make_soft("ev-neg", claim="Negative", entities=["fund:B", "fund:C"], direction="negative"))

        conflicts = graph.detect_conflicts()
        # They share "fund:B" and have opposite directions → conflict
        assert len(conflicts) == 1

    def test_conflict_three_way(self):
        """Multiple conflicting pairs are all detected."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-p1", claim="Good", direction="positive"))
        graph.add(_make_soft("ev-n1", claim="Bad", direction="negative"))
        graph.add(_make_soft("ev-p2", claim="Great", direction="positive"))

        # All 3 share "fund:110011" by default
        # ev-p1 vs ev-n1 = conflict, ev-p2 vs ev-n1 = conflict, ev-p1 vs ev-p2 = no conflict
        conflicts = graph.detect_conflicts()
        assert len(conflicts) == 2


# ═══════════════════════════════════════════════════════════════════════════
#  Aggregation
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphAggregation:
    """aggregate_confidence: weighted-average confidence per entity."""

    def test_aggregate_confidence_basic(self):
        """Average confidence for a single entity is computed correctly."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1", entities=["fund:A"]))
        graph.add(_make_soft("ev-2", entities=["fund:A"], confidence=0.5))

        conf = graph.aggregate_confidence("fund:A")
        # (1.0 + 0.5) / 2 = 0.75
        assert conf == pytest.approx(0.75)

    def test_aggregate_confidence_single_item(self):
        """Single item returns its confidence."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1", entities=["fund:A"]))
        assert graph.aggregate_confidence("fund:A") == 1.0

    def test_aggregate_confidence_no_evidence(self):
        """No evidence for entity returns 0.0."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1", entities=["fund:A"]))
        assert graph.aggregate_confidence("fund:B") == 0.0

    def test_aggregate_confidence_empty_graph(self):
        """Empty graph returns 0.0."""
        graph = EvidenceGraph()
        assert graph.aggregate_confidence("anything") == 0.0

    def test_aggregate_confidence_mixed_entities(self):
        """Only items matching the entity contribute to its aggregate."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-a1", entities=["fund:A"]))
        graph.add(_make_soft("ev-a2", entities=["fund:A", "fund:B"], confidence=0.6))
        graph.add(_make_hard("ev-b1", entities=["fund:B"]))

        # fund:A: (1.0 + 0.6) / 2 = 0.8
        assert graph.aggregate_confidence("fund:A") == pytest.approx(0.8)
        # fund:B: (0.6 + 1.0) / 2 = 0.8
        assert graph.aggregate_confidence("fund:B") == pytest.approx(0.8)


# ═══════════════════════════════════════════════════════════════════════════
#  Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphValidation:
    """validate: integrity checks on the graph."""

    def test_valid_graph_returns_empty(self):
        """A healthy graph produces no issues."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1"))
        graph.add(_make_soft("ev-2"))
        assert graph.validate() == []

    def test_hard_evidence_wrong_confidence(self):
        """HardEvidence with confidence != 1.0 is flagged."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-ok"))
        # Create a valid HardEvidence then mutate to bypass __post_init__
        ev_bad = _make_hard("ev-bad", claim="bad hard")
        object.__setattr__(ev_bad, "confidence_weight", 0.7)
        graph.add(ev_bad)
        issues = graph.validate()
        assert len(issues) == 1
        assert "ev-bad" in issues[0]
        assert "1.0" in issues[0]

    def test_negative_confidence_flagged(self):
        """Negative confidence is flagged."""
        graph = EvidenceGraph()
        # Create valid item then mutate confidence to bypass __post_init__
        ev_bad = _make_soft("ev-bad", claim="negative conf")
        object.__setattr__(ev_bad, "confidence_weight", -0.1)
        graph.add(ev_bad)
        issues = graph.validate()
        assert len(issues) == 1
        assert "invalid confidence" in issues[0]

    def test_confidence_over_one_flagged(self):
        """Confidence > 1.0 is flagged."""
        graph = EvidenceGraph()
        # Create valid item then mutate confidence to bypass __post_init__
        ev_bad = _make_soft("ev-bad", claim="over conf")
        object.__setattr__(ev_bad, "confidence_weight", 1.5)
        graph.add(ev_bad)
        issues = graph.validate()
        assert len(issues) == 1
        assert "invalid confidence" in issues[0]

    def test_validation_multiple_issues(self):
        """Multiple validation issues are all reported."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-good"))
        # Create valid items then mutate to bypass __post_init__
        ev_bad_hard = _make_hard("ev-bad-hard", claim="bad hard", entities=["fund:X"])
        object.__setattr__(ev_bad_hard, "confidence_weight", 0.5)
        graph.add(ev_bad_hard)
        ev_neg = _make_soft("ev-negative", claim="negative", entities=["fund:Y"])
        object.__setattr__(ev_neg, "confidence_weight", -0.2)
        graph.add(ev_neg)
        issues = graph.validate()
        assert len(issues) == 2


# ═══════════════════════════════════════════════════════════════════════════
#  Claim similarity (internal)
# ═══════════════════════════════════════════════════════════════════════════

class TestClaimSimilarity:
    """_claim_similarity: word-overlap computation."""

    def test_identical_claims(self):
        """Identical claims have similarity 1.0."""
        sim = EvidenceGraph._claim_similarity("the fund is strong", "the fund is strong")
        assert sim == pytest.approx(1.0)

    def test_partial_overlap(self):
        """Partial word overlap returns correct ratio."""
        sim = EvidenceGraph._claim_similarity("fund is strong", "fund is weak")
        # words_a = {fund, is, strong}, words_b = {fund, is, weak}
        # intersection = {fund, is} -> 2 / min(3, 3) = 0.666...
        assert sim == pytest.approx(2.0 / 3.0)

    def test_no_overlap(self):
        """No shared words returns 0.0."""
        sim = EvidenceGraph._claim_similarity("aaaa bbbb", "cccc dddd")
        assert sim == pytest.approx(0.0)

    def test_first_claim_empty(self):
        """Empty first claim returns 0.0."""
        sim = EvidenceGraph._claim_similarity("", "something")
        assert sim == pytest.approx(0.0)

    def test_second_claim_empty(self):
        """Empty second claim returns 0.0."""
        sim = EvidenceGraph._claim_similarity("something", "")
        assert sim == pytest.approx(0.0)

    def test_both_claims_empty(self):
        """Both claims empty returns 0.0."""
        sim = EvidenceGraph._claim_similarity("", "")
        assert sim == pytest.approx(0.0)

    def test_case_insensitive(self):
        """Similarity is case-insensitive."""
        sim = EvidenceGraph._claim_similarity("FUND IS STRONG", "fund is strong")
        assert sim == pytest.approx(1.0)

    def test_one_word_each_identical(self):
        """Single-word identical claims."""
        sim = EvidenceGraph._claim_similarity("bullish", "bullish")
        assert sim == pytest.approx(1.0)

    def test_one_word_each_different(self):
        """Single-word different claims."""
        sim = EvidenceGraph._claim_similarity("bullish", "bearish")
        assert sim == pytest.approx(0.0)

    def test_subset_words(self):
        """One claim is a subset of the other."""
        sim = EvidenceGraph._claim_similarity("fund strong", "fund is very strong")
        # intersection = {fund, strong} -> 2 / min(2, 4) = 1.0
        assert sim == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════════════════
#  Serialization
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphSerialization:
    """to_dict: JSON-compatible serialization."""

    def test_to_dict_structure(self):
        """to_dict contains items, edges, and stats keys."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1"))
        graph.add(_make_soft("ev-2"))
        graph.add_edge("ev-1", "ev-2")

        d = graph.to_dict()
        assert "items" in d
        assert "edges" in d
        assert "stats" in d
        assert d["edges"] == [["ev-1", "ev-2", "supports"]]

    def test_to_dict_items(self):
        """to_dict items are serialized via EvidenceItem.to_dict."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1", claim="Test claim"))
        d = graph.to_dict()
        ev_dict = d["items"]["ev-1"]
        assert ev_dict["evidence_type"] == "HardEvidence"
        assert ev_dict["claim"] == "Test claim"
        assert isinstance(ev_dict["timestamp"], str)

    def test_to_dict_stats(self):
        """to_dict stats are computed correctly."""
        graph = EvidenceGraph()
        graph.add(_make_hard("ev-1"))
        graph.add(_make_hard("ev-2"))
        graph.add(_make_soft("ev-3"))
        graph.add_edge("ev-1", "ev-3")

        d = graph.to_dict()
        stats = d["stats"]
        assert stats["total"] == 3
        assert stats["hard"] == 2
        assert stats["soft"] == 1
        assert stats["hybrid"] == 0
        assert stats["conflicts"] == 0  # All neutral

    def test_to_dict_empty(self):
        """Empty graph serializes correctly."""
        graph = EvidenceGraph()
        d = graph.to_dict()
        assert d["items"] == {}
        assert d["edges"] == []
        assert d["stats"]["total"] == 0

    def test_to_dict_hybrid_count_in_stats(self):
        """HybridEvidence count appears in stats."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-soft", claim="upgrade me"))
        graph.add(_make_hard("ev-h1"))
        graph.add(_make_hard("ev-h2"))
        graph.upgrade_to_hybrid("ev-soft", ["ev-h1", "ev-h2"])

        d = graph.to_dict()
        assert d["stats"]["hybrid"] == 1
        assert d["stats"]["soft"] == 0
        assert d["stats"]["hard"] == 2

    def test_evidence_graph_to_dict_is_pure(self):
        """to_dict must not mutate graph edges by detecting conflicts."""
        graph = EvidenceGraph()
        graph.add(_make_soft("ev-pos", claim="Bullish", direction="positive"))
        graph.add(_make_soft("ev-neg", claim="Bearish", direction="negative"))

        before_edges = list(graph.edges)
        d = graph.to_dict()

        assert graph.edges == before_edges
        assert d["stats"]["conflicts"] == 1


# ═══════════════════════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceGraphEdgeCases:
    """Edge cases and resilience."""

    def test_empty_graph_operations(self):
        """Operations on empty graph do not crash."""
        graph = EvidenceGraph()
        assert graph.get("x") is None
        assert graph.by_entity("x") == []
        assert graph.detect_conflicts() == []
        assert graph.deduplicate() == []
        assert graph.validate() == []
        assert graph.aggregate_confidence("x") == 0.0

    def test_add_none_item_raises(self):
        """Adding None should raise AttributeError."""
        graph = EvidenceGraph()
        with pytest.raises(AttributeError):
            graph.add(None)  # type: ignore[arg-type]

    def test_ordering_preserved(self):
        """Items maintain insertion ordering (Python 3.7+)."""
        graph = EvidenceGraph()
        ids = ["ev-c", "ev-a", "ev-b"]
        for eid in ids:
            graph.add(_make_hard(eid))
        assert list(graph.items.keys()) == ids
