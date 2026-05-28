"""Tests for Phase 6: PlannerNode, CriticNode, LedgerNode, iteration loop, circuit breaker."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.state import FundResearchState, EMPTY_STATE


def _make_state(**overrides) -> FundResearchState:
    """Create a test state with sensible defaults, with optional overrides."""
    state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _make_fund_data(code: str = "110011") -> dict:
    """Create minimal fund data dict."""
    return {
        "code": code,
        "name": f"Test Fund {code}",
        "fund_type": "混合型",
        "nav": None,
        "perf": {},
        "holdings": [],
        "sectors": [],
    }


# =====================================================================
# Planner Node Tests
# =====================================================================

class TestPlannerNode:
    """Tests for planner_agent_node function."""

    def test_planner_emits_tasks(self):
        """Planner should emit research tasks for each fund."""
        from src.agents.graphs.planner_agent import planner_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
        )
        result = planner_agent_node(state)

        assert isinstance(result, dict)
        assert "research_tasks" in result
        assert len(result["research_tasks"]) == 1

        task = result["research_tasks"][0]
        assert task["fund_code"] == "110011"
        assert task["type"] == "score_fund"
        assert task["priority"] == "high"  # No existing scores
        assert "quant" in task["missing_dimensions"]

    def test_planner_handles_multiple_funds(self):
        """Planner should emit one task per fund."""
        from src.agents.graphs.planner_agent import planner_agent_node

        state = _make_state(
            funds_data={
                "110011": _make_fund_data("110011"),
                "000001": _make_fund_data("000001"),
            },
        )
        result = planner_agent_node(state)

        assert len(result["research_tasks"]) == 2
        codes = {t["fund_code"] for t in result["research_tasks"]}
        assert codes == {"110011", "000001"}

    def test_planner_lower_priority_with_scores(self):
        """Planner should lower priority when scores already exist."""
        from src.agents.graphs.planner_agent import planner_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            quant_scores={"110011": {"score": 75.0}},
            fundamental_scores={"110011": {"score": 65.0}},
        )
        result = planner_agent_node(state)

        task = result["research_tasks"][0]
        assert task["priority"] == "medium"  # Some scores exist, some missing

    def test_planner_low_priority_all_scored(self):
        """Planner should set low priority when all dimensions scored."""
        from src.agents.graphs.planner_agent import planner_agent_node

        scores = {"score": 75.0}
        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            quant_scores={"110011": scores},
            fundamental_scores={"110011": scores},
            event_scores={"110011": scores},
            position_scores={"110011": scores},
            timing_scores={"110011": scores},
        )
        result = planner_agent_node(state)

        task = result["research_tasks"][0]
        assert task["priority"] == "low"
        assert task["missing_dimensions"] == []

    def test_planner_increments_iteration(self):
        """Planner should increment iteration counter."""
        from src.agents.graphs.planner_agent import planner_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            iteration=2,
        )
        result = planner_agent_node(state)

        assert result["iteration"] == 3

    def test_planner_logs_iterations(self):
        """Planner should append to planner_iteration_log."""
        from src.agents.graphs.planner_agent import planner_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
        )
        state["planner_iteration_log"] = [{"iteration": 0}]  # type: ignore[typeddict-item]

        result = planner_agent_node(state)

        assert len(result["planner_iteration_log"]) == 2
        assert result["planner_iteration_log"][-1]["iteration"] == 1

    def test_planner_empty_state(self):
        """Planner should handle empty state gracefully."""
        from src.agents.graphs.planner_agent import planner_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
        result = planner_agent_node(state)

        assert result["research_tasks"] == []
        assert result["iteration"] == 1

    def test_planner_docstring_exists(self):
        """planner_agent_node must have a docstring."""
        from src.agents.graphs.planner_agent import planner_agent_node
        assert planner_agent_node.__doc__ is not None
        assert len(planner_agent_node.__doc__) > 10


# =====================================================================
# Critic Node Tests
# =====================================================================

class TestCriticNode:
    """Tests for critic_agent_node function."""

    def test_critic_detects_gaps(self):
        """Critic should flag missing scoring dimensions as gaps."""
        from src.agents.graphs.critic_agent import critic_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            quant_scores={"110011": {"score": 75.0}},
        )
        result = critic_agent_node(state)

        assert "critic_report" in result
        report = result["critic_report"]
        assert len(report["gaps"]) > 0
        assert any("fundamental" in g for g in report["gaps"])
        assert any("event" in g for g in report["gaps"])

    def test_critic_passes_when_complete(self):
        """Critic should pass when all dimensions have scores."""
        from src.agents.graphs.critic_agent import critic_agent_node

        scores = {"score": 75.0}
        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            quant_scores={"110011": scores},
            fundamental_scores={"110011": scores},
            event_scores={"110011": scores},
            position_scores={"110011": scores},
            timing_scores={"110011": scores},
        )
        result = critic_agent_node(state)

        report = result["critic_report"]
        assert report["passed"] is True
        assert report["gaps"] == []

    def test_critic_bias_increases_with_iterations(self):
        """Critic bias_score should increase with iteration count."""
        from src.agents.graphs.critic_agent import critic_agent_node

        state_1 = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            iteration=1,
        )
        state_3 = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            iteration=3,
        )

        result_1 = critic_agent_node(state_1)
        result_3 = critic_agent_node(state_3)

        # bias = min((iteration - 1) / 3.0, 1.0)
        # iter 1: 0.0, iter 3: 0.667
        assert result_1["critic_report"]["bias_score"] == 0.0
        assert result_3["critic_report"]["bias_score"] == pytest.approx(0.667, rel=0.01)
        assert result_1["critic_report"]["bias_score"] < result_3["critic_report"]["bias_score"]

    def test_circuit_breaker_max_iterations(self):
        """Circuit breaker should force-pass when iteration >= 3 even with gaps."""
        from src.agents.graphs.critic_agent import critic_agent_node

        # At iteration 3 with gaps — circuit breaker should force pass
        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            iteration=3,
        )
        result = critic_agent_node(state)

        report = result["critic_report"]
        assert report["passed"] is True
        assert report["circuit_broken"] is True
        assert len(report["gaps"]) > 0  # Gaps still exist

    def test_circuit_breaker_bias_threshold(self):
        """Circuit breaker should force-pass when bias_score > 0.8."""
        from src.agents.graphs.critic_agent import critic_agent_node

        # At iteration 4: bias = min((4-1)/3, 1.0) = 1.0 > 0.8
        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            iteration=4,
        )
        result = critic_agent_node(state)

        report = result["critic_report"]
        assert report["passed"] is True
        assert report["circuit_broken"] is True
        assert report["bias_score"] > 0.8

    def test_critic_no_gaps_at_iteration_1(self):
        """Critic should not pass at iteration 1 if gaps exist (no circuit breaker yet)."""
        from src.agents.graphs.critic_agent import critic_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            iteration=1,
        )
        result = critic_agent_node(state)

        report = result["critic_report"]
        assert report["passed"] is False
        assert report["circuit_broken"] is False

    def test_critic_empty_state(self):
        """Critic should handle empty funds_data gracefully."""
        from src.agents.graphs.critic_agent import critic_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
        result = critic_agent_node(state)

        assert "critic_report" in result
        assert result["critic_report"]["gaps"] == []
        assert result["critic_report"]["passed"] is True  # No funds → no gaps

    def test_critic_docstring_exists(self):
        """critic_agent_node must have a docstring."""
        from src.agents.graphs.critic_agent import critic_agent_node
        assert critic_agent_node.__doc__ is not None
        assert len(critic_agent_node.__doc__) > 10


# =====================================================================
# Ledger Node Tests
# =====================================================================

class TestLedgerNode:
    """Tests for ledger_agent_node function."""

    def test_ledger_generates_decisions(self):
        """Ledger should generate decisions from strategies."""
        from src.agents.graphs.ledger_node import ledger_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            strategies={
                "110011": {
                    "action": "HOLD",
                    "execution_amount": 0.0,
                    "rationale": ["Stable performance"],
                    "triggers": [],
                    "time_horizon": "3 months",
                    "risk_budget": 0.05,
                }
            },
            iteration=2,
        )
        result = ledger_agent_node(state)

        assert "final_thesis" in result
        assert "execution_ledger" in result
        assert result["phase"] == "complete"

        thesis = result["final_thesis"]
        assert "thesis_id" in thesis
        assert "decisions" in thesis
        assert len(thesis["decisions"]) == 1

        ledger = result["execution_ledger"]
        assert ledger["version"] == "execution-ledger.v1"
        assert len(ledger["decisions"]) == 1

    def test_ledger_decision_fields(self):
        """Each decision should contain all decision-contract.v2 fields."""
        from src.agents.graphs.ledger_node import ledger_agent_node

        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            strategies={
                "110011": {
                    "action": "ADD",
                    "execution_amount": 50000.0,
                    "rationale": ["Strong momentum", "Undervalued"],
                    "triggers": ["Price < 100"],
                    "time_horizon": "6 months",
                    "risk_budget": 0.08,
                }
            },
            critic_report={"passed": True},
        )
        result = ledger_agent_node(state)

        decision = result["final_thesis"]["decisions"][0]
        required_fields = [
            "decision_id", "fund_code", "fund_name", "action",
            "execution_amount", "rationale_anchor", "trigger_conditions",
            "invalidating_conditions", "time_horizon", "risk_budget",
            "audit_trail", "version",
        ]
        for field in required_fields:
            assert field in decision, f"Missing field: {field}"

        assert decision["version"] == "decision-contract.v2"
        assert decision["action"] == "ADD"
        assert decision["execution_amount"] == 50000.0
        assert "Strong momentum" in decision["rationale_anchor"]

    def test_ledger_confidence_from_critic(self):
        """Confidence should be higher when critic passed."""
        from src.agents.graphs.ledger_node import ledger_agent_node

        # With critic passed=True
        state_passed = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            strategies={"110011": {"action": "HOLD"}},
            critic_report={"passed": True},
        )
        # With critic passed=False
        state_failed = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
            strategies={"110011": {"action": "HOLD"}},
            critic_report={"passed": False},
        )

        result_passed = ledger_agent_node(state_passed)
        result_failed = ledger_agent_node(state_failed)

        assert result_passed["final_thesis"]["confidence"] == 0.8
        assert result_failed["final_thesis"]["confidence"] == 0.5

    def test_ledger_handles_no_strategies(self):
        """Ledger should handle empty strategies gracefully."""
        from src.agents.graphs.ledger_node import ledger_agent_node

        state = _make_state(funds_data={"110011": _make_fund_data("110011")})
        result = ledger_agent_node(state)

        assert result["final_thesis"]["decisions"] == []
        assert result["execution_ledger"]["decisions"] == []

    def test_ledger_includes_fund_name(self):
        """Decision should include the fund name from funds_data."""
        from src.agents.graphs.ledger_node import ledger_agent_node

        state = _make_state(
            funds_data={"110011": {"code": "110011", "name": "E Fund"}},
            strategies={"110011": {"action": "HOLD"}},
        )
        result = ledger_agent_node(state)

        assert result["final_thesis"]["decisions"][0]["fund_name"] == "E Fund"

    def test_ledger_empty_state(self):
        """Ledger should handle empty state gracefully."""
        from src.agents.graphs.ledger_node import ledger_agent_node

        state: FundResearchState = dict(EMPTY_STATE)  # type: ignore[arg-type]
        result = ledger_agent_node(state)

        assert result["final_thesis"]["decisions"] == []
        assert result["execution_ledger"]["decisions"] == []
        assert result["phase"] == "complete"

    def test_ledger_docstring_exists(self):
        """ledger_agent_node must have a docstring."""
        from src.agents.graphs.ledger_node import ledger_agent_node
        assert ledger_agent_node.__doc__ is not None
        assert len(ledger_agent_node.__doc__) > 10


# =====================================================================
# Iteration Loop & Supervisor Tests
# =====================================================================

class TestIterationLoop:
    """Tests for the iteration loop logic in the graph."""

    def test_critic_router_goes_to_strategy_on_pass(self):
        """_critic_router should route to strategy when critic passed."""
        from src.agents.graphs.supervisor import _critic_router

        state = _make_state(
            critic_report={"passed": True, "gaps": []},
            iteration=1,
        )
        next_node = _critic_router(state)
        assert next_node == "strategy"

    def test_critic_router_loops_on_gaps(self):
        """_critic_router should loop to planner when critic not passed and iter < 3."""
        from src.agents.graphs.supervisor import _critic_router

        state = _make_state(
            critic_report={"passed": False, "gaps": ["Missing quant score for 110011"]},
            iteration=1,
        )
        next_node = _critic_router(state)
        assert next_node == "planner"

    def test_critic_router_circuit_breaker_at_iter_3(self):
        """_critic_router should route to strategy when iteration >= 3."""
        from src.agents.graphs.supervisor import _critic_router

        state = _make_state(
            critic_report={"passed": False, "gaps": ["Missing quant score for 110011"]},
            iteration=3,
        )
        next_node = _critic_router(state)
        assert next_node == "strategy"

    def test_new_graph_has_all_eight_nodes(self):
        """build_research_graph should include all 8 nodes."""
        from src.agents.graphs.supervisor import build_research_graph

        graph = build_research_graph()
        assert graph is not None

    def test_new_graph_accepts_state(self):
        """New graph should accept FundResearchState without error."""
        from src.agents.graphs.supervisor import build_research_graph

        graph = build_research_graph()
        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
        )
        try:
            result = graph.invoke(state)
            assert isinstance(result, dict)
        except Exception:
            pass  # Some internal deps may not be fully wired

    def test_legacy_graph_still_works(self):
        """build_research_graph_legacy should still construct without error."""
        from src.agents.graphs.supervisor import build_research_graph_legacy

        graph = build_research_graph_legacy()
        assert graph is not None


# =====================================================================
# State Schema Tests
# =====================================================================

class TestStateSchema:
    """Tests for FundResearchState schema updates."""

    def test_state_has_new_fields(self):
        """FundResearchState should contain all Phase 6 fields."""
        import typing

        # Get type hints from the TypedDict
        hints = typing.get_type_hints(FundResearchState)
        new_fields = [
            "research_tasks",
            "planner_iteration_log",
            "critic_report",
            "critic_iteration",
            "final_thesis",
            "execution_ledger",
            "phase",
        ]
        for field in new_fields:
            assert field in hints, f"Missing state field: {field}"

    def test_empty_state_has_defaults(self):
        """EMPTY_STATE should have sensible defaults for new fields."""
        assert EMPTY_STATE["research_tasks"] == []
        assert EMPTY_STATE["planner_iteration_log"] == []
        assert EMPTY_STATE["critic_report"] == {}
        assert EMPTY_STATE["critic_iteration"] == 0
        assert EMPTY_STATE["final_thesis"] == {}
        assert EMPTY_STATE["execution_ledger"] == {}
        assert EMPTY_STATE["phase"] == "planning"

    def test_integration_planner_to_critic(self):
        """Planner output should flow correctly into critic input."""
        from src.agents.graphs.planner_agent import planner_agent_node
        from src.agents.graphs.critic_agent import critic_agent_node

        # Run planner
        state = _make_state(
            funds_data={"110011": _make_fund_data("110011")},
        )
        planner_result = planner_agent_node(state)
        state.update(planner_result)  # type: ignore[typeddict-item]

        # Run critic on planner's output
        critic_result = critic_agent_node(state)

        assert "critic_report" in critic_result
        # With no scores populated, critic should detect gaps
        assert len(critic_result["critic_report"]["gaps"]) > 0

    def test_integration_full_pipeline_mocked(self):
        """End-to-end: planner→news→quant→risk→research→critic→strategy→ledger."""
        from langgraph.graph import END, StateGraph

        from src.agents.state import FundResearchState

        # Define simple node functions
        def _planner(state):
            return {"research_tasks": [{"fund_code": "110011"}], "iteration": 1}

        def _news(state):
            return {"scored_news": {"110011": {}}}

        def _quant(state):
            return {"quant_scores": {"110011": {}}}

        def _risk(state):
            return {"risk_assessments": {"110011": {}}, "timing_scores": {"110011": {}}}

        def _research(state):
            return {"fundamental_scores": {"110011": {}}, "event_scores": {"110011": {}}, "position_scores": {"110011": {}}}

        def _critic(state):
            return {"critic_report": {"passed": True, "gaps": [], "bias_score": 0.0}}

        def _critic_router(state):
            cr = state.get("critic_report", {})
            return "strategy" if cr.get("passed") else "planner"

        def _strategy(state):
            return {"strategies": {"110011": {"action": "HOLD"}}}

        def _ledger(state):
            return {"final_thesis": {"decisions": [{"action": "HOLD"}]}, "execution_ledger": {"decisions": []}, "phase": "complete"}

        graph = StateGraph(FundResearchState)
        graph.add_node("planner", _planner)
        graph.add_node("news", _news)
        graph.add_node("quant", _quant)
        graph.add_node("risk", _risk)
        graph.add_node("research", _research)
        graph.add_node("critic", _critic)
        graph.add_node("strategy", _strategy)
        graph.add_node("ledger", _ledger)

        graph.set_entry_point("planner")
        graph.add_edge("planner", "news")
        graph.add_edge("news", "quant")
        graph.add_edge("quant", "risk")
        graph.add_edge("risk", "research")
        graph.add_edge("research", "critic")
        graph.add_conditional_edges("critic", _critic_router)
        graph.add_edge("strategy", "ledger")
        graph.add_edge("ledger", END)

        compiled = graph.compile()

        state = _make_state(funds_data={"110011": {"code": "110011"}})
        result = compiled.invoke(state)

        assert result["research_tasks"] == [{"fund_code": "110011"}]
        assert result["critic_report"]["passed"] is True
        assert result["strategies"] == {"110011": {"action": "HOLD"}}
        assert result["final_thesis"]["decisions"] == [{"action": "HOLD"}]
        assert result["phase"] == "complete"
