"""Tests for evidence_anchor_diagnostics in decision_support."""
from __future__ import annotations

import pytest

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.skills_runtime.decision_support.anchor_diagnostics import build_evidence_anchor_diagnostics


def _make_evidence(evidence_id: str, direction: str = "positive") -> EvidenceItem:
    from datetime import datetime
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type="HardEvidence",
        source_type="quant_tool",
        timestamp=datetime.now(),
        related_entities=["fund:110011"],
        claim=f"Test claim {evidence_id}",
        value=1.0,
        confidence_weight=1.0,
        direction=direction,
        provenance={},
    )


class TestEvidenceAnchorDiagnostics:
    def test_active_buy_with_valid_anchors(self):
        graph = EvidenceGraph()
        graph.add(_make_evidence("ev1"))
        graph.add(_make_evidence("ev2"))

        result = build_evidence_anchor_diagnostics(
            action="BUY",
            evidence_graph=graph,
            rationale_anchor=["ev1", "ev2"],
        )
        assert result["active_action_requires_anchor"] is True
        assert result["anchor_count"] == 2
        assert len(result["valid_anchor_refs"]) == 2
        assert len(result["invalid_anchor_refs"]) == 0
        assert len(result["missing_anchor_refs"]) == 0

    def test_active_buy_with_invalid_evidence_ref(self):
        graph = EvidenceGraph()
        graph.add(_make_evidence("ev1"))

        result = build_evidence_anchor_diagnostics(
            action="BUY",
            evidence_graph=graph,
            rationale_anchor=["ev1", "ev_missing"],
        )
        assert "ev1" in result["valid_anchor_refs"]
        assert "ev_missing" in result["invalid_anchor_refs"]

    def test_active_buy_with_no_anchors(self):
        graph = EvidenceGraph()
        graph.add(_make_evidence("ev1"))

        result = build_evidence_anchor_diagnostics(
            action="BUY",
            evidence_graph=graph,
            rationale_anchor=[],
        )
        assert result["active_action_requires_anchor"] is True
        assert len(result["missing_anchor_refs"]) >= 1

    def test_passive_hold_with_no_anchors(self):
        graph = EvidenceGraph()
        result = build_evidence_anchor_diagnostics(
            action="HOLD",
            evidence_graph=graph,
            rationale_anchor=[],
        )
        assert result["active_action_requires_anchor"] is False
        assert "passive" in result["limitations"][0].lower() or "no anchors" in result["limitations"][0].lower()

    def test_trade_anchor_coverage(self):
        graph = EvidenceGraph()
        graph.add(_make_evidence("ev1"))
        graph.add(_make_evidence("ev2"))

        trade_plan = [
            {"trade_id": "T1", "action": "BUY", "evidence_refs": ["ev1", "ev2"], "risk_flags_refs": []},
            {"trade_id": "T2", "action": "BUY", "evidence_refs": ["ev_missing"], "risk_flags_refs": []},
            {"trade_id": "T3", "action": "HOLD", "evidence_refs": [], "risk_flags_refs": []},
        ]

        result = build_evidence_anchor_diagnostics(
            action="BUY",
            evidence_graph=graph,
            rationale_anchor=["ev1"],
            trade_plan=trade_plan,
        )
        assert len(result["trade_anchor_coverage"]) == 3
        t1 = result["trade_anchor_coverage"][0]
        assert t1["coverage"] == "full"
        t2 = result["trade_anchor_coverage"][1]
        assert t2["coverage"] == "none"
        t3 = result["trade_anchor_coverage"][2]
        assert t3["required"] is False

    def test_anchor_entity_mismatch_detected(self):
        graph = EvidenceGraph()
        item = EvidenceItem(
            evidence_id="ev_no_entities",
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=__import__("datetime").datetime.now(),
            related_entities=["fund:110011"],
            claim="Has entities but testing mismatch",
            value=1.0,
            confidence_weight=1.0,
            provenance={},
        )
        graph.add(item)

        result = build_evidence_anchor_diagnostics(
            action="HOLD",
            evidence_graph=graph,
            rationale_anchor=["ev_no_entities"],
        )
        assert result["anchor_count"] == 1
        assert "ev_no_entities" in result["valid_anchor_refs"]
