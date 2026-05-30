"""Planner MCP capability plan tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from src.core.planner import Planner
from src.schemas.research_task import ResearchTask


def test_planner_adds_mcp_capabilities_for_news_research():
    plan = _plan(objective="review market news")
    news_step = _step(plan, "NewsResearch")

    assert "web_search" in news_step.required_mcp_capabilities
    assert "financial_news" in news_step.required_mcp_capabilities


def test_planner_adds_mcp_capabilities_for_sentiment_research():
    plan = _plan(objective="review sentiment")
    sentiment_step = _step(plan, "SentimentResearch")

    assert sentiment_step.required_mcp_capabilities == ["social_sentiment"]
    assert "optional:trend_radar" in sentiment_step.evidence_requirements


def test_planner_does_not_require_mcp_for_pure_quant_step():
    plan = _plan(objective="analyze performance")
    quant_step = _step(plan, "QuantRiskAnalysis")

    assert quant_step.required_mcp_capabilities == []


def test_planner_plan_is_json_serializable():
    plan = _plan(objective="review market news")

    json.dumps(plan.to_dict())


def test_planner_does_not_generate_decision():
    plan = _plan(objective="review market news")
    data = plan.to_dict()

    assert "decision" not in data
    assert all("decision" not in step for step in data["steps"])


def _plan(objective: str):
    kg = MagicMock()
    kg.graph = None
    return Planner().plan(
        ResearchTask(
            task_id="planner-mcp",
            objective=objective,
            fund_universe=["110011"],
            risk_profile="moderate",
            time_horizon="1 year",
        ),
        kg,
    )


def _step(plan, skill_name: str):
    return next(step for step in plan.steps if step.skill_name == skill_name)
