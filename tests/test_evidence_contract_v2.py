"""Tests for evidence-contract.v2 — EvidenceItem schema contract.

Verifies the schema-level constraints defined in evidence-contract.v2:
- HardEvidence confidence_weight must be 1.0
- to_dict serialization roundtrip
- SoftEvidence confidence in [0.1, 0.9]
- Empty related_entities rejected
- Provenance preserved through serialization
- Version field is "evidence-contract.v2"
"""

from __future__ import annotations

from datetime import datetime

import pytest
from src.schemas.evidence import EvidenceItem


class TestContractHardEvidence:
    """evidence-contract.v2 — HardEvidence constraints."""

    def test_confidence_always_one(self):
        """HardEvidence confidence_weight must always be 1.0 (contract rule)."""
        evidence = EvidenceItem(
            evidence_id="contract-hard-1",
            evidence_type="HardEvidence",
            source_type="sharpe_calculator",
            timestamp=datetime.now(),
            related_entities=["fund:110011"],
            claim="Sharpe ratio is 2.1",
            value=2.1,
        )
        assert evidence.confidence_weight == 1.0
        assert evidence.evidence_type == "HardEvidence"

    def test_confidence_one_enforced_at_construction(self):
        """Setting HardEvidence confidence != 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="HardEvidence confidence_weight"):
            EvidenceItem(
                evidence_id="contract-hard-bad",
                evidence_type="HardEvidence",
                source_type="calc",
                timestamp=datetime.now(),
                related_entities=["fund:110011"],
                claim="test",
                value=1.0,
                confidence_weight=0.9,  # Must be 1.0
            )

    def test_from_tool_output_sets_confidence_one(self):
        """from_tool_output factory ensures confidence=1.0."""
        evidence = EvidenceItem.from_tool_output(
            tool_name="alpha_calc",
            output=0.05,
            claim="Alpha is 5%",
            entities=["fund:110011"],
        )
        assert evidence.confidence_weight == 1.0
        assert evidence.evidence_type == "HardEvidence"


class TestContractSerialization:
    """evidence-contract.v2 — to_dict serialization."""

    def test_to_dict_contains_all_required_fields(self):
        """to_dict output includes all contract fields."""
        evidence = EvidenceItem.from_tool_output(
            tool_name="sortino",
            output=1.5,
            claim="Sortino ratio",
            entities=["fund:110011", "stock:600519"],
            direction="positive",
            provenance={"method": "daily_returns"},
        )
        d = evidence.to_dict()
        assert "evidence_id" in d
        assert "evidence_type" in d
        assert "source_type" in d
        assert "timestamp" in d
        assert "related_entities" in d
        assert "claim" in d
        assert "value" in d
        assert "confidence_weight" in d
        assert "direction" in d
        assert "version" in d
        assert "provenance" in d

    def test_timestamp_isoformat(self):
        """Timestamp is serialized as ISO 8601 string."""
        evidence = EvidenceItem(
            evidence_id="ser-ts",
            evidence_type="HardEvidence",
            source_type="test",
            timestamp=datetime(2026, 5, 29, 10, 0, 0),
            related_entities=["fund:110011"],
            claim="test",
            value=1.0,
        )
        d = evidence.to_dict()
        assert d["timestamp"] == "2026-05-29T10:00:00"
        assert isinstance(d["timestamp"], str)

    def test_provenance_preserved(self):
        """Provenance dict is preserved through serialization."""
        provenance = {"source": "tavily", "query": "AI funds", "confidence": "high"}
        evidence = EvidenceItem.from_tool_output(
            tool_name="test",
            output={},
            claim="test",
            entities=["f1"],
            provenance=provenance,
        )
        d = evidence.to_dict()
        assert d["provenance"] == provenance


class TestContractSoftEvidence:
    """evidence-contract.v2 — SoftEvidence constraints."""

    def test_confidence_in_range(self):
        """SoftEvidence confidence_weight is always in [0.1, 0.9]."""
        evidence = EvidenceItem.from_news(
            source="finnhub",
            news_item={"title": "Market update"},
            entities=["fund:110011"],
            confidence=0.75,
        )
        assert 0.1 <= evidence.confidence_weight <= 0.9

    def test_confidence_clamped_low(self):
        """Confidence below 0.1 is clamped to 0.1."""
        evidence = EvidenceItem.from_news(
            source="test",
            news_item={"title": "t"},
            entities=["f1"],
            confidence=0.0,
        )
        assert evidence.confidence_weight == 0.1

    def test_confidence_clamped_high(self):
        """Confidence above 0.9 is clamped to 0.9."""
        evidence = EvidenceItem.from_news(
            source="test",
            news_item={"title": "t"},
            entities=["f1"],
            confidence=1.0,
        )
        assert evidence.confidence_weight == 0.9


class TestContractValidation:
    """evidence-contract.v2 — field validation."""

    def test_empty_entities_rejected(self):
        """Empty related_entities list raises ValueError."""
        with pytest.raises(ValueError, match="related_entities"):
            EvidenceItem(
                evidence_id="empty-entities",
                evidence_type="HardEvidence",
                source_type="calc",
                timestamp=datetime.now(),
                related_entities=[],
                claim="test",
                value=1.0,
            )

    def test_empty_source_type_rejected(self):
        """Empty source_type raises ValueError."""
        with pytest.raises(ValueError, match="source_type"):
            EvidenceItem(
                evidence_id="empty-source",
                evidence_type="HardEvidence",
                source_type="",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim="test",
                value=1.0,
            )

    def test_negative_confidence_rejected(self):
        """Negative confidence_weight raises ValueError."""
        with pytest.raises(ValueError, match="confidence_weight"):
            EvidenceItem(
                evidence_id="neg-conf",
                evidence_type="SoftEvidence",
                source_type="news",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim="test",
                value={},
                confidence_weight=-0.5,
            )


class TestContractVersion:
    """evidence-contract.v2 — version field."""

    def test_version_is_v2(self):
        """Default version is evidence-contract.v2."""
        evidence = EvidenceItem.from_tool_output(
            tool_name="test", output=1.0, claim="test", entities=["f1"]
        )
        assert evidence.version == "evidence-contract.v2"

    def test_version_in_serialization(self):
        """Version field appears in to_dict output."""
        evidence = EvidenceItem.from_tool_output(
            tool_name="test", output=1.0, claim="test", entities=["f1"]
        )
        d = evidence.to_dict()
        assert d["version"] == "evidence-contract.v2"


class TestContractEdgeCases:
    """evidence-contract.v2 — edge cases and boundary conditions."""

    def test_hybrid_evidence_accepts_range(self):
        """HybridEvidence accepts any confidence in [0.0, 1.0]."""
        for conf in [0.0, 0.3, 0.7, 1.0]:
            evidence = EvidenceItem(
                evidence_id=f"hybrid-{conf}",
                evidence_type="HybridEvidence",
                source_type="combined",
                timestamp=datetime.now(),
                related_entities=["f1"],
                claim="test",
                value={},
                confidence_weight=conf,
            )
            assert evidence.confidence_weight == conf

    def test_from_news_sets_version_v2(self):
        """from_news factory sets version to evidence-contract.v2."""
        evidence = EvidenceItem.from_news(
            source="test",
            news_item={"title": "t"},
            entities=["f1"],
        )
        assert evidence.version == "evidence-contract.v2"
