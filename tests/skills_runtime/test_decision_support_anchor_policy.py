"""Tests for decision_support evidence anchor policy."""

import pytest

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.skills_runtime.decision_support.anchor_diagnostics import build_evidence_anchor_diagnostics


def _make_graph(n_items: int = 3) -> EvidenceGraph:
    items = {}
    for i in range(n_items):
        item = EvidenceItem(
            evidence_id=f"ev-{i}",
            evidence_type="HardEvidence",
            source_type="fund_analysis",
            timestamp="2026-01-01T00:00:00",
            related_entities=[f"fund:{i:06d}"],
            claim=f"Test claim {i}",
            value=1.0,
            confidence_weight=1.0,
            direction="neutral",
        )
        items[item.evidence_id] = item
    return EvidenceGraph(items=items)


class TestEvidenceAnchorDiagnostics:
    def test_returns_dict_with_required_keys(self):
        graph = _make_graph(3)
        result = build_evidence_anchor_diagnostics(
            action="BUY", evidence_graph=graph, rationale_anchor=["ev-0"]
        )
        assert isinstance(result, dict)
        assert "active_action_requires_anchor" in result
        assert "anchor_count" in result

    def test_empty_anchor_list(self):
        graph = _make_graph(3)
        result = build_evidence_anchor_diagnostics(
            action="HOLD", evidence_graph=graph, rationale_anchor=[]
        )
        assert result["anchor_count"] == 0

    def test_valid_anchors(self):
        graph = _make_graph(3)
        result = build_evidence_anchor_diagnostics(
            action="BUY", evidence_graph=graph, rationale_anchor=["ev-0", "ev-1"]
        )
        assert result["anchor_count"] == 2

    def test_active_action_requires_anchor_flag(self):
        graph = _make_graph(1)
        result = build_evidence_anchor_diagnostics(
            action="BUY", evidence_graph=graph, rationale_anchor=[]
        )
        assert result["active_action_requires_anchor"] is True

    def test_passive_action_does_not_require_anchor_flag(self):
        graph = _make_graph(1)
        result = build_evidence_anchor_diagnostics(
            action="HOLD", evidence_graph=graph, rationale_anchor=[]
        )
        assert result["active_action_requires_anchor"] is False

    def test_invalid_anchor_refs(self):
        graph = _make_graph(1)
        result = build_evidence_anchor_diagnostics(
            action="BUY", evidence_graph=graph, rationale_anchor=["nonexistent"]
        )
        assert "nonexistent" in result["invalid_anchor_refs"]

    def test_valid_anchor_refs_populated(self):
        graph = _make_graph(2)
        result = build_evidence_anchor_diagnostics(
            action="BUY", evidence_graph=graph, rationale_anchor=["ev-0"]
        )
        assert "ev-0" in result["valid_anchor_refs"]

    def test_limitations_for_active_action_no_valid_anchors(self):
        graph = _make_graph(1)
        result = build_evidence_anchor_diagnostics(
            action="SELL", evidence_graph=graph, rationale_anchor=[]
        )
        assert any("no valid evidence anchors" in lim.lower() for lim in result["limitations"])
