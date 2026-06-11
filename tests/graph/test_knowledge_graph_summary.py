"""Tests for knowledge_graph_summary artifact in fund_analysis."""
from __future__ import annotations

import json
import pytest

from src.skills_runtime.fund_analysis.knowledge_graph_stage import build_knowledge_graph_summary


class TestKnowledgeGraphSummary:
    def test_holdings_present_produces_summary(self):
        positions = [
            {"fund_code": "110011", "fund_name": "Test Fund", "shares": 1000, "current_nav": 1.5, "cost_nav": 1.2, "current_value": 1500, "cost_value": 1200, "pnl_pct": 25.0, "asset_type": "equity"},
        ]
        fund_profiles = {"110011": {"fund_type": "equity", "fund_name": "Test Fund"}}
        holdings = {
            "110011": [
                {"stock_code": "600519", "stock_name": "Moutai", "weight": 9.5, "sector": "consumer", "industry": "baijiu"},
                {"stock_code": "000858", "stock_name": "Wuliangye", "weight": 7.2, "sector": "consumer", "industry": "baijiu"},
            ],
        }
        result = build_knowledge_graph_summary(
            positions=positions,
            fund_profiles=fund_profiles,
            holdings=holdings,
        )
        assert result["enabled"] is True
        assert result["fund_count"] >= 1
        assert result["stock_count"] >= 1
        assert isinstance(result["top_shared_holdings"], list)
        assert isinstance(result["theme_paths"], list)
        assert isinstance(result["limitations"], list)

    def test_holdings_missing_produces_disabled_summary(self):
        result = build_knowledge_graph_summary(
            positions=[],
            fund_profiles={},
            holdings={},
        )
        assert result["enabled"] is False
        assert result["fund_count"] == 0
        assert len(result["limitations"]) >= 1

    def test_events_appear_when_host_provided(self):
        positions = [
            {"fund_code": "110011", "fund_name": "Test Fund", "shares": 1000, "current_nav": 1.5, "cost_nav": 1.2, "current_value": 1500, "cost_value": 1200, "pnl_pct": 25.0, "asset_type": "equity"},
        ]
        fund_profiles = {"110011": {"fund_type": "equity"}}
        holdings = {
            "110011": [
                {"stock_code": "600519", "stock_name": "Moutai", "weight": 9.5, "sector": "consumer", "industry": "baijiu"},
            ],
        }
        events = [
            {"event_id": "E001", "event_type": "regulatory", "polarity": 0.8, "magnitude": 0.6},
        ]
        result = build_knowledge_graph_summary(
            positions=positions,
            fund_profiles=fund_profiles,
            holdings=holdings,
            events=events,
        )
        assert result["enabled"] is True
        assert result["event_count"] >= 1

    def test_no_formal_decision_in_summary(self):
        positions = [
            {"fund_code": "110011", "fund_name": "Test Fund", "shares": 1000, "current_nav": 1.5, "cost_nav": 1.2, "current_value": 1500, "cost_value": 1200, "pnl_pct": 25.0, "asset_type": "equity"},
        ]
        fund_profiles = {"110011": {"fund_type": "equity"}}
        holdings = {"110011": [{"stock_code": "600519", "stock_name": "Moutai", "weight": 9.5, "sector": "consumer", "industry": "baijiu"}]}
        result = build_knowledge_graph_summary(
            positions=positions,
            fund_profiles=fund_profiles,
            holdings=holdings,
        )
        assert "decision" not in result
        assert "execution_ledger" not in result


class TestKnowledgeGraphSummaryWithFixture:
    @pytest.fixture(params=[
        "semiconductor_profit_protection.json",
        "bond_cash_allocation.json",
        "energy_loss_position.json",
        "mixed_portfolio_rebalance.json",
    ])
    def fixture_data(self, request):
        fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "user_flows")
        path = os.path.join(fixtures_dir, request.param)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_fixture_produces_knowledge_graph_summary(self, fixture_data):
        positions = fixture_data.get("portfolio", {}).get("positions", [])
        fund_profiles = fixture_data.get("fund_profiles", {})
        holdings = fixture_data.get("holdings", {})
        events = fixture_data.get("events", fixture_data.get("catalyst_events"))

        result = build_knowledge_graph_summary(
            positions=positions,
            fund_profiles=fund_profiles,
            holdings=holdings,
            events=events,
        )
        assert "enabled" in result
        assert "fund_count" in result
        assert "limitations" in result


import os
