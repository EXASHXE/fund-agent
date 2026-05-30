"""Tests for the ResearchTask schema, SourceType, and backward-compatible aliases."""

from __future__ import annotations

import pytest
from src.schemas.research_task import ResearchTask
from src.schemas.evidence import SourceType, Direction
from src.schemas.decision import ActionType
from src.schemas import EvidenceDirection, DecisionAction


def test_research_task_creation():
    """Create ResearchTask with all fields provided."""
    task = ResearchTask(
        task_id="task-001",
        user_id="user-42",
        portfolio={"funds": ["fund:110011"], "weights": [1.0]},
        fund_universe=["fund:110011", "fund:110022"],
        as_of_date="2025-06-01",
        objective="Evaluate portfolio risk-adjusted returns",
        constraints={"max_risk_budget": 0.1},
        risk_profile="aggressive",
        time_horizon="6 months",
    )
    assert task.task_id == "task-001"
    assert task.user_id == "user-42"
    assert task.portfolio == {"funds": ["fund:110011"], "weights": [1.0]}
    assert task.fund_universe == ["fund:110011", "fund:110022"]
    assert task.as_of_date == "2025-06-01"
    assert task.objective == "Evaluate portfolio risk-adjusted returns"
    assert task.constraints == {"max_risk_budget": 0.1}
    assert task.risk_profile == "aggressive"
    assert task.time_horizon == "6 months"


def test_research_task_defaults():
    """ResearchTask default values should be set correctly."""
    task = ResearchTask(task_id="task-default")
    assert task.user_id == ""
    assert task.portfolio == {}
    assert task.fund_universe == []
    assert task.as_of_date == ""
    assert task.objective == ""
    assert task.constraints == {}
    assert task.risk_profile == "moderate"
    assert task.time_horizon == "1 year"


def test_research_task_to_dict():
    """to_dict should produce camelCase JSON-compatible dict and roundtrip via from_dict."""
    task = ResearchTask(
        task_id="task-002",
        user_id="user-99",
        portfolio={"funds": ["fund:110011"]},
        fund_universe=["fund:110011"],
        as_of_date="2025-07-01",
        objective="Test serialization",
        constraints={"limit": 5},
        risk_profile="conservative",
        time_horizon="3 months",
    )
    d = task.to_dict()

    # Verify camelCase keys
    assert d["taskId"] == "task-002"
    assert d["userId"] == "user-99"
    assert d["fundUniverse"] == ["fund:110011"]
    assert d["asOfDate"] == "2025-07-01"
    assert d["riskProfile"] == "conservative"
    assert d["timeHorizon"] == "3 months"

    # Verify snake_case originals are preserved as-is in the dataclass
    assert task.task_id == "task-002"
    assert task.as_of_date == "2025-07-01"

    # Roundtrip via from_dict with camelCase keys
    task2 = ResearchTask.from_dict(d)
    assert task2 == task


def test_research_task_from_dict():
    """Deserialize from a snake_case dict back to ResearchTask."""
    data = {
        "task_id": "task-from-dict",
        "user_id": "alice",
        "portfolio": {"funds": ["fund:000001"]},
        "fund_universe": ["fund:000001", "fund:000002"],
        "as_of_date": "2025-08-15",
        "objective": "Analyze diversification",
        "constraints": {"min_funds": 2},
        "risk_profile": "moderate",
        "time_horizon": "1 year",
    }
    task = ResearchTask.from_dict(data)
    assert task.task_id == "task-from-dict"
    assert task.user_id == "alice"
    assert len(task.fund_universe) == 2
    assert task.risk_profile == "moderate"
    assert task.time_horizon == "1 year"

    # Also verify from_dict handles camelCase keys (like a to_dict output)
    task2 = ResearchTask.from_dict({
        "taskId": "task-camel",
        "userId": "bob",
        "fundUniverse": ["fund:000003"],
        "asOfDate": "2025-09-01",
        "riskProfile": "aggressive",
        "timeHorizon": "6 months",
        "portfolio": {"funds": ["fund:000003"]},
        "objective": "Test camelCase from_dict",
        "constraints": {},
    })
    assert task2.task_id == "task-camel"
    assert task2.user_id == "bob"


def test_source_type_valid_values():
    """SourceType should accept all six valid literal values."""
    valid_values = [
        "quant_tool",
        "news_source",
        "sentiment_analysis",
        "kg_query",
        "llm_inference",
        "hybrid",
    ]
    for val in valid_values:
        # Verify type-checking works by assigning to a variable typed as SourceType
        st: SourceType = val  # type: ignore[valid-type]
        assert st == val


def test_evidence_direction_alias():
    """EvidenceDirection should be identical to Direction."""
    assert EvidenceDirection is Direction
    # Verify it accepts the same literals
    for d in ("positive", "negative", "neutral"):
        assert d in Direction.__args__
        assert d in EvidenceDirection.__args__


def test_decision_action_alias():
    """DecisionAction should be identical to ActionType."""
    assert DecisionAction is ActionType
    # Verify it accepts the same literals
    for act in ("BUY", "SELL", "HOLD", "PAUSE_DCA", "REDUCE", "INCREASE", "WAIT"):
        assert act in ActionType.__args__
        assert act in DecisionAction.__args__
