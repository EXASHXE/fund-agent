"""External host smoke tests without ResearchOS."""

from __future__ import annotations

import json
import sys

from src.schemas.skill import SkillInput
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability
from src.tools.evidence.validators import compile_evidence_graph


def test_external_host_can_run_news_to_decision_without_research_os():
    before = set(sys.modules)
    output = _run_news_to_decision()
    newly_imported = set(sys.modules) - before

    assert output.status in {"OK", "PARTIAL"}
    assert "decision" in output.artifacts
    assert "execution_ledger" in output.artifacts
    assert "src.core.research_os" not in newly_imported


def test_external_host_can_run_fund_analysis_to_decision_without_research_os():
    before = set(sys.modules)
    manifest = load_skillpack_manifest()
    fund_cls = resolve_runtime(manifest.skill("fund_analysis").runtime)

    fund_output = fund_cls().run(
        SkillInput(
            task_id="host-smoke",
            step_id="fund",
            skill_name="fund_analysis",
            payload={"related_entities": ["fund:110011"]},
        )
    )
    compile_result = compile_evidence_graph(fund_output.evidence_items)
    decision_output = DecisionSupportSkill().run(
        SkillInput(
            task_id="host-smoke",
            step_id="decision",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": "review fund",
                "time_horizon": "1 year",
            },
        )
    )
    newly_imported = set(sys.modules) - before

    assert fund_output.status == "OK"
    assert decision_output.status == "OK"
    assert "decision" in decision_output.artifacts
    assert "src.core.research_os" not in newly_imported


def test_external_host_flow_is_json_serializable():
    output = _run_news_to_decision()

    json.dumps(output.to_dict())


def _run_news_to_decision():
    manifest = load_skillpack_manifest()
    news_spec = manifest.skill("news_research")
    news_cls = resolve_runtime(news_spec.runtime)
    host_mcp = InMemoryMCPHostAdapter(
        capabilities=[
            MCPCapability(name="financial_news", input_schema={}, output_schema={})
        ],
        handlers={
            "financial_news": lambda _: {
                "items": [
                    {
                        "claim": "Host financial news signal is positive",
                        "timestamp": "2026-05-31T00:00:00",
                        "related_entities": ["fund:110011"],
                        "confidence_weight": 0.7,
                        "direction": "positive",
                    }
                ]
            }
        },
    )
    news_output = news_cls(mcp_adapter=host_mcp).run(
        SkillInput(
            task_id="host-smoke",
            step_id="news",
            skill_name="news_research",
            payload={"related_entities": ["fund:110011"]},
            required_mcp_capabilities=["financial_news"],
        )
    )
    compile_result = compile_evidence_graph(news_output.evidence_items)
    return DecisionSupportSkill().run(
        SkillInput(
            task_id="host-smoke",
            step_id="decision",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": "review fund",
                "time_horizon": "1 year",
            },
        )
    )
