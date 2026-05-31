import pytest

from legacy.agents.orchestrator import AgentOrchestrator
from legacy.agents.protocols import AgentContext, AgentOpinion, StageResult
from src.tools.registry import ToolDefinition, ToolRegistry


def test_tool_registry_filters_tools_by_agent_and_invokes_handler():
    registry = ToolRegistry()

    @registry.tool("news.brief", "Return compressed news context", agents=("news",))
    def news_brief(code):
        return {"code": code, "brief": "ok"}

    @registry.tool("portfolio.summary", "Return portfolio summary", agents=("portfolio",))
    def portfolio_summary():
        return {"total": 100}

    assert [tool.name for tool in registry.list("news")] == ["news.brief"]
    assert [tool.name for tool in registry.list("portfolio")] == ["portfolio.summary"]
    assert registry.invoke("news.brief", code="000001") == {"code": "000001", "brief": "ok"}


def test_tool_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    registry.register(ToolDefinition("dup", "first", lambda: None))

    with pytest.raises(ValueError, match="工具已注册"):
        registry.register(ToolDefinition("dup", "second", lambda: None))


def test_agent_protocols_keep_evidence_slices_separate():
    ctx = AgentContext(
        report_date="2026-05-22",
        evidence={"funds": {"000001": {"identity": {"name": "测试基金"}}}},
        prompts={"news": "prompt"},
        tool_names=("news.brief",),
    )
    result = StageResult(name="news", status="ok", output={"done": True})

    assert ctx.fund_evidence("000001")["identity"]["name"] == "测试基金"
    assert ctx.fund_evidence("missing") == {}
    assert result.ok is True


def test_agent_orchestrator_collects_opinions_and_stage_errors():
    ctx = AgentContext(report_date="2026-05-22", evidence={"funds": {}})
    orchestrator = AgentOrchestrator()

    orchestrator.register(
        "news",
        lambda context: AgentOpinion(
            agent="news",
            payload={"report_date": context.report_date, "impact": "neutral"},
            confidence=0.5,
        ),
    )
    result = orchestrator.run(ctx, ["news", "summary"])

    assert result.ok is False
    assert result.opinions[0].payload["impact"] == "neutral"
    assert result.stages[0].ok is True
    assert result.stages[1].errors == ("未注册 Agent: summary",)
