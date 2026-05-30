"""Purity tests for EvidenceGraph serialization."""

from __future__ import annotations

from datetime import datetime

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


def test_evidence_graph_to_dict_is_pure():
    """to_dict must not mutate graph edges."""
    graph = EvidenceGraph()
    graph.add(_make_soft("ev-pos", direction="positive"))
    graph.add(_make_soft("ev-neg", direction="negative"))

    before_edges = list(graph.edges)
    first = graph.to_dict()
    second = graph.to_dict()

    assert graph.edges == before_edges
    assert first["stats"]["conflicts"] == 1
    assert second["stats"]["conflicts"] == 1


def test_to_dict_does_not_duplicate_conflict_edges():
    """to_dict must not add or duplicate conflict edges."""
    graph = EvidenceGraph()
    graph.add(_make_soft("ev-pos", direction="positive"))
    graph.add(_make_soft("ev-neg", direction="negative"))
    graph.detect_conflicts()

    assert graph.edges == [("ev-pos", "ev-neg", "contradicts")]

    graph.to_dict()
    graph.to_dict()

    assert graph.edges == [("ev-pos", "ev-neg", "contradicts")]


def _make_soft(evidence_id: str, direction: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type="SoftEvidence",
        source_type="news",
        timestamp=datetime.now(),
        related_entities=["fund:110011"],
        claim=f"{direction} outlook",
        value={},
        confidence_weight=0.5,
        direction=direction,
        provenance={"source": "news"},
    )
