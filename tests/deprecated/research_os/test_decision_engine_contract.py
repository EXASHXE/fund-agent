"""Contract hardening tests for DecisionEngine and Decision."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.core.critic import CritiqueResult
from src.core.decision_engine import DecisionEngine
from src.core.ledger import LedgerBuilder
from src.schemas.decision import Decision
from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph


def test_active_decision_requires_real_evidence_anchor():
    """Active engine decisions must anchor to an EvidenceGraph evidence_id."""
    graph = EvidenceGraph()
    graph.add(_make_hard("ev-positive", direction="positive"))

    decision = DecisionEngine().decide(
        _task(),
        graph,
        CritiqueResult(status="PASS"),
    )

    assert decision.action == "BUY"
    assert decision.rationale_anchor == ["ev-positive"]


def test_fake_rationale_anchor_is_rejected():
    """Known fake anchors must not satisfy the Decision contract."""
    with pytest.raises(ValueError, match="fake placeholders"):
        Decision(
            decision_id="fake-anchor",
            action="BUY",
            execution_amount=1000.0,
            rationale_anchor=["fake-anchor"],
            trigger_conditions=["signal"],
            invalidating_conditions=["invalidated"],
            time_horizon="1 year",
            risk_budget=0.05,
        )


def test_wait_can_have_empty_anchor_with_missing_evidence():
    """WAIT can be anchorless only when insufficient evidence is explicit."""
    decision = Decision(
        decision_id="wait-empty",
        action="WAIT",
        execution_amount=0.0,
        rationale_anchor=[],
        trigger_conditions=["Insufficient evidence to support an active decision"],
        invalidating_conditions=["Risk budget exceeded"],
        time_horizon="1 year",
        risk_budget=0.01,
        audit_trail=["Insufficient evidence: no evidence items available"],
    )

    assert decision.rationale_anchor == []


def test_exhausted_critique_allows_only_passive_actions():
    """EXHAUSTED critique must downgrade any active signal to a passive action."""
    graph = EvidenceGraph()
    graph.add(_make_hard("ev-positive", direction="positive"))

    decision = DecisionEngine().decide(
        _task(),
        graph,
        CritiqueResult(status="EXHAUSTED", issues=["missing risk"]),
    )

    assert decision.action in {"WAIT", "HOLD", "PAUSE_DCA"}
    assert decision.execution_amount == 0.0
    assert any("Blocked by critic" in item for item in decision.audit_trail)


def test_no_no_evidence_available_placeholder():
    """Empty evidence must not generate the old fake no_evidence_available anchor."""
    decision = DecisionEngine().decide(
        _task(),
        EvidenceGraph(),
        CritiqueResult(status="EXHAUSTED", issues=["missing evidence"]),
    )

    assert "no_evidence_available" not in decision.rationale_anchor
    assert decision.rationale_anchor == []
    assert any("Insufficient evidence" in item for item in decision.audit_trail)


def test_decision_is_json_serializable():
    """Decision.to_dict output must be JSON serializable."""
    decision = DecisionEngine().decide(
        _task(),
        EvidenceGraph(),
        CritiqueResult(status="EXHAUSTED", issues=["missing evidence"]),
    )

    json.dumps(decision.to_dict())


def test_execution_ledger_contains_audit_fields():
    """ExecutionLedger exposes decision audit fields and evidence ids."""
    graph = EvidenceGraph()
    graph.add(_make_hard("ev-positive", direction="positive"))
    decision = DecisionEngine().decide(
        _task(),
        graph,
        CritiqueResult(status="PASS"),
    )

    ledger = LedgerBuilder().build(decision, graph)
    payload = ledger.to_dict()
    first = payload["decisions"][0]

    assert payload["ledger_id"] == ledger.ledger_id
    assert first["decision_id"] == decision.decision_id
    assert first["evidence_ids"] == ["ev-positive"]
    assert first["audit_trail"]
    assert first["created_at"]
    json.dumps(payload)


def _task():
    return SimpleNamespace(
        risk_profile="moderate",
        time_horizon="1 year",
        constraints={},
    )


def _make_hard(evidence_id: str, direction: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_type="HardEvidence",
        source_type="quant_tool",
        timestamp=datetime.now(),
        related_entities=["fund:110011"],
        claim=f"{direction} quant signal",
        value={"score": 1.0},
        confidence_weight=1.0,
        direction=direction,
        provenance={"source": "quant_tool"},
    )
