"""DecisionSupportSkill trade evidence anchoring tests (TASK D)."""

from __future__ import annotations

from datetime import datetime

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill


def _graph_with_evidence(evidence_id: str = "ev-1") -> EvidenceGraph:
    graph = EvidenceGraph()
    graph.add(
        EvidenceItem(
            evidence_id=evidence_id,
            evidence_type="HardEvidence",
            source_type="quant_tool",
            timestamp=datetime.now(),
            related_entities=["fund:TEST001"],
            claim="positive risk adjusted return signal",
            value={"score": 1.0},
            confidence_weight=1.0,
            direction="positive",
            provenance={"tool": "quant_tool"},
        )
    )
    return graph


def _make_input(trade_plan_trades, evidence_graph, **extra):
    payload = {
        "evidence_graph": evidence_graph.to_dict(),
        "objective": "review portfolio",
        "time_horizon": "medium_term",
        "portfolio_context": {"total_value": 100000.0, "cash_available": 25000.0},
        "risk_profile": {"risk_level": "moderate", "max_trade_pct": 0.1, "liquidity_reserve_pct": 0.05},
        "constraints": {"min_trade_amount": 100.0},
        "trade_plan": {"suggested_trade_plan": trade_plan_trades},
        "selected_trade_ids": [t.get("trade_id", "") for t in trade_plan_trades],
        **extra,
    }
    return SkillInput(
        task_id="test",
        step_id="ds",
        skill_name="decision_support",
        payload=payload,
    )


def test_active_buy_with_trade_evidence_refs_succeeds():
    graph = _graph_with_evidence("ev-1")
    trade = {
        "trade_id": "trade-buy-1",
        "fund_code": "TEST001",
        "fund_name": "Test Fund",
        "action": "BUY",
        "amount": 5000.0,
        "rationale": "Positive signal from quant tool",
        "evidence_refs": ["ev-1"],
    }
    output = DecisionSupportSkill().run(_make_input([trade], graph))
    assert output.status == "OK"
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) == 1
    assert decisions[0]["action"] == "BUY"
    assert decisions[0]["execution_amount"] > 0
    assert "ev-1" in decisions[0]["rationale_anchor"]


def test_active_buy_without_trade_specific_evidence_downgrades():
    graph = _graph_with_evidence("ev-1")
    trade = {
        "trade_id": "trade-buy-2",
        "fund_code": "TEST001",
        "fund_name": "Test Fund",
        "action": "BUY",
        "amount": 5000.0,
        "evidence_refs": [],
        "risk_flags_refs": [],
    }
    output = DecisionSupportSkill().run(_make_input([trade], graph))
    assert output.status == "OK"
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) == 1
    assert decisions[0]["action"] in {"HOLD", "WAIT"}
    assert decisions[0]["execution_amount"] == 0.0
    assert any(
        "Insufficient evidence" in item
        for item in decisions[0].get("audit_trail", [])
    )


def test_sell_with_fake_evidence_refs_downgrades():
    graph = _graph_with_evidence("ev-real")
    trade = {
        "trade_id": "trade-sell-fake",
        "fund_code": "TEST001",
        "fund_name": "Test Fund",
        "action": "SELL",
        "amount": 3000.0,
        "current_value": 30000.0,
        "evidence_refs": ["ev-fake-1", "ev-fake-2"],
        "risk_flags_refs": [],
    }
    output = DecisionSupportSkill().run(_make_input([trade], graph))
    assert output.status == "OK"
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) == 1
    assert decisions[0]["action"] in {"HOLD", "WAIT"}
    assert decisions[0]["execution_amount"] == 0.0


def test_hold_explains_missing_evidence():
    graph = EvidenceGraph()
    trade = {
        "trade_id": "trade-hold-1",
        "fund_code": "TEST001",
        "fund_name": "Test Fund",
        "action": "HOLD",
        "amount": 0.0,
        "why_not_buy": "insufficient positive signals",
        "why_not_sell": "no negative signals",
        "missing_evidence": "no evidence items available",
        "evidence_refs": [],
        "risk_flags_refs": [],
    }
    output = DecisionSupportSkill().run(_make_input([trade], graph))
    assert output.status == "OK"
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) == 1
    assert decisions[0]["action"] == "HOLD"
    assert decisions[0]["execution_amount"] == 0.0
    assert any(
        "Missing evidence" in item or "Insufficient evidence" in item
        for item in decisions[0].get("audit_trail", [])
    )


def test_buy_with_valid_risk_flags_refs_succeeds():
    graph = _graph_with_evidence("rf-1")
    trade = {
        "trade_id": "trade-risk-refs",
        "fund_code": "TEST001",
        "fund_name": "Test Fund",
        "action": "BUY",
        "amount": 5000.0,
        "rationale": "Risk flag evidence supports action",
        "evidence_refs": [],
        "risk_flags_refs": ["rf-1"],
    }
    output = DecisionSupportSkill().run(_make_input([trade], graph))
    assert output.status == "OK"
    decisions = output.artifacts.get("decisions", [])
    assert len(decisions) == 1
    assert decisions[0]["action"] == "BUY"
    assert "rf-1" in decisions[0]["rationale_anchor"]
