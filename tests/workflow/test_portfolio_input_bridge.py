"""Tests for portfolio input bridge — deterministic, no network."""

from __future__ import annotations

import pytest

from src.skills_runtime.workflow.portfolio_input_bridge import bridge_portfolio_input


def _demo_input(**overrides):
    base = {
        "schema_version": "fund_portfolio_input.v1",
        "user_question": "分析一下",
        "analysis_mode": "report_only",
        "as_of_date": "2024-12-31",
        "base_currency": "CNY",
        "holdings": [
            {
                "fund_code": "000001",
                "fund_name": "华夏成长混合",
                "current_value": 50000,
                "units": 32700,
                "cost_basis": 45000,
                "cost_basis_confidence": "exact",
                "holding_days": 365,
                "unrealized_pnl": 5000,
                "unrealized_pnl_pct": 11.1,
            },
        ],
        "cash_allocation": {"cash_available": 5000},
        "provider_data_snapshot_ref": "provider_data_snapshot_demo.json",
        "risk_profile_ref": "risk_profile_template.yaml",
        "constraints_ref": "investment_constraints_template.yaml",
        "user_preferences": {"language": "zh-CN", "report_style": "detailed"},
        "data_quality": {"missing_fields": [], "estimated_fields": []},
        "privacy_mode": "full",
    }
    base.update(overrides)
    return base


class TestBridgePortfolioInput:
    def test_complete_input(self):
        result = bridge_portfolio_input(_demo_input())
        assert "payload" in result
        payload = result["payload"]
        assert payload["portfolio"]["total_value"] == 50000
        assert payload["portfolio"]["cash_available"] == 5000
        assert len(payload["portfolio"]["positions"]) == 1
        assert payload["user_question"] == "分析一下"
        assert payload["analysis_mode"] == "report_only"

    def test_missing_cost_basis(self):
        inp = _demo_input()
        inp["holdings"][0]["cost_basis"] = None
        inp["holdings"][0]["cost_basis_confidence"] = "unknown"
        result = bridge_portfolio_input(inp)
        assert any("MISSING_COST_BASIS" in w for w in result["warnings"])

    def test_missing_provider_snapshot(self):
        inp = _demo_input(provider_data_snapshot_ref="")
        result = bridge_portfolio_input(inp)
        assert any("NO_PROVIDER_SNAPSHOT" in w for w in result["warnings"])

    def test_report_only_mode(self):
        result = bridge_portfolio_input(_demo_input(analysis_mode="report_only"))
        assert result["payload"]["analysis_mode"] == "report_only"

    def test_formal_trade_decision_mode(self):
        result = bridge_portfolio_input(_demo_input(analysis_mode="formal_trade_decision"))
        assert any("FORMAL_DECISION_REQUESTED" in w for w in result["warnings"])

    def test_empty_holdings(self):
        result = bridge_portfolio_input(_demo_input(holdings=[]))
        assert any("EMPTY_HOLDINGS" in w for w in result["warnings"])

    def test_privacy_mode(self):
        result = bridge_portfolio_input(_demo_input(privacy_mode="anonymous"))
        assert result["payload"]["privacy_mode"] == "anonymous"

    def test_no_broker_execution_fields(self):
        result = bridge_portfolio_input(_demo_input())
        payload_str = str(result["payload"])
        assert "broker" not in payload_str.lower()
        assert "order" not in payload_str.lower()
        assert "execution" not in payload_str.lower()

    def test_invalid_input(self):
        result = bridge_portfolio_input("not a dict")
        assert any("INVALID_INPUT" in w for w in result["warnings"])

    def test_data_quality_missing_fields(self):
        inp = _demo_input(data_quality={"missing_fields": ["003003.cost_basis"], "estimated_fields": []})
        result = bridge_portfolio_input(inp)
        assert any("DATA_QUALITY_MISSING" in w for w in result["warnings"])
