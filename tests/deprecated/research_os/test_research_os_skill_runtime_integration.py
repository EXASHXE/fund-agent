"""Optional reference workflow integration with SkillInput / SkillOutput.

Host integrations use the skillpack manifest and skills_runtime directly.
"""

from __future__ import annotations

import json

from src.core.research_os import run_research_task
from src.core.skill_registry import SkillDefinition, SkillRegistry
from src.graph.knowledge_graph import KnowledgeGraph
from src.schemas.evidence import EvidenceItem
from src.schemas.research_task import ResearchTask
from src.schemas.skill import SkillInput, SkillOutput
from src.tools.adapters.mcp import InMemoryMCPHostAdapter


def test_research_os_builds_skill_input_from_plan_step():
    captured: list[SkillInput] = []

    def _capture(skill_input: SkillInput) -> SkillOutput:
        captured.append(skill_input)
        return SkillOutput(step_id=skill_input.step_id, skill_name=skill_input.skill_name)

    registry = SkillRegistry()
    registry.register(SkillDefinition(name="QuantRiskAnalysis", handler=_capture))

    run_research_task(_task(), kg=KnowledgeGraph(), skill_registry=registry, max_iterations=1)

    assert captured
    assert captured[0].task_id == "research-os-skill-runtime"
    assert captured[0].step_id == "step_0"
    assert captured[0].skill_name == "QuantRiskAnalysis"
    assert "fund_codes" in captured[0].kg_context


def test_research_os_collects_skill_output_evidence():
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            name="QuantRiskAnalysis",
            handler=lambda skill_input: SkillOutput(
                step_id=skill_input.step_id,
                skill_name=skill_input.skill_name,
                evidence_items=[_hard_evidence()],
            ),
        )
    )

    result = run_research_task(_task(), kg=KnowledgeGraph(), skill_registry=registry, max_iterations=1)

    assert result.evidence_count >= 1


def test_research_os_records_skill_output_errors():
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            name="QuantRiskAnalysis",
            handler=lambda skill_input: SkillOutput(
                step_id=skill_input.step_id,
                skill_name=skill_input.skill_name,
                status="FAILED",
                errors=[{"type": "SkillError", "message": "structured failure"}],
            ),
        )
    )

    result = run_research_task(_task(), kg=KnowledgeGraph(), skill_registry=registry, max_iterations=1)

    assert any("structured failure" in error["message"] for error in result.skill_errors)
    assert result.failed_steps


def test_research_os_records_mcp_capability_audit():
    registry = SkillRegistry(mcp_adapter=InMemoryMCPHostAdapter())

    result = run_research_task(_task(), kg=KnowledgeGraph(), skill_registry=registry, max_iterations=1)

    audit = result.artifacts["mcp_capability_audit"]
    assert audit
    assert any(record["missing_mcp_capabilities"] for record in audit)


def test_research_os_missing_required_mcp_prevents_false_pass():
    registry = SkillRegistry(mcp_adapter=InMemoryMCPHostAdapter())

    result = run_research_task(_task(), kg=KnowledgeGraph(), skill_registry=registry, max_iterations=1)

    assert result.critique_status != "PASS"


def test_research_os_final_thesis_is_json_serializable():
    result = run_research_task(
        _task(),
        kg=KnowledgeGraph(),
        skill_registry=SkillRegistry(),
        max_iterations=1,
    )

    json.dumps(result.to_dict())


def _hard_evidence() -> EvidenceItem:
    return EvidenceItem.from_tool_output(
        tool_name="local_quant_tools",
        output={"volatility": 0.12},
        claim="Risk volatility metric computed",
        entities=["fund:110011"],
        direction="neutral",
        provenance={"tool": "local_quant_tools"},
    )


def _task() -> ResearchTask:
    return ResearchTask(
        task_id="research-os-skill-runtime",
        objective="review market sentiment",
        fund_universe=["110011"],
        risk_profile="moderate",
        time_horizon="1 year",
    )
