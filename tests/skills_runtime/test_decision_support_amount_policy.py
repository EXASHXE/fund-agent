"""Tests for decision_support amount calculation policies."""

from src.skills_runtime.decision_support.amount_policy import _calculate_risk_budget, _derive_execution_amount


class TestCalculateRiskBudget:
    def test_explicit_risk_budget(self):
        payload = {"risk_budget": {"risk_budget": 5000.0}}
        result = _calculate_risk_budget(payload, "BUY")
        assert result == 5000.0

    def test_conservative_default(self):
        payload = {"risk_profile": {"risk_level": "conservative"}}
        result = _calculate_risk_budget(payload, "BUY")
        assert result == 0.02

    def test_moderate_default(self):
        payload = {"risk_profile": {"risk_level": "moderate"}}
        result = _calculate_risk_budget(payload, "BUY")
        assert result == 0.05

    def test_aggressive_default(self):
        payload = {"risk_profile": {"risk_level": "aggressive"}}
        result = _calculate_risk_budget(payload, "BUY")
        assert result == 0.10

    def test_passive_action_returns_minimal(self):
        payload = {}
        result = _calculate_risk_budget(payload, "HOLD")
        assert result == 0.01

    def test_no_context_moderate_default(self):
        payload = {}
        result = _calculate_risk_budget(payload, "BUY")
        assert result == 0.05


class TestDeriveExecutionAmount:
    def test_passive_action_returns_zero(self):
        result = _derive_execution_amount("HOLD", {})
        assert result[0] == 0.0

    def test_forbidden_action_returns_zero(self):
        payload = {"constraints": {"forbidden_actions": ["BUY"]}}
        result = _derive_execution_amount("BUY", payload)
        assert result[0] == 0.0

    def test_default_amount_when_no_context(self):
        result = _derive_execution_amount("BUY", {})
        assert result[0] == 10000.0

    def test_capped_by_portfolio_risk(self):
        payload = {
            "portfolio_context": {"total_value": 100000, "cash_available": 50000},
            "risk_profile": {"max_trade_pct": 0.1},
            "risk_budget": {},
            "constraints": {},
        }
        result = _derive_execution_amount("BUY", payload)
        assert result[0] <= 10000.0

    def test_zero_requested_when_below_min(self):
        payload = {
            "portfolio_context": {"total_value": 100},
            "risk_profile": {"max_trade_pct": 0.01},
            "risk_budget": {},
            "constraints": {"min_trade_amount": 50},
        }
        result = _derive_execution_amount("BUY", payload)
        assert result[0] == 0.0
