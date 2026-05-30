"""Host integration contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability
from src.tools.evidence.validators import compile_evidence_graph


def test_host_agent_can_resolve_and_call_skill_from_manifest():
    manifest = load_skillpack_manifest()
    news_spec = manifest.skill("news_research")
    news_cls = resolve_runtime(news_spec.runtime)
    host_mcp = _host_mcp()

    output = news_cls(mcp_adapter=host_mcp).run(
        SkillInput(
            task_id="host",
            step_id="news",
            skill_name="news_research",
            payload={"related_entities": ["fund:110011"]},
            required_mcp_capabilities=["financial_news"],
        )
    )

    assert output.status == "OK"
    assert output.evidence_items


def test_host_agent_can_compile_evidence_and_call_decision_support():
    host_mcp = _host_mcp()
    manifest = load_skillpack_manifest()
    news_cls = resolve_runtime(manifest.skill("news_research").runtime)
    news_output = news_cls(mcp_adapter=host_mcp).run(
        SkillInput(
            task_id="host",
            step_id="news",
            skill_name="news_research",
            payload={"related_entities": ["fund:110011"]},
            required_mcp_capabilities=["financial_news"],
        )
    )

    compile_result = compile_evidence_graph(news_output.evidence_items)
    decision_output = DecisionSupportSkill().run(
        SkillInput(
            task_id="host",
            step_id="decision",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": "review fund",
                "time_horizon": "1 year",
            },
        )
    )

    assert decision_output.status == "OK"
    assert "decision" in decision_output.artifacts
    assert "execution_ledger" in decision_output.artifacts
    json.dumps(decision_output.to_dict())


def test_host_integration_doc_exists_and_describes_external_agent_flow():
    content = Path("docs/host-integration.md").read_text()

    for phrase in (
        "external agent host",
        "load_skillpack_manifest",
        "resolve_runtime",
        "MCPHostAdapter",
        "SkillInput",
        "compile_evidence_graph",
        "DecisionSupportSkill",
        "does not own the agent loop",
    ):
        assert phrase in content


def _host_mcp() -> InMemoryMCPHostAdapter:
    return InMemoryMCPHostAdapter(
        capabilities=[
            MCPCapability(
                name="financial_news",
                input_schema={},
                output_schema={},
            )
        ],
        handlers={
            "financial_news": lambda _: {
                "items": [
                    {
                        "claim": "Positive host news signal",
                        "timestamp": "2026-05-31T00:00:00",
                        "related_entities": ["fund:110011"],
                        "confidence_weight": 0.7,
                        "direction": "positive",
                    }
                ]
            }
        },
    )
