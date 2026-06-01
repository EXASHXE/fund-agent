"""Minimal host demo: news → evidence → decision.

This demonstrates the complete external host integration flow using only
in-memory adapters. No real network calls, no provider SDKs, no ResearchOS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.skill import SkillInput
from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability
from src.tools.evidence.validators import compile_evidence_graph


def main() -> None:
    manifest = load_skillpack_manifest()
    news_spec = manifest.skill("news_research")

    adapter = InMemoryMCPHostAdapter(
        capabilities=[
            MCPCapability(
                name="financial_news",
                input_schema={"query": "string"},
                output_schema={"items": "list"},
            ),
            MCPCapability(
                name="web_search",
                input_schema={"query": "string"},
                output_schema={"items": "list"},
            ),
        ],
        handlers={
            "financial_news": _mock_handler,
            "web_search": _mock_handler,
        },
    )

    news_cls = resolve_runtime(news_spec.runtime)
    news_skill = news_cls(mcp_adapter=adapter)

    news_output = news_skill.run(
        SkillInput(
            task_id="host-task-1",
            step_id="news-1",
            skill_name="news_research",
            payload={"related_entities": ["fund:110011"]},
            required_mcp_capabilities=news_spec.requires_mcp,
        )
    )

    compile_result = compile_evidence_graph(news_output.evidence_items)

    decision_output = DecisionSupportSkill().run(
        SkillInput(
            task_id="host-task-1",
            step_id="decision-1",
            skill_name="decision_support",
            payload={
                "evidence_graph": compile_result.graph.to_dict(),
                "objective": "review fund",
                "time_horizon": "1 year",
            },
        )
    )

    result = {
        "status": "OK",
        "decision": decision_output.artifacts.get("decision"),
        "execution_ledger": decision_output.artifacts.get("execution_ledger"),
    }
    print(json.dumps(result, indent=2, default=str))


def _mock_handler(payload: dict) -> dict:
    return {
        "ok": True,
        "data": {
            "items": [
                {
                    "source_type": "financial_news",
                    "claim": "Fund demonstrates strong Q1 performance",
                    "direction": "positive",
                    "confidence_weight": 0.75,
                    "related_entities": payload.get("related_entities", []),
                    "timestamp": "2026-06-01T00:00:00",
                },
            ],
        },
    }


if __name__ == "__main__":
    main()
