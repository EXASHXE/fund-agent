"""Tests for Phase 4 agent tool bindings."""


def _evidence():
    return {
        "portfolio": {"total_value": 10000},
        "portfolio_evidence": {"risk_matrix": {"warnings": ["集中"]}},
        "workflow_evidence": {},
        "funds": {
            "000001": {
                "identity": {"name": "测试基金"},
                "risk_constraints": {"current_weight": 0.1},
                "holding_metrics": {"current_value": 1000},
                "quant_baseline": {"macro_score": 15, "total_score": 72},
                "factor_matrix": {"source": "kg_ai_pipeline"},
                "trend_evidence": {"short_term": {"direction": "flat"}},
                "strategy_advice": {"action": "hold", "confidence": 0.72},
                "news_evidence": {"news_count": 0, "samples": []},
            }
        },
        "recommendation_evidence": {"status": "skipped", "candidates": []},
    }


def test_agent_tool_registry_exposes_strategy_relevant_evidence_tools():
    from legacy.agents.tools import build_agent_tool_registry, tools_for_agent

    registry = build_agent_tool_registry(_evidence())
    names = [tool.name for tool in tools_for_agent(registry, "strategy")]

    assert "evidence.fund_identity" in names
    assert "kg.impact_chain" in names
    assert "scoring.factor_matrix" in names
    assert "portfolio.context" in names
    assert "strategy.evaluate_trigger" in names

    payload = registry.invoke("evidence.fund_identity", code="000001")
    assert payload["identity"]["name"] == "测试基金"


def test_strategy_trigger_tool_uses_strategy_model_contract():
    from legacy.agents.tools import build_agent_tool_registry

    registry = build_agent_tool_registry(_evidence())
    result = registry.invoke(
        "strategy.evaluate_trigger",
        trigger={
            "metric": "score",
            "operator": ">=",
            "threshold": 70,
            "description": "评分确认",
        },
        context={"score": 72},
    )

    assert result == {"triggered": True, "description": "评分确认"}


def test_kg_impact_chain_tool_uses_graph_builder_contract():
    import networkx as nx

    from legacy.agents.tools import build_agent_tool_registry
    from src.graph.schema import EventNode, FundNode, KGEdge, KGEdgeType, StockNode

    graph = nx.DiGraph()
    graph.add_node("fund:000001", data=FundNode(code="000001", name="测试基金"))
    graph.add_node("stock:600519", data=StockNode(code="600519", name="贵州茅台"))
    graph.add_edge(
        "fund:000001",
        "stock:600519",
        edge_data=KGEdge(
            source="fund:000001",
            target="stock:600519",
            edge_type=KGEdgeType.HOLDS,
            weight=10.0,
        ),
    )
    graph.add_node(
        "event:evt-1",
        data=EventNode(event_id="evt-1", event_type="policy", polarity=-0.5, magnitude=0.8),
    )
    graph.add_edge(
        "event:evt-1",
        "stock:600519",
        edge_data=KGEdge(
            source="event:evt-1",
            target="stock:600519",
            edge_type=KGEdgeType.IMPACTS,
            polarity=-0.5,
            magnitude=0.8,
        ),
    )

    registry = build_agent_tool_registry(_evidence(), graph=graph)
    result = registry.invoke("kg.impact_chain", code="000001", event_id="evt-1")

    assert result["total_polarity"] == -0.05
    assert result["paths"][0]["stock"] == "stock:600519"


def test_agent_tools_package_exposes_planned_tool_modules():
    from legacy.agents.tools import AGENT_TOOL_MODULES

    assert AGENT_TOOL_MODULES == (
        "kg_tools",
        "vector_tools",
        "news_tools",
        "analysis_tools",
        "strategy_tools",
    )
