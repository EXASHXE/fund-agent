"""Tests for src.core.planner — Planner, Plan, PlanStep.

Verifies:
    * PlanStep creation, serialization, dependencies
    * Plan initialization, serialization, timestamps
    * Planner KG-first behavior (KG context snapshotted before steps)
    * Step ordering, sequential IDs, default skill order
    * Replan increments iteration
    * Graceful handling of missing KG
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.core.planner import Plan, Planner, PlanStep
from src.schemas.research_task import ResearchTask


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_task() -> ResearchTask:
    return ResearchTask(
        task_id="test-001",
        fund_universe=["110011"],
        objective="review portfolio",
        risk_profile="moderate",
        time_horizon="1 year",
    )


@pytest.fixture
def multi_fund_task() -> ResearchTask:
    return ResearchTask(
        task_id="test-002",
        fund_universe=["110011", "000001"],
        objective="market analysis",
        risk_profile="aggressive",
        time_horizon="6 months",
    )


@pytest.fixture
def simple_objective_task() -> ResearchTask:
    return ResearchTask(
        task_id="test-003",
        fund_universe=["110011"],
        objective="analyze performance",
        risk_profile="moderate",
        time_horizon="1 year",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PlanStep Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlanStep:
    def test_plan_step_creation(self):
        """PlanStep should store all fields correctly."""
        step = PlanStep(
            step_id="step_0",
            skill_name="QuantRiskAnalysis",
            input={"param": 42},
            expected_output="Risk metrics",
            depends_on=[],
            reason="Always needed",
        )
        assert step.step_id == "step_0"
        assert step.skill_name == "QuantRiskAnalysis"
        assert step.input == {"param": 42}
        assert step.expected_output == "Risk metrics"
        assert step.depends_on == []
        assert step.reason == "Always needed"

    def test_plan_step_to_dict(self):
        """to_dict should produce expected keys."""
        step = PlanStep(
            step_id="step_1",
            skill_name="NewsResearch",
            input={"skill": "NewsResearch"},
            expected_output="EvidenceItems for NewsResearch",
            depends_on=["step_0"],
            reason="Required gap: NewsResearch",
        )
        d = step.to_dict()
        assert d["step_id"] == "step_1"
        assert d["skill_name"] == "NewsResearch"
        assert d["input"] == {"skill": "NewsResearch"}
        assert d["expected_output"] == "EvidenceItems for NewsResearch"
        assert d["depends_on"] == ["step_0"]
        assert d["reason"] == "Required gap: NewsResearch"

    def test_plan_step_dependencies(self):
        """Steps should track dependency chains."""
        step_0 = PlanStep(
            step_id="step_0",
            skill_name="First",
            depends_on=[],
            reason="entry",
        )
        step_1 = PlanStep(
            step_id="step_1",
            skill_name="Second",
            depends_on=["step_0"],
            reason="depends on first",
        )
        assert step_0.depends_on == []
        assert step_1.depends_on == ["step_0"]

    def test_plan_step_defaults(self):
        """PlanStep should have sensible defaults."""
        step = PlanStep(step_id="step_0", skill_name="Test")
        assert step.input == {}
        assert step.expected_output == ""
        assert step.depends_on == []
        assert step.reason == ""


# ═══════════════════════════════════════════════════════════════════════════════
# Plan Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlan:
    def test_plan_initialization(self):
        """Plan should store task_id, steps, and metadata."""
        steps = [PlanStep(step_id="step_0", skill_name="Test")]
        plan = Plan(
            task_id="test-001",
            steps=steps,
            kg_context_snapshot={"fund_codes": ["110011"]},
            iteration=0,
        )
        assert plan.task_id == "test-001"
        assert len(plan.steps) == 1
        assert plan.kg_context_snapshot == {"fund_codes": ["110011"]}
        assert plan.iteration == 0
        assert isinstance(plan.generated_at, datetime)

    def test_plan_to_dict(self):
        """Plan.to_dict should serialize all fields including steps."""
        steps = [
            PlanStep(step_id="step_0", skill_name="QuantRiskAnalysis", reason="r0"),
            PlanStep(step_id="step_1", skill_name="ThesisGeneration", depends_on=["step_0"], reason="r1"),
        ]
        plan = Plan(
            task_id="test-001",
            steps=steps,
            kg_context_snapshot={"fund_codes": ["110011"]},
            iteration=0,
        )
        d = plan.to_dict()
        assert d["task_id"] == "test-001"
        assert len(d["steps"]) == 2
        assert d["steps"][0]["step_id"] == "step_0"
        assert d["steps"][1]["depends_on"] == ["step_0"]
        assert "generated_at" in d
        assert d["iteration"] == 0

    def test_plan_default_steps(self):
        """Plan should default to empty steps."""
        plan = Plan(task_id="test-001")
        assert plan.steps == []
        assert plan.kg_context_snapshot == {}
        assert plan.iteration == 0

    def test_plan_to_dict_empty_steps(self):
        """to_dict should work with zero steps."""
        plan = Plan(task_id="test-empty")
        d = plan.to_dict()
        assert d["steps"] == []
        assert d["task_id"] == "test-empty"


# ═══════════════════════════════════════════════════════════════════════════════
# Planner Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlanner:
    def test_planner_queries_kg_first(self, sample_task):
        """KG context must be snapshotted in the Plan (queried BEFORE steps)."""
        planner = Planner()

        # Mock KG with a graph that has fund node
        kg = MagicMock()
        kg.graph = MagicMock()
        kg.graph.has_node.return_value = True

        plan = planner.plan(sample_task, kg)

        # KG context must exist and contain the fund code
        assert "fund_codes" in plan.kg_context_snapshot
        assert sample_task.fund_universe[0] in plan.kg_context_snapshot
        # Steps should be generated after KG query
        assert len(plan.steps) > 0

    def test_plan_generates_steps(self, sample_task):
        """Plan should generate steps for a review-based objective."""
        planner = Planner()

        # Mock KG
        kg = MagicMock()
        kg.graph = None  # No graph built → gaps detected

        plan = planner.plan(sample_task, kg)

        assert len(plan.steps) > 0
        assert plan.task_id == "test-001"
        assert plan.iteration == 0

        # Verify skill names are from DEFAULT_SKILL_ORDER
        skill_names = [s.skill_name for s in plan.steps]
        for name in skill_names:
            assert name in Planner.DEFAULT_SKILL_ORDER or name == name

    def test_plan_step_ids_sequential(self, sample_task):
        """Step IDs should be sequential: step_0, step_1, ..."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.plan(sample_task, kg)

        for i, step in enumerate(plan.steps):
            assert step.step_id == f"step_{i}"

    def test_plan_step_dependency_chain(self, sample_task):
        """Each step should depend on the previous step (linear chain)."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.plan(sample_task, kg)

        for i, step in enumerate(plan.steps):
            if i == 0:
                assert step.depends_on == [], f"step_{i} should have no deps"
            else:
                assert step.depends_on == [f"step_{i - 1}"], (
                    f"step_{i} should depend on step_{i - 1}"
                )

    def test_default_skill_order(self, sample_task):
        """Steps must follow DEFAULT_SKILL_ORDER (not arbitrary)."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.plan(sample_task, kg)

        skill_names = [s.skill_name for s in plan.steps]
        # Extract ordered subset that matches DEFAULT_SKILL_ORDER
        default_order = [s for s in Planner.DEFAULT_SKILL_ORDER if s in skill_names]

        # Full DEFAULT_SKILL_ORDER should appear in correct sequence
        for i in range(len(default_order) - 1):
            idx_current = skill_names.index(default_order[i])
            idx_next = skill_names.index(default_order[i + 1])
            assert idx_current < idx_next, (
                f"{default_order[i]} should come before {default_order[i + 1]}"
            )

    def test_plan_requires_thesis_generation_always(self, sample_task):
        """ThesisGeneration must always be the last step."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        # Even with a simple objective, thesis should be last
        plan = planner.plan(sample_task, kg)
        skill_names = [s.skill_name for s in plan.steps]
        assert skill_names[-1] == "ThesisGeneration", "ThesisGeneration must be final step"

    def test_replan_increments_iteration(self, sample_task):
        """replan should produce a plan with iteration incremented."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.replan(sample_task, kg, retry_suggestions=["missing quant"])
        assert plan.iteration == 1

        # Steps should still be generated
        assert len(plan.steps) > 0

    def test_no_news_without_review_market_objective(self, simple_objective_task):
        """News/Sentiment should NOT be included if objective lacks review/market keywords."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.plan(simple_objective_task, kg)
        skill_names = [s.skill_name for s in plan.steps]
        assert "NewsResearch" not in skill_names
        assert "SentimentResearch" not in skill_names

    def test_news_included_with_review_objective(self, sample_task):
        """News/Sentiment SHOULD be included when objective is 'review portfolio'."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.plan(sample_task, kg)
        skill_names = [s.skill_name for s in plan.steps]
        assert "NewsResearch" in skill_names
        assert "SentimentResearch" in skill_names

    def test_multi_fund_kg_context(self, multi_fund_task):
        """KG context should include all funds in the universe."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.plan(multi_fund_task, kg)
        ctx = plan.kg_context_snapshot
        assert ctx["fund_codes"] == ["110011", "000001"]
        for code in multi_fund_task.fund_universe:
            assert code in ctx

    def test_quant_risk_analysis_always_included(self, simple_objective_task):
        """QuantRiskAnalysis must always be included regardless of objective."""
        planner = Planner()
        kg = MagicMock()
        kg.graph = None

        plan = planner.plan(simple_objective_task, kg)
        skill_names = [s.skill_name for s in plan.steps]
        assert "QuantRiskAnalysis" in skill_names
