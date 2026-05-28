"""Tests for the EvidenceItem schema (evidence-contract.v2)."""

from __future__ import annotations

import pytest
from datetime import datetime
from src.schemas.evidence import EvidenceItem


class TestEvidenceItemValidation:
    """Tests for EvidenceItem validation constraints."""

    def test_hard_evidence_confidence_must_be_1(self):
        """HardEvidence with confidence_weight != 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="HardEvidence confidence_weight"):
            EvidenceItem(
                evidence_id="test-1",
                evidence_type="HardEvidence",
                source_type="sortino_tool",
                timestamp=datetime.now(),
                related_entities=["fund:110011"],
                claim="Sortino ratio is 1.5",
                value=1.5,
                confidence_weight=0.8,  # Should fail
            )

    def test_hard_evidence_default_confidence_is_1(self):
        """HardEvidence with default confidence should work."""
        evidence = EvidenceItem(
            evidence_id="test-1",
            evidence_type="HardEvidence",
            source_type="sortino_tool",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="Sortino ratio is 1.5",
            value=1.5,
        )
        assert evidence.confidence_weight == 1.0

    def test_empty_source_type_raises(self):
        """Empty source_type should raise ValueError."""
        with pytest.raises(ValueError, match="source_type"):
            EvidenceItem(
                evidence_id="test-1",
                evidence_type="HardEvidence",
                source_type="",  # Empty
                timestamp=datetime.now(),
                related_entities=["fund:110011"],
                claim="test",
                value=1.0,
            )

    def test_empty_related_entities_raises(self):
        """Empty related_entities should raise ValueError."""
        with pytest.raises(ValueError, match="related_entities"):
            EvidenceItem(
                evidence_id="test-1",
                evidence_type="HardEvidence",
                source_type="sortino",
                timestamp=datetime.now(),
                related_entities=[],  # Empty
                claim="test",
                value=1.0,
            )

    def test_invalid_confidence_weight_raises(self):
        """Confidence weight > 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="confidence_weight"):
            EvidenceItem(
                evidence_id="test-1",
                evidence_type="SoftEvidence",
                source_type="finnhub",
                timestamp=datetime.now(),
                related_entities=["fund:110011"],
                claim="test",
                value={"title": "test"},
                confidence_weight=1.5,  # > 1.0
            )

    def test_negative_confidence_weight_raises(self):
        """Negative confidence weight should raise ValueError."""
        with pytest.raises(ValueError, match="confidence_weight"):
            EvidenceItem(
                evidence_id="test-1",
                evidence_type="SoftEvidence",
                source_type="finnhub",
                timestamp=datetime.now(),
                related_entities=["fund:110011"],
                claim="test",
                value={"title": "test"},
                confidence_weight=-0.1,  # < 0.0
            )

    def test_hybrid_evidence_allows_custom_confidence(self):
        """HybridEvidence allows any confidence_weight in [0.0, 1.0]."""
        evidence = EvidenceItem(
            evidence_id="test-1",
            evidence_type="HybridEvidence",
            source_type="combined_analysis",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="Hybrid analysis",
            value={},
            confidence_weight=0.75,
        )
        assert evidence.confidence_weight == 0.75
        assert evidence.evidence_type == "HybridEvidence"


class TestEvidenceItemFactories:
    """Tests for EvidenceItem factory methods."""

    def test_from_tool_output_creates_hard_evidence(self):
        """from_tool_output should create HardEvidence with confidence 1.0."""
        evidence = EvidenceItem.from_tool_output(
            tool_name="sortino_tool",
            output=1.5,
            claim="Sortino ratio",
            entities=["fund:110011"],
            direction="positive",
        )
        assert evidence.evidence_type == "HardEvidence"
        assert evidence.confidence_weight == 1.0
        assert evidence.source_type == "sortino_tool"
        assert evidence.direction == "positive"
        assert evidence.version == "evidence-contract.v2"

    def test_from_tool_output_generates_id_and_timestamp(self):
        """from_tool_output should auto-generate id and timestamp."""
        evidence = EvidenceItem.from_tool_output(
            tool_name="xirr_calc",
            output=0.12,
            claim="XIRR is 12%",
            entities=["fund:110011"],
        )
        assert evidence.evidence_id
        assert isinstance(evidence.timestamp, datetime)

    def test_from_news_creates_soft_evidence(self):
        """from_news should create SoftEvidence with clamped confidence."""
        evidence = EvidenceItem.from_news(
            source="finnhub",
            news_item={"title": "Market rally continues"},
            entities=["fund:110011"],
            direction="positive",
            confidence=0.7,
        )
        assert evidence.evidence_type == "SoftEvidence"
        assert 0.1 <= evidence.confidence_weight <= 0.9
        assert evidence.source_type == "finnhub"
        assert evidence.provenance == {"source": "finnhub"}

    def test_from_news_extracts_title_as_claim(self):
        """from_news should use title from news_item as claim."""
        evidence = EvidenceItem.from_news(
            source="finnhub",
            news_item={"title": "Bullish signal detected"},
            entities=["fund:110011"],
        )
        assert evidence.claim == "Bullish signal detected"

    def test_from_news_falls_back_to_claim_key(self):
        """from_news should fall back to 'claim' key if 'title' is missing."""
        evidence = EvidenceItem.from_news(
            source="finnhub",
            news_item={"claim": "Earnings beat estimates"},
            entities=["fund:110011"],
        )
        assert evidence.claim == "Earnings beat estimates"

    def test_from_news_empty_claim(self):
        """from_news with no title or claim should produce empty string."""
        evidence = EvidenceItem.from_news(
            source="finnhub",
            news_item={"other": "data"},
            entities=["fund:110011"],
        )
        assert evidence.claim == ""

    def test_soft_evidence_confidence_clamped_low(self):
        """from_news should clamp confidence to min 0.1."""
        evidence = EvidenceItem.from_news(
            source="test",
            news_item={"title": "t"},
            entities=["f1"],
            confidence=0.0,
        )
        assert evidence.confidence_weight == 0.1

    def test_soft_evidence_confidence_clamped_high(self):
        """from_news should clamp confidence to max 0.9."""
        evidence = EvidenceItem.from_news(
            source="test",
            news_item={"title": "t"},
            entities=["f1"],
            confidence=1.0,
        )
        assert evidence.confidence_weight == 0.9

    def test_from_news_default_confidence(self):
        """from_news should default confidence to 0.5."""
        evidence = EvidenceItem.from_news(
            source="test",
            news_item={"title": "t"},
            entities=["f1"],
        )
        assert evidence.confidence_weight == 0.5


class TestEvidenceItemSerialization:
    """Tests for EvidenceItem serialization."""

    def test_to_dict_serialization(self):
        """to_dict should produce a JSON-compatible dict."""
        evidence = EvidenceItem.from_tool_output(
            "sortino", 1.5, "test", ["fund:1"]
        )
        d = evidence.to_dict()
        assert d["evidence_type"] == "HardEvidence"
        assert d["confidence_weight"] == 1.0
        assert isinstance(d["timestamp"], str)
        assert d["version"] == "evidence-contract.v2"
        assert d["claim"] == "test"
        assert d["related_entities"] == ["fund:1"]

    def test_to_dict_includes_all_fields(self):
        """to_dict should include all EvidenceItem fields."""
        evidence = EvidenceItem(
            evidence_id="custom-id",
            evidence_type="SoftEvidence",
            source_type="tavily",
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            related_entities=["fund:110011", "stock:600519"],
            claim="AI sector is growing",
            value={"summary": "AI growth continues"},
            confidence_weight=0.8,
            direction="positive",
            provenance={"source": "tavily", "query": "AI funds"},
        )
        d = evidence.to_dict()
        assert d["evidence_id"] == "custom-id"
        assert d["evidence_type"] == "SoftEvidence"
        assert d["source_type"] == "tavily"
        assert d["timestamp"] == "2025-01-15T10:30:00"
        assert d["related_entities"] == ["fund:110011", "stock:600519"]
        assert d["claim"] == "AI sector is growing"
        assert d["direction"] == "positive"
        assert d["provenance"] == {"source": "tavily", "query": "AI funds"}

    def test_to_dict_related_entities_preserved(self):
        """to_dict should preserve related_entities as-is."""
        entities = ["fund:110011", "stock:600519", "industry:AI"]
        evidence = EvidenceItem.from_tool_output(
            "test_tool", 42, "test", entities
        )
        d = evidence.to_dict()
        assert d["related_entities"] == entities


class TestEvidenceItemEdgeCases:
    """Edge case tests for EvidenceItem."""

    def test_minimal_hard_evidence(self):
        """Creating HardEvidence with only required fields should work."""
        evidence = EvidenceItem(
            evidence_id="minimal",
            evidence_type="HardEvidence",
            source_type="calc",
            timestamp=datetime.now(),
            related_entities=["fund:1"],
            claim="minimal",
            value=None,
        )
        assert evidence.value is None
        assert evidence.direction == "neutral"
        assert evidence.provenance == {}

    def test_soft_evidence_with_complex_value(self):
        """SoftEvidence value can hold complex dict structures."""
        complex_news = {
            "title": "Rate decision",
            "source": "Reuters",
            "sentiment": -0.3,
            "entities": ["Fed", "interest rates"],
            "url": "https://example.com/news/1",
        }
        evidence = EvidenceItem.from_news(
            source="finnhub",
            news_item=complex_news,
            entities=["fund:110011"],
            direction="negative",
            confidence=0.6,
        )
        assert evidence.value == complex_news
        assert evidence.direction == "negative"

    def test_multiple_entities(self):
        """related_entities can contain multiple entity types."""
        evidence = EvidenceItem.from_tool_output(
            tool_name="correlation_matrix",
            output={"fund_a": 0.8, "fund_b": 0.6},
            claim="Correlation between funds",
            entities=["fund:110011", "fund:110022", "fund:110033"],
            provenance={"method": "pearson"},
        )
        assert len(evidence.related_entities) == 3
        assert "fund:110011" in evidence.related_entities

    def test_provenance_default_empty_dict(self):
        """Provenance should default to empty dict when not provided."""
        evidence = EvidenceItem(
            evidence_id="no-provenance",
            evidence_type="HardEvidence",
            source_type="calc",
            timestamp=datetime.now(),
            related_entities=["fund:1"],
            claim="no provenance",
            value=1,
        )
        assert evidence.provenance == {}

    def test_version_default(self):
        """Version should default to evidence-contract.v2."""
        evidence = EvidenceItem(
            evidence_id="version-test",
            evidence_type="HardEvidence",
            source_type="calc",
            timestamp=datetime.now(),
            related_entities=["fund:1"],
            claim="test",
            value=1,
        )
        assert evidence.version == "evidence-contract.v2"
