"""Tests for EvidenceGraph compiler — builders and validators.

Tests the public API in src/tools/evidence/builders.py and
src/tools/evidence/validators.py.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from src.schemas.evidence import EvidenceItem
from src.tools.evidence.builders import (
    build_hard_evidence,
    build_hybrid_evidence,
    build_soft_evidence,
)
from src.tools.evidence.validators import (
    EvidenceGraphCompileReport,
    EvidenceGraphCompileResult,
    aggregate_confidence,
    compile_evidence_graph,
    deduplicate_evidence,
    detect_conflicts,
    validate_evidence,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Builder tests
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildHardEvidence:
    """build_hard_evidence — HardEvidence construction."""

    def test_confidence_always_one(self):
        """HardEvidence always has confidence_weight == 1.0."""
        item = build_hard_evidence(
            tool_name="sortino_tool",
            output=1.5,
            claim="Sortino ratio is 1.5",
            entities=["fund:110011"],
        )
        assert item.evidence_type == "HardEvidence"
        assert item.confidence_weight == 1.0

    def test_fields_populated(self):
        """All required fields are populated correctly."""
        item = build_hard_evidence(
            tool_name="xirr_calc",
            output=0.12,
            claim="XIRR is 12%",
            entities=["fund:110011", "fund:110022"],
            direction="positive",
            provenance={"method": "daily_nav"},
        )
        assert item.source_type == "xirr_calc"
        assert item.claim == "XIRR is 12%"
        assert item.related_entities == ["fund:110011", "fund:110022"]
        assert item.direction == "positive"
        assert item.provenance == {"method": "daily_nav"}
        assert isinstance(item.timestamp, datetime)
        assert bool(item.evidence_id)  # non-empty uuid

    def test_default_direction_neutral(self):
        """Default direction is neutral."""
        item = build_hard_evidence(
            tool_name="test", output={}, claim="test", entities=["f1"]
        )
        assert item.direction == "neutral"

    def test_default_provenance_empty(self):
        """Default provenance is empty dict."""
        item = build_hard_evidence(
            tool_name="test", output={}, claim="test", entities=["f1"]
        )
        assert item.provenance == {}


class TestBuildSoftEvidence:
    """build_soft_evidence — SoftEvidence construction."""

    def test_clamps_low_confidence(self):
        """Confidence below 0.1 is clamped to 0.1."""
        item = build_soft_evidence(
            source="finnhub",
            claim="Market is down",
            entities=["fund:110011"],
            confidence=0.0,
        )
        assert item.evidence_type == "SoftEvidence"
        assert item.confidence_weight == 0.1

    def test_clamps_high_confidence(self):
        """Confidence above 0.9 is clamped to 0.9."""
        item = build_soft_evidence(
            source="finnhub",
            claim="Strong rally",
            entities=["fund:110011"],
            confidence=1.0,
        )
        assert item.confidence_weight == 0.9

    def test_default_confidence(self):
        """Default confidence is 0.5."""
        item = build_soft_evidence(
            source="tavily",
            claim="Neutral news",
            entities=["fund:110011"],
        )
        assert item.confidence_weight == 0.5

    def test_sets_source_type(self):
        """Source type is set from the source parameter."""
        item = build_soft_evidence(
            source="akshare",
            claim="Test",
            entities=["stock:600519"],
        )
        assert item.source_type == "akshare"

    def test_preserves_claim(self):
        """Claim is passed through correctly."""
        item = build_soft_evidence(
            source="test",
            claim="AI sector growth accelerating",
            entities=["industry:AI"],
        )
        assert item.claim == "AI sector growth accelerating"


class TestBuildHybridEvidence:
    """build_hybrid_evidence — HybridEvidence construction."""

    def test_three_sources_upgraded(self):
        """3+ soft items are upgraded to HybridEvidence (needs 2+ supporting)."""
        soft1 = build_soft_evidence("src1", "Bullish signal", ["f1"], confidence=0.5)
        soft2 = build_soft_evidence("src2", "Bullish signal", ["f1"], confidence=0.6)
        soft3 = build_soft_evidence("src3", "Bullish signal", ["f1"], confidence=0.7)
        hybrid = build_hybrid_evidence([soft1, soft2, soft3])
        assert hybrid is not None
        assert hybrid.evidence_type == "HybridEvidence"

    def test_confidence_increased(self):
        """Hybrid confidence is boosted above the original single source."""
        soft1 = build_soft_evidence("src1", "Momentum positive", ["f1"], confidence=0.5)
        soft2 = build_soft_evidence("src2", "Momentum positive", ["f1"], confidence=0.6)
        soft3 = build_soft_evidence("src3", "Momentum positive", ["f1"], confidence=0.7)
        hybrid = build_hybrid_evidence([soft1, soft2, soft3])
        assert hybrid is not None
        # Original confidence 0.5 * 1.3 = 0.65
        assert hybrid.confidence_weight > 0.5

    def test_single_source_returns_original(self):
        """Single source returns the item unchanged (no upgrade)."""
        soft = build_soft_evidence("src1", "Standalone", ["f1"])
        result = build_hybrid_evidence([soft])
        assert result is soft  # same object
        assert result.evidence_type == "SoftEvidence"

    def test_empty_list_returns_none(self):
        """Empty list returns None."""
        result = build_hybrid_evidence([])
        assert result is None

    def test_confidence_capped_at_095(self):
        """Hybrid confidence boost is capped at 0.95."""
        soft1 = build_soft_evidence("src1", "High conf", ["f1"], confidence=0.8)
        soft2 = build_soft_evidence("src2", "High conf", ["f1"], confidence=0.9)
        soft3 = build_soft_evidence("src3", "High conf", ["f1"], confidence=0.9)
        hybrid = build_hybrid_evidence([soft1, soft2, soft3])
        assert hybrid is not None
        # 0.8 * 1.3 = 1.04, capped at 0.95
        assert hybrid.confidence_weight == pytest.approx(0.95)


# ═══════════════════════════════════════════════════════════════════════════
#  Validator tests
# ═══════════════════════════════════════════════════════════════════════════

class TestValidateEvidence:
    """validate_evidence — per-item validation."""

    @staticmethod
    def _make_valid_hard() -> EvidenceItem:
        """Create a valid HardEvidence item."""
        return EvidenceItem(
            evidence_id="test-valid",
            evidence_type="HardEvidence",
            source_type="test_tool",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="valid",
            value=1.0,
        )

    def test_valid_item_returns_empty(self):
        """A valid hard evidence item produces no errors."""
        item = self._make_valid_hard()
        errors = validate_evidence(item)
        assert errors == []

    def test_valid_soft_returns_empty(self):
        """A valid soft evidence item produces no errors."""
        item = EvidenceItem(
            evidence_id="soft-valid",
            evidence_type="SoftEvidence",
            source_type="finnhub",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="soft valid",
            value={},
            confidence_weight=0.5,
        )
        errors = validate_evidence(item)
        assert errors == []

    def test_rejects_missing_source(self):
        """Missing source_type returns a validation error."""
        item = self._make_valid_hard()
        object.__setattr__(item, "source_type", "")
        errors = validate_evidence(item)
        assert "Missing source_type" in errors

    def test_rejects_missing_timestamp(self):
        """Missing timestamp returns a validation error."""
        item = self._make_valid_hard()
        object.__setattr__(item, "timestamp", None)
        errors = validate_evidence(item)
        assert "Missing timestamp" in errors

    def test_rejects_missing_entities(self):
        """Empty related_entities returns a validation error."""
        item = self._make_valid_hard()
        object.__setattr__(item, "related_entities", [])
        errors = validate_evidence(item)
        assert "Missing related_entities" in errors

    def test_rejects_hard_evidence_bad_confidence(self):
        """HardEvidence with confidence != 1.0 is flagged."""
        item = self._make_valid_hard()
        object.__setattr__(item, "confidence_weight", 0.5)
        errors = validate_evidence(item)
        assert any("1.0" in e for e in errors)

    def test_rejects_soft_confidence_below_01(self):
        """SoftEvidence with confidence < 0.1 is flagged."""
        item = EvidenceItem(
            evidence_id="soft-bad",
            evidence_type="SoftEvidence",
            source_type="finnhub",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="bad",
            value={},
            confidence_weight=0.5,
        )
        object.__setattr__(item, "confidence_weight", 0.05)
        errors = validate_evidence(item)
        assert any("0.1" in e for e in errors)

    def test_rejects_hybrid_confidence_below_01(self):
        """HybridEvidence with confidence < 0.1 is flagged."""
        item = EvidenceItem(
            evidence_id="hybrid-bad",
            evidence_type="HybridEvidence",
            source_type="hybrid",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="bad",
            value={},
            confidence_weight=0.5,
        )
        object.__setattr__(item, "confidence_weight", 0.05)
        errors = validate_evidence(item)
        assert any("0.1" in e for e in errors)


class TestDeduplicateEvidence:
    """deduplicate_evidence — near-duplicate removal."""

    def test_removes_duplicates(self):
        """Near-duplicate claims on same entities are deduplicated."""
        item_a = EvidenceItem(
            evidence_id="ev-a",
            evidence_type="SoftEvidence",
            source_type="news",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="Fund is performing well",
            value={},
            confidence_weight=0.7,
        )
        item_b = EvidenceItem(
            evidence_id="ev-b",
            evidence_type="SoftEvidence",
            source_type="news",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="Fund is performing well",
            value={},
            confidence_weight=0.5,
        )
        result = deduplicate_evidence([item_a, item_b])
        assert len(result) == 1

    def test_preserves_unique_items(self):
        """Non-duplicate items are preserved."""
        item_a = EvidenceItem(
            evidence_id="ev-a",
            evidence_type="SoftEvidence",
            source_type="news",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="Fund is performing well",
            value={},
            confidence_weight=0.5,
        )
        item_b = EvidenceItem(
            evidence_id="ev-b",
            evidence_type="SoftEvidence",
            source_type="news",
            timestamp=datetime.now(),
            related_entities=["f2"],
            claim="Different fund",
            value={},
            confidence_weight=0.5,
        )
        result = deduplicate_evidence([item_a, item_b])
        assert len(result) == 2

    def test_empty_list(self):
        """Empty list returns empty list."""
        assert deduplicate_evidence([]) == []


class TestDetectConflicts:
    """detect_conflicts — opposite-direction detection."""

    def test_opposite_directions_detected(self):
        """Opposite directions on shared entity produces a conflict."""
        pos = EvidenceItem(
            evidence_id="ev-pos",
            evidence_type="SoftEvidence",
            source_type="news",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="Bullish",
            value={},
            direction="positive",
        )
        neg = EvidenceItem(
            evidence_id="ev-neg",
            evidence_type="SoftEvidence",
            source_type="news",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="Bearish",
            value={},
            direction="negative",
        )
        conflicts = detect_conflicts([pos, neg])
        assert len(conflicts) == 1
        assert conflicts[0][2] == "contradiction"

    def test_same_direction_no_conflict(self):
        """Same direction on shared entity is not a conflict."""
        items = [
            EvidenceItem(
                evidence_id=f"ev-{i}",
                evidence_type="SoftEvidence",
                source_type="news",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim=f"Claim {i}",
                value={},
                direction="positive",
            )
            for i in range(2)
        ]
        assert detect_conflicts(items) == []

    def test_empty_list(self):
        """Empty list returns empty list."""
        assert detect_conflicts([]) == []


class TestAggregateConfidence:
    """aggregate_confidence — average confidence calculation."""

    def test_average_confidence(self):
        """Average confidence is computed correctly."""
        items = [
            EvidenceItem(
                evidence_id=f"ev-{i}",
                evidence_type="HardEvidence" if i == 0 else "SoftEvidence",
                source_type="test",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim="test",
                value={},
                confidence_weight=conf,
            )
            for i, conf in enumerate([1.0, 0.5, 0.8])
        ]
        result = aggregate_confidence(items)
        assert result == pytest.approx((1.0 + 0.5 + 0.8) / 3)

    def test_single_item(self):
        """Single item returns its own confidence."""
        items = [
            EvidenceItem(
                evidence_id="ev-1",
                evidence_type="HardEvidence",
                source_type="test",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim="test",
                value=1.0,
            )
        ]
        assert aggregate_confidence(items) == 1.0

    def test_empty_list(self):
        """Empty list returns 0.0."""
        assert aggregate_confidence([]) == 0.0


class TestCompileEvidenceGraph:
    """compile_evidence_graph — graph assembly."""

    def test_compiles_items_into_graph(self):
        """Items are compiled into an EvidenceGraph."""
        items = [
            EvidenceItem(
                evidence_id="ev-1",
                evidence_type="HardEvidence",
                source_type="tool_a",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim="First evidence",
                value=1.0,
            ),
            EvidenceItem(
                evidence_id="ev-2",
                evidence_type="SoftEvidence",
                source_type="news",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim="Second evidence",
                value={},
                confidence_weight=0.5,
            ),
        ]
        result = compile_evidence_graph(items)
        graph = result.graph
        assert isinstance(result, EvidenceGraphCompileResult)
        assert isinstance(result.report, EvidenceGraphCompileReport)
        assert len(graph.items) == 2
        assert graph.get("ev-1") is not None
        assert graph.get("ev-2") is not None

    def test_empty_input(self):
        """Empty list produces empty graph."""
        result = compile_evidence_graph([])
        graph = result.graph
        assert len(graph.items) == 0
        assert graph.edges == []

    def test_compile_rejects_invalid_evidence(self):
        """Invalid evidence is rejected before graph assembly."""
        valid = EvidenceItem(
            evidence_id="ev-valid",
            evidence_type="HardEvidence",
            source_type="tool_a",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="Valid evidence",
            value=1.0,
        )
        invalid = EvidenceItem(
            evidence_id="ev-invalid",
            evidence_type="HardEvidence",
            source_type="tool_b",
            timestamp=datetime.now(),
            related_entities=["f1"],
            claim="Invalid evidence",
            value=1.0,
        )
        object.__setattr__(invalid, "confidence_weight", 0.5)

        result = compile_evidence_graph([valid, invalid])
        report = result.report

        assert isinstance(report, EvidenceGraphCompileReport)
        assert report.rejected_count == 1
        assert report.accepted_count == 1
        assert "ev-valid" in result.graph.items
        assert "ev-invalid" not in result.graph.items
        assert report.rejected_items[0]["evidence_id"] == "ev-invalid"

    def test_compile_rejects_missing_source_type(self):
        """Missing source_type is rejected by the compiler."""
        item = _make_soft("ev-missing-source")
        object.__setattr__(item, "source_type", "")

        result = compile_evidence_graph([item])

        assert result.report.rejected_count == 1
        assert result.report.rejected_items[0]["evidence_id"] == "ev-missing-source"
        assert "ev-missing-source" not in result.graph.items

    def test_compile_rejects_missing_timestamp(self):
        """Missing timestamp is rejected by the compiler."""
        item = _make_soft("ev-missing-timestamp")
        object.__setattr__(item, "timestamp", None)

        result = compile_evidence_graph([item])

        assert result.report.rejected_count == 1
        assert any("timestamp" in error for error in result.report.rejected_items[0]["errors"])
        assert result.graph.items == {}

    def test_compile_rejects_empty_related_entities(self):
        """Empty related_entities is rejected by the compiler."""
        item = _make_soft("ev-empty-entities")
        object.__setattr__(item, "related_entities", [])

        result = compile_evidence_graph([item])

        assert result.report.rejected_count == 1
        assert any("related_entities" in error for error in result.report.rejected_items[0]["errors"])
        assert result.graph.items == {}

    def test_compile_rejects_bad_hard_evidence_confidence(self):
        """HardEvidence with confidence != 1.0 is rejected."""
        item = _make_hard("ev-bad-hard")
        object.__setattr__(item, "confidence_weight", 0.7)

        result = compile_evidence_graph([item])

        assert result.report.rejected_count == 1
        assert any("1.0" in error for error in result.report.rejected_items[0]["errors"])
        assert result.graph.items == {}

    def test_compile_deduplicates_claims(self):
        """Same claim + related_entities + source_type is deduplicated."""
        item_a = _make_soft(
            "ev-dup-a",
            claim="Fund risk is improving",
            source_type="news",
            confidence=0.5,
        )
        item_b = _make_soft(
            "ev-dup-b",
            claim="Fund risk is improving",
            source_type="news",
            confidence=0.8,
        )

        result = compile_evidence_graph([item_a, item_b])

        assert result.report.deduplicated_count == 1
        assert result.report.accepted_count == 1
        assert "ev-dup-b" in result.graph.items
        assert "ev-dup-a" not in result.graph.items

    def test_compile_detects_conflicts(self):
        """Opposite directions on the same entity produce a conflict."""
        positive = _make_soft("ev-pos", direction="positive")
        negative = _make_soft("ev-neg", direction="negative")

        result = compile_evidence_graph([positive, negative])

        assert result.report.conflict_count == 1
        assert result.report.conflicts == [("ev-pos", "ev-neg")]
        assert ("ev-pos", "ev-neg", "contradicts") in result.graph.edges

    def test_compile_upgrades_soft_to_hybrid_only_with_multi_source_support(self):
        """Only 2+ independent source_type values may upgrade SoftEvidence."""
        same_source_a = _make_soft("same-a", source_type="news_a", direction="positive")
        same_source_b = _make_soft("same-b", source_type="news_a", direction="positive")

        single_source = compile_evidence_graph([same_source_a, same_source_b])

        assert single_source.report.hybrid_upgraded_count == 0
        assert all(
            item.evidence_type == "SoftEvidence"
            for item in single_source.graph.items.values()
        )

        multi_source_a = _make_soft("multi-a", source_type="news_a", direction="positive")
        multi_source_b = _make_soft("multi-b", source_type="news_b", direction="positive")

        multi_source = compile_evidence_graph([multi_source_a, multi_source_b])

        assert multi_source.report.hybrid_upgraded_count == 1
        assert multi_source.graph.get("multi-a").evidence_type == "HybridEvidence"
        assert multi_source.graph.get("multi-b").evidence_type == "SoftEvidence"

    def test_compile_report_is_json_serializable(self):
        """EvidenceGraphCompileReport must be JSON serializable."""
        result = compile_evidence_graph([
            _make_soft("ev-json-a", source_type="news_a", direction="positive"),
            _make_soft("ev-json-b", source_type="news_b", direction="positive"),
        ])

        json.dumps(result.report.to_dict())


def _make_hard(
    evidence_id: str,
    claim: str = "Hard evidence",
    entities: list[str] | None = None,
    direction: str = "neutral",
    source_type: str = "quant_tool",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type="HardEvidence",
        source_type=source_type,
        timestamp=datetime.now(),
        related_entities=entities or ["fund:110011"],
        claim=claim,
        value=1.0,
        direction=direction,
    )


def _make_soft(
    evidence_id: str,
    claim: str = "Soft evidence",
    entities: list[str] | None = None,
    direction: str = "neutral",
    source_type: str = "news",
    confidence: float = 0.5,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type="SoftEvidence",
        source_type=source_type,
        timestamp=datetime.now(),
        related_entities=entities or ["fund:110011"],
        claim=claim,
        value={},
        confidence_weight=confidence,
        direction=direction,
        provenance={"source": source_type},
    )
