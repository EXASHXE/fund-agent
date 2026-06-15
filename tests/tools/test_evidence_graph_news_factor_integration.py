"""Tests for evidence graph integration with news/factor/provider snapshots."""

from __future__ import annotations

from src.schemas.evidence import EvidenceItem
from src.tools.evidence.validators import compile_evidence_graph


def _make_evidence(
    evidence_id: str = "ev_001",
    source_type: str = "quant_tool",
    related_entities: list[str] | None = None,
    evidence_type: str = "HardEvidence",
    confidence_weight: float | None = None,
) -> EvidenceItem:
    """Create an EvidenceItem for testing.

    For SoftEvidence, pass confidence_weight explicitly in [0.1, 0.9].
    For HardEvidence, confidence_weight defaults to 1.0.
    """
    if confidence_weight is None:
        confidence_weight = 1.0 if evidence_type == "HardEvidence" else 0.5
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_type=source_type,
        timestamp="2024-01-01T00:00:00Z",
        related_entities=related_entities or ["fund:000001"],
        claim="Test claim",
        value={"test": True},
        confidence_weight=confidence_weight,
    )


class TestNewsSnapshotEvidence:
    """Tests for evidence items sourced from news snapshots."""

    def test_news_snapshot_source_type_accepted(self):
        ev = _make_evidence(source_type="news_snapshot", evidence_type="SoftEvidence")
        assert ev.source_type == "news_snapshot"
        assert ev.evidence_type == "SoftEvidence"

    def test_news_snapshot_evidence_in_graph(self):
        items = [
            _make_evidence(
                evidence_id="news_001",
                source_type="news_snapshot",
                evidence_type="SoftEvidence",
                related_entities=["fund:000001", "sector:semiconductor"],
            ),
            _make_evidence(
                evidence_id="news_002",
                source_type="news_snapshot",
                evidence_type="SoftEvidence",
                related_entities=["sector:CPO"],
            ),
        ]
        result = compile_evidence_graph(items)
        assert len(result.graph.items) == 2
        assert all(item.source_type == "news_snapshot" for item in result.graph.items.values())

    def test_news_snapshot_confidence_is_soft(self):
        ev = _make_evidence(source_type="news_snapshot", evidence_type="SoftEvidence")
        # SoftEvidence confidence is clamped to [0.1, 0.9] by factory;
        # direct construction with _make_evidence defaults to 0.5 for SoftEvidence
        assert 0.1 <= ev.confidence_weight <= 0.9


class TestFactorSnapshotEvidence:
    """Tests for evidence items sourced from factor snapshots."""

    def test_factor_snapshot_source_type_accepted(self):
        ev = _make_evidence(source_type="factor_snapshot")
        assert ev.source_type == "factor_snapshot"

    def test_factor_snapshot_evidence_in_graph(self):
        items = [
            _make_evidence(
                evidence_id="factor_001",
                source_type="factor_snapshot",
                related_entities=["fund:000001"],
            ),
        ]
        result = compile_evidence_graph(items)
        assert len(result.graph.items) == 1
        assert list(result.graph.items.values())[0].source_type == "factor_snapshot"


class TestProviderSnapshotEvidence:
    """Tests for evidence items sourced from provider snapshots."""

    def test_provider_snapshot_source_type_accepted(self):
        ev = _make_evidence(source_type="provider_snapshot")
        assert ev.source_type == "provider_snapshot"


class TestManualTransactionEvidence:
    """Tests for evidence items sourced from manual transactions."""

    def test_manual_transaction_source_type_accepted(self):
        ev = _make_evidence(source_type="manual_transaction", evidence_type="SoftEvidence")
        assert ev.source_type == "manual_transaction"


class TestPortfolioSnapshotEvidence:
    """Tests for evidence items sourced from portfolio snapshots."""

    def test_portfolio_snapshot_source_type_accepted(self):
        ev = _make_evidence(source_type="portfolio_snapshot")
        assert ev.source_type == "portfolio_snapshot"


class TestMixedSourceEvidenceGraph:
    """Tests for evidence graph with mixed snapshot and traditional sources."""

    def test_mixed_sources_in_graph(self):
        items = [
            _make_evidence(evidence_id="hard_001", source_type="quant_tool"),
            _make_evidence(
                evidence_id="news_001",
                source_type="news_snapshot",
                evidence_type="SoftEvidence",
            ),
            _make_evidence(
                evidence_id="factor_001",
                source_type="factor_snapshot",
            ),
            _make_evidence(
                evidence_id="provider_001",
                source_type="provider_snapshot",
            ),
        ]
        result = compile_evidence_graph(items)
        assert len(result.graph.items) == 4
        source_types = {item.source_type for item in result.graph.items.values()}
        assert source_types == {"quant_tool", "news_snapshot", "factor_snapshot", "provider_snapshot"}

    def test_hard_and_soft_evidence_coexist(self):
        items = [
            _make_evidence(evidence_id="hard_001", source_type="quant_tool", evidence_type="HardEvidence"),
            _make_evidence(
                evidence_id="soft_001",
                source_type="news_snapshot",
                evidence_type="SoftEvidence",
            ),
        ]
        result = compile_evidence_graph(items)
        hard_items = [i for i in result.graph.items.values() if i.evidence_type == "HardEvidence"]
        soft_items = [i for i in result.graph.items.values() if i.evidence_type == "SoftEvidence"]
        assert len(hard_items) == 1
        assert len(soft_items) == 1
