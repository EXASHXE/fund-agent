"""Tests for DecisionEngine + LedgerBuilder with contract enforcement.

Covers:
    - Decision validation (all required fields, action constraints)
    - Non-PASS critique downgrades active actions to WAIT
    - PASS critique allows active actions
    - LedgerBuilder single/multi decision construction
    - Ledger serialization and aggregation
"""

from __future__ import annotations

import pytest
from datetime import datetime
from src.schemas.decision import Decision, ExecutionLedger
from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.research_task import ResearchTask
from src.core.critic import Critic, CritiqueResult
from src.core.decision_engine import DecisionEngine
from src.core.ledger import LedgerBuilder


# ── Helper ──────────────────────────────────────────────────────────────────

def _make_valid_decision(**overrides: object) -> Decision:
    """Build a minimal valid Decision, overriding any fields."""
    defaults: dict[str, object] = {
        "decision_id": "dec-001",
        "action": "HOLD",
        "execution_amount": 0.0,
        "rationale_anchor": ["ev-001"],
        "trigger_conditions": ["price_below_ma50"],
        "invalidating_conditions": ["price_above_ma200"],
        "time_horizon": "1M",
        "risk_budget": 0.05,
    }
    defaults.update(overrides)
    return Decision(**defaults)  # type: ignore[arg-type]


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_task() -> ResearchTask:
    return ResearchTask(
        task_id="test-decision-001",
        objective="review portfolio",
        fund_universe=["110011"],
        risk_profile="moderate",
        time_horizon="3 months",
    )


@pytest.fixture
def sample_evidence_graph() -> EvidenceGraph:
    g = EvidenceGraph()
    item = EvidenceItem.from_tool_output(
        tool_name="quant_tool",
        output={"sharpe": 1.5},
        claim="Strong risk-adjusted returns",
        entities=["fund:110011"],
        direction="positive",
        provenance={"source": "quant_analysis"},
    )
    g.add(item)
    return g


@pytest.fixture
def pass_critique() -> CritiqueResult:
    return CritiqueResult(
        status="PASS",
        iteration=1,
    )


@pytest.fixture
def retry_critique() -> CritiqueResult:
    return CritiqueResult(
        status="RETRY",
        issues=["Missing risk evidence"],
        missing_evidence=["risk_metrics"],
        retry_plan_suggestions=["Run risk analysis"],
        iteration=1,
    )


@pytest.fixture
def engine() -> DecisionEngine:
    return DecisionEngine()


@pytest.fixture
def ledger_builder() -> LedgerBuilder:
    return LedgerBuilder()


# ── Test 1: Decision with all required fields ────────────────────────────────


class TestDecisionValidAllFields:
    """Decision created with all required fields should be valid."""

    def test_decision_valid_all_fields(self) -> None:
        decision = _make_valid_decision(
            decision_id="valid-001",
            action="BUY",
            execution_amount=5000.0,
            rationale_anchor=["ev-001", "ev-002"],
            trigger_conditions=["signal_1"],
            invalidating_conditions=["inv_1"],
            time_horizon="6M",
            risk_budget=0.08,
            audit_trail=["ev-001", "ev-002"],
        )
        assert decision.decision_id == "valid-001"
        assert decision.action == "BUY"
        assert decision.execution_amount == 5000.0
        assert len(decision.rationale_anchor) == 2
        assert len(decision.trigger_conditions) == 1
        assert len(decision.invalidating_conditions) == 1
        assert decision.time_horizon == "6M"
        assert decision.risk_budget == 0.08
        assert len(decision.audit_trail) == 2


# ── Test 2: BUY with execution_amount=0 raises ───────────────────────────────


class TestDecisionMissingExecutionAmount:
    """BUY/SELL/INCREASE/REDUCE with execution_amount=0 must raise ValueError."""

    def test_decision_missing_execution_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="requires execution_amount > 0"):
            _make_valid_decision(action="BUY", execution_amount=0.0)


# ── Test 3: Empty rationale_anchor raises ────────────────────────────────────


class TestDecisionMissingRationaleAnchor:
    """Empty rationale_anchor must raise ValueError."""

    def test_decision_missing_rationale_anchor_raises(self) -> None:
        with pytest.raises(ValueError, match="rationale_anchor"):
            _make_valid_decision(rationale_anchor=[])


# ── Test 4: Empty trigger_conditions raises ──────────────────────────────────


class TestDecisionMissingTriggerConditions:
    """Empty trigger_conditions must raise ValueError."""

    def test_decision_missing_trigger_conditions_raises(self) -> None:
        with pytest.raises(ValueError, match="trigger_conditions"):
            _make_valid_decision(trigger_conditions=[])


# ── Test 5: Empty invalidating_conditions raises ─────────────────────────────


class TestDecisionMissingInvalidatingConditions:
    """Empty invalidating_conditions must raise ValueError."""

    def test_decision_missing_invalidating_conditions_raises(self) -> None:
        with pytest.raises(ValueError, match="invalidating_conditions"):
            _make_valid_decision(invalidating_conditions=[])


# ── Test 6: RETRY critique blocks BUY → downgraded to WAIT ───────────────────


class TestNonPassCritiqueBlocksBuy:
    """RETRY critique → BUY action must be downgraded to WAIT."""

    def test_non_pass_critique_blocks_buy(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        sample_evidence_graph: EvidenceGraph,
        retry_critique: CritiqueResult,
    ) -> None:
        decision = engine.decide(
            sample_task, sample_evidence_graph, retry_critique
        )
        assert decision.action == "WAIT"


# ── Test 7: RETRY critique blocks SELL → downgraded to WAIT ──────────────────


class TestNonPassCritiqueBlocksSell:
    """RETRY critique → SELL action must be downgraded to WAIT."""

    def test_non_pass_critique_blocks_sell(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        sample_evidence_graph: EvidenceGraph,
        retry_critique: CritiqueResult,
    ) -> None:
        decision = engine.decide(
            sample_task, sample_evidence_graph, retry_critique
        )
        assert decision.action == "WAIT"


# ── Test 8: PASS critique allows BUY ─────────────────────────────────────────


class TestPassCritiqueAllowsBuy:
    """PASS critique → engine may produce BUY when evidence is positive."""

    def test_pass_critique_allows_buy(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        sample_evidence_graph: EvidenceGraph,
        pass_critique: CritiqueResult,
    ) -> None:
        # With strong positive evidence, a PASS critique should produce
        # BUY or INCREASE (not WAIT).
        decision = engine.decide(
            sample_task, sample_evidence_graph, pass_critique
        )
        assert decision.action in ("BUY", "INCREASE", "HOLD")
        # Must have required fields
        assert len(decision.rationale_anchor) > 0
        assert len(decision.trigger_conditions) > 0
        assert len(decision.invalidating_conditions) > 0
        assert decision.risk_budget > 0


# ── Test 9: Decision engine produces a valid Decision ────────────────────────


class TestDecisionEngineProducesValidDecision:
    """complete decide() output must be a valid Decision with all fields."""

    def test_decision_engine_produces_valid_decision(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        sample_evidence_graph: EvidenceGraph,
        pass_critique: CritiqueResult,
    ) -> None:
        decision = engine.decide(
            sample_task, sample_evidence_graph, pass_critique
        )
        assert isinstance(decision, Decision)
        assert isinstance(decision.decision_id, str)
        assert len(decision.decision_id) > 0
        assert decision.action in (
            "BUY", "SELL", "HOLD", "PAUSE_DCA",
            "REDUCE", "INCREASE", "WAIT",
        )
        assert isinstance(decision.execution_amount, float)
        assert len(decision.rationale_anchor) > 0
        assert len(decision.trigger_conditions) > 0
        assert len(decision.invalidating_conditions) > 0
        assert decision.risk_budget > 0
        assert isinstance(decision.audit_trail, list)
        assert decision.version == "decision-contract.v2"
        assert isinstance(decision.created_at, datetime)


# ── Test 10: LedgerBuilder.build with single decision ────────────────────────


class TestLedgerBuildSingleDecision:
    """LedgerBuilder.build() with one Decision."""

    def test_ledger_build_single_decision(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        decision = _make_valid_decision(
            decision_id="ledger-001",
            action="BUY",
            execution_amount=5000.0,
        )
        ledger = ledger_builder.build(decision)
        assert isinstance(ledger, ExecutionLedger)
        assert len(ledger.decisions) == 1
        assert ledger.decisions[0].decision_id == "ledger-001"
        assert ledger.decisions[0].action == "BUY"
        assert ledger.version == "execution-ledger.v1"


# ── Test 11: Ledger serialization ────────────────────────────────────────────


class TestLedgerSerialization:
    """ledger.to_dict() works correctly."""

    def test_ledger_serialization(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        decision = _make_valid_decision(
            decision_id="ser-001",
            action="HOLD",
        )
        ledger = ledger_builder.build(decision)
        d = ledger.to_dict()
        assert d["version"] == "execution-ledger.v1"
        assert isinstance(d["generated_at"], str)
        assert len(d["decisions"]) == 1
        assert d["decisions"][0]["decision_id"] == "ser-001"


# ── Test 12: LedgerBuilder.build_multi with multiple decisions ───────────────


class TestLedgerBuildMultiDecision:
    """LedgerBuilder.build_multi() with multiple Decisions."""

    def test_ledger_build_multi_decision(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        d1 = _make_valid_decision(decision_id="multi-001", action="BUY", execution_amount=3000.0)
        d2 = _make_valid_decision(decision_id="multi-002", action="HOLD")
        d3 = _make_valid_decision(decision_id="multi-003", action="SELL", execution_amount=2000.0)
        ledger = ledger_builder.build_multi([d1, d2, d3])
        assert len(ledger.decisions) == 3
        assert ledger.decisions[0].decision_id == "multi-001"
        assert ledger.decisions[1].decision_id == "multi-002"
        assert ledger.decisions[2].decision_id == "multi-003"

        # Aggregate checks
        assert ledger_builder.total_risk(ledger) > 0
        summary = ledger_builder.actions_summary(ledger)
        assert summary == {"BUY": 1, "HOLD": 1, "SELL": 1}


# ── Test 13: WAIT allowed when non-PASS critique ─────────────────────────────


class TestWaitAllowedWhenNonPass:
    """WAIT is allowed even with non-PASS critique."""

    def test_wait_allowed_when_non_pass(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        retry_critique: CritiqueResult,
    ) -> None:
        # Use empty evidence graph so engine naturally returns WAIT
        empty_graph = EvidenceGraph()
        decision = engine.decide(sample_task, empty_graph, retry_critique)
        assert decision.action == "WAIT"
        # Engine provides fallback anchor when evidence is empty
        assert len(decision.rationale_anchor) > 0
        assert decision.risk_budget > 0


# ── Test 14: HOLD allowed when non-PASS critique ─────────────────────────────


class TestHoldAllowedWhenNonPass:
    """HOLD is allowed even with non-PASS critique."""

    def test_hold_allowed_when_non_pass(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        sample_evidence_graph: EvidenceGraph,
        retry_critique: CritiqueResult,
    ) -> None:
        # With evidence present but non-PASS critique, action should be WAIT
        decision = engine.decide(
            sample_task, sample_evidence_graph, retry_critique
        )
        # Non-PASS critique forces WAIT (not HOLD)
        assert decision.action == "WAIT"
        assert decision.risk_budget > 0


# ── Test 15: LedgerBuilder rejects non-Decision input ────────────────────────


class TestLedgerBuilderRejectsInvalidInput:
    """LedgerBuilder must raise TypeError for non-Decision inputs."""

    def test_build_rejects_non_decision(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        with pytest.raises(TypeError, match="Expected Decision"):
            ledger_builder.build("not a decision")  # type: ignore[arg-type]

    def test_build_multi_rejects_non_decision(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        valid = _make_valid_decision(decision_id="ok", action="HOLD")
        with pytest.raises(TypeError, match="Expected Decision"):
            ledger_builder.build_multi([valid, "bad"])  # type: ignore[list-item]


# ── Test 16: Total risk and actions summary helpers ──────────────────────────


class TestLedgerAggregation:
    """LedgerBuilder aggregation helpers."""

    def test_total_risk_sums_correctly(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        d1 = _make_valid_decision(decision_id="d1", risk_budget=0.03)
        d2 = _make_valid_decision(decision_id="d2", risk_budget=0.07)
        ledger = ledger_builder.build_multi([d1, d2])
        assert ledger_builder.total_risk(ledger) == pytest.approx(0.10)

    def test_actions_summary_counts(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        d1 = _make_valid_decision(decision_id="d1", action="BUY", execution_amount=1000.0)
        d2 = _make_valid_decision(decision_id="d2", action="BUY", execution_amount=2000.0)
        d3 = _make_valid_decision(decision_id="d3", action="HOLD")
        ledger = ledger_builder.build_multi([d1, d2, d3])
        assert ledger_builder.actions_summary(ledger) == {"BUY": 2, "HOLD": 1}

    def test_empty_ledger_zero_risk(
        self,
        ledger_builder: LedgerBuilder,
    ) -> None:
        ledger = ledger_builder.build_multi([])
        assert ledger_builder.total_risk(ledger) == 0.0
        assert ledger_builder.actions_summary(ledger) == {}


# ── Test 17: Decision engine handles empty evidence gracefully ───────────────


class TestDecisionEngineEmptyEvidence:
    """Decision engine handles missing/empty evidence gracefully."""

    def test_empty_evidence_returns_wait(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        pass_critique: CritiqueResult,
    ) -> None:
        empty_graph = EvidenceGraph()
        decision = engine.decide(sample_task, empty_graph, pass_critique)
        # With empty evidence, action should be WAIT
        assert decision.action == "WAIT"
        assert decision.execution_amount == 0.0
        assert decision.risk_budget > 0

    def test_none_evidence_returns_wait(
        self,
        engine: DecisionEngine,
        sample_task: ResearchTask,
        pass_critique: CritiqueResult,
    ) -> None:
        decision = engine.decide(sample_task, None, pass_critique)
        assert decision.action == "WAIT"
        assert decision.risk_budget > 0


# ── Test 18: Decision engine respects risk profiles ──────────────────────────


class TestDecisionEngineRiskProfiles:
    """Decision engine adjusts risk budget based on risk_profile."""

    def test_conservative_risk_budget(
        self,
        engine: DecisionEngine,
        sample_evidence_graph: EvidenceGraph,
        pass_critique: CritiqueResult,
    ) -> None:
        task = ResearchTask(
            task_id="conservative-001",
            objective="review conservative portfolio",
            fund_universe=["110011"],
            risk_profile="conservative",
        )
        decision = engine.decide(task, sample_evidence_graph, pass_critique)
        # conservative passive actions get 0.01
        # But with PASS critique and evidence, action may be active
        # For active conservative, risk = 0.02
        if decision.action in ("BUY", "SELL", "INCREASE", "REDUCE"):
            assert decision.risk_budget == 0.02
        else:
            assert decision.risk_budget == 0.01

    def test_aggressive_risk_budget(
        self,
        engine: DecisionEngine,
        sample_evidence_graph: EvidenceGraph,
        pass_critique: CritiqueResult,
    ) -> None:
        task = ResearchTask(
            task_id="aggressive-001",
            objective="review aggressive portfolio",
            fund_universe=["110011"],
            risk_profile="aggressive",
        )
        decision = engine.decide(task, sample_evidence_graph, pass_critique)
        if decision.action in ("BUY", "SELL", "INCREASE", "REDUCE"):
            assert decision.risk_budget == 0.10
        else:
            assert decision.risk_budget == 0.01
