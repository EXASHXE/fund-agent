"""Runtime contract tests for the Research OS loop."""

from __future__ import annotations

import json
import networkx as nx

from src.core.research_os import run_research_task
from src.core.skill_registry import SkillDefinition, SkillOutput, SkillRegistry
from src.graph.knowledge_graph import KnowledgeGraph
from src.schemas.research_task import ResearchTask


def test_missing_skill_is_recorded():
    """A planned but unregistered skill is recorded in skill_errors."""
    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    assert result.skill_errors
    assert any(error["error_type"] == "KeyError" for error in result.skill_errors)
    assert result.failed_steps


def test_skill_exception_is_recorded():
    """A skill handler exception is recorded in failed_steps/skill_errors."""
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            name="QuantRiskAnalysis",
            handler=lambda _: (_ for _ in ()).throw(RuntimeError("skill exploded")),
        )
    )

    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=registry,
        max_iterations=1,
    )

    assert any("skill exploded" in error["message"] for error in result.skill_errors)
    assert any("skill exploded" in step["error"] for step in result.failed_steps)


def test_empty_evidence_never_passes_critic():
    """Empty evidence must not produce a PASS critique."""
    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    assert result.evidence_count == 0
    assert result.critique_status != "PASS"


def test_max_iterations_returns_exhausted_not_pass():
    """ResearchOS max_iterations exhaustion returns EXHAUSTED, not PASS."""
    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    assert result.iterations == 1
    assert result.critique_status == "EXHAUSTED"


def test_final_thesis_contains_compile_reports():
    """FinalThesis artifacts expose compile reports and final critique status."""
    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    artifacts = result.artifacts
    assert "skill_errors" in artifacts
    assert "failed_steps" in artifacts
    assert "warnings" in artifacts
    assert "mcp_capability_audit" in artifacts
    assert "evidence_compile_report" in artifacts
    assert "iteration_compile_reports" in artifacts
    assert "final_critique_status" in artifacts
    assert artifacts["final_critique_status"] == result.critique_status


def test_exhausted_outputs_only_passive_decision():
    """EXHAUSTED ResearchOS runs can only emit passive decisions."""
    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    assert result.critique_status == "EXHAUSTED"
    assert result.decision is not None
    assert result.decision["action"] in {"WAIT", "HOLD", "PAUSE_DCA"}


def test_final_thesis_contains_runtime_audit_fields():
    """FinalThesis artifacts include all runtime audit fields."""
    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    artifacts = result.artifacts
    for key in (
        "skill_errors",
        "failed_steps",
        "warnings",
        "mcp_capability_audit",
        "evidence_compile_report",
        "iteration_compile_reports",
        "final_critique_status",
        "final_decision_status",
        "ledger_id",
    ):
        assert key in artifacts
    assert artifacts["final_decision_status"] == result.decision["action"]
    assert artifacts["ledger_id"] == result.ledger["ledger_id"]


def test_final_thesis_is_json_serializable():
    """FinalThesis.to_dict output must be JSON serializable."""
    result = run_research_task(
        task=_task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    json.dumps(result.to_dict())


def test_kg_query_failure_is_recorded_as_warning(monkeypatch):
    """KG query fallback must record a warning instead of silently swallowing."""
    graph = nx.DiGraph()
    graph.add_node("fund:110011")
    kg = KnowledgeGraph(graph=graph)

    def _raise(*args, **kwargs):
        raise RuntimeError("kg unavailable")

    monkeypatch.setattr("src.core.research_os.get_entity_chain", _raise)

    result = run_research_task(
        task=_task(),
        kg=kg,
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    assert any("KG query failed" in warning for warning in result.warnings)
    assert any("kg unavailable" in warning for warning in result.warnings)


def _task() -> ResearchTask:
    return ResearchTask(
        task_id="runtime-contract",
        objective="review",
        fund_universe=["110011"],
        risk_profile="moderate",
        time_horizon="1 year",
    )
