"""Minimal host-agent flow for fund-agent skill pack."""

from src.schemas.skill import SkillInput
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.skills_runtime.news_research import NewsResearchSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability
from src.tools.evidence.validators import compile_evidence_graph


host_mcp = InMemoryMCPHostAdapter(
    capabilities=[
        MCPCapability(name="financial_news", input_schema={}, output_schema={}),
    ],
    handlers={
        "financial_news": lambda payload: {
            "items": [
                {
                    "claim": "Example host-provided news signal",
                    "timestamp": "2026-05-31T00:00:00",
                    "related_entities": ["fund:110011"],
                    "direction": "neutral",
                    "confidence_weight": 0.5,
                }
            ]
        }
    },
)

news_skill = NewsResearchSkill(mcp_adapter=host_mcp)
news_output = news_skill.run(
    SkillInput(
        task_id="example",
        step_id="news",
        skill_name="news_research",
        payload={"query": "fund:110011"},
        required_mcp_capabilities=["financial_news"],
    )
)

compile_result = compile_evidence_graph(news_output.evidence_items)
decision_output = DecisionSupportSkill().run(
    SkillInput(
        task_id="example",
        step_id="decision",
        skill_name="decision_support",
        payload={
            "evidence_graph": compile_result.graph.to_dict(),
            "objective": "review fund",
            "time_horizon": "1 year",
        },
    )
)
