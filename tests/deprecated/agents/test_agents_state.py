"""Tests for LangGraph state and supervisor routing."""
import pytest
from legacy.agents.state import FundResearchState, EMPTY_STATE
from legacy.agents.supervisor import get_supervisor_routing, AGENT_ORDER


class TestFundResearchState:
    def test_empty_state_creation(self):
        state = EMPTY_STATE
        assert state["portfolio_config"] == {}
        assert state["funds_data"] == {}
        assert state["iteration"] == 0
        assert state["errors"] == []

    def test_state_has_all_required_fields(self):
        required_fields = [
            "portfolio_config", "report_date", "funds_data", "knowledge_graph",
            "search_plans", "raw_news", "classified_news", "scored_news",
            "research_summaries", "extracted_events",
            "market_regime", "quant_scores", "fundamental_scores",
            "event_scores", "position_scores", "timing_scores", "final_scores",
            "risk_assessments", "strategies", "portfolio_strategy",
            "iteration", "next_agent", "errors",
        ]
        for field in required_fields:
            assert field in EMPTY_STATE, f"Missing field: {field}"

    def test_empty_state_market_regime(self):
        assert EMPTY_STATE["market_regime"] == "normal"


class TestSupervisorRouting:
    def test_agent_order_is_valid(self):
        assert AGENT_ORDER == ["news", "quant", "risk", "research", "strategy"]

    def test_supervisor_routing_initial(self):
        routing = get_supervisor_routing(state=EMPTY_STATE)
        assert routing["next_agent"] == "news"

    def test_supervisor_routing_after_news(self):
        state = dict(EMPTY_STATE)
        state["scored_news"] = {"110011": {"count": 5}}
        routing = get_supervisor_routing(state=state)
        assert routing["next_agent"] in ["quant", "risk"]

    def test_supervisor_routing_explicit_next_agent(self):
        state = dict(EMPTY_STATE)
        state["next_agent"] = "research"
        routing = get_supervisor_routing(state=state)
        assert routing["next_agent"] == "research"

    def test_supervisor_routing_all_done(self):
        state = dict(EMPTY_STATE)
        state["scored_news"] = {"110011": {}}
        state["quant_scores"] = {"110011": {}}
        state["risk_assessments"] = {"110011": {}}
        state["fundamental_scores"] = {"110011": {}}
        state["timing_scores"] = {"110011": {}}
        state["strategies"] = {"110011": {}}
        routing = get_supervisor_routing(state=state)
        assert routing["next_agent"] == "done"

    def test_supervisor_routing_needs_quant(self):
        state = dict(EMPTY_STATE)
        state["scored_news"] = {"110011": {}}  # news done
        routing = get_supervisor_routing(state=state)
        assert routing["next_agent"] == "quant"

    def test_supervisor_routing_needs_risk(self):
        state = dict(EMPTY_STATE)
        state["scored_news"] = {"110011": {}}
        state["quant_scores"] = {"110011": {}}  # quant done
        routing = get_supervisor_routing(state=state)
        assert routing["next_agent"] == "risk"