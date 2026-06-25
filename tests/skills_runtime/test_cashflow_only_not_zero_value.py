"""Tests that cashflow_only / valuation-blocked positions are NOT silently
converted to 0.0 in any stage of the fund_analysis pipeline.

These tests enforce the M7.3 contract rule:
  "cashflow_only 不得进入 P&L / contribution / HHI / max holding / risk flags"
  "current_value=None 不能被转为 0.0"
"""

from __future__ import annotations

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.fund_analysis.cash_deployment_rules import compute_cash_deployment_diagnostics
from src.skills_runtime.fund_analysis.contribution_stage import compute_position_contribution
from src.skills_runtime.fund_analysis.context import CoreMetricsBundle, PortfolioInputBundle
from src.skills_runtime.fund_analysis.metrics_stage import build_portfolio_summary
from src.skills_runtime.fund_analysis.profit_protection_rules import compute_profit_protection_diagnostics
from src.skills_runtime.fund_analysis.safe_parsing import _has_valuation, _position_current_value


def _make_bundle(positions, total_value=15000, fund_codes=None):
    """Create a minimal PortfolioInputBundle with defaults for unused fields."""
    if fund_codes is None:
        fund_codes = [p.get("fund_code", "") for p in positions if isinstance(p, dict) and p.get("fund_code")]
    return PortfolioInputBundle(
        payload={},
        portfolio={"total_value": total_value, "positions": positions},
        positions=positions,
        fund_codes=fund_codes,
        fund_profiles={},
        nav_history={},
        holdings={},
        risk_profile={},
        constraints={},
        transactions=[],
        dca_plans={},
        market_scenario={},
        benchmarks={},
        benchmark_history={},
        peer_group={},
        factor_exposures={},
        manager_profiles={},
        fee_schedules={},
        redemption_rules={},
        research_planning=False,
        nav_data={},
        as_of_date="2026-06-01",
    )


def _make_metrics():
    """Create a minimal CoreMetricsBundle with defaults."""
    return CoreMetricsBundle(
        position_weights={}, concentration={}, exposures={},
        cash_ratio=0.0, industry_exposure={}, fund_type_exposure={},
        fund_metrics={}, risk_flags=[], pnl_summary=None,
        trade_budget=None, short_term_budget=None, dca_review=None,
        normalized_transactions=[], ledger_summary=None,
        cost_basis_summary=None, reconciliation=None, trading_flags=[],
        scenario_flags=[], portfolio_summary={}, rebalance_plan=None,
    )


# ── _has_valuation / _position_current_value ──────────────────────────────


class TestHasValuation:
    def test_returns_false_when_current_value_is_none(self):
        assert _has_valuation({"fund_code": "X"}) is False

    def test_returns_false_when_valuation_type_cashflow_only(self):
        assert _has_valuation({"fund_code": "X", "current_value": 100, "valuation_type": "cashflow_only"}) is False

    def test_returns_false_when_valuation_type_none(self):
        assert _has_valuation({"fund_code": "X", "current_value": 100, "valuation_type": "none"}) is False

    def test_returns_true_when_current_value_present(self):
        assert _has_valuation({"fund_code": "X", "current_value": 100}) is True

    def test_returns_true_when_valuation_type_estimated(self):
        assert _has_valuation({"fund_code": "X", "current_value": 100, "valuation_type": "estimated"}) is True


class TestPositionCurrentValue:
    def test_returns_none_when_no_valuation(self):
        assert _position_current_value({"fund_code": "X"}) is None

    def test_returns_none_when_cashflow_only(self):
        assert _position_current_value({"fund_code": "X", "current_value": 100, "valuation_type": "cashflow_only"}) is None

    def test_returns_float_when_valuation_present(self):
        assert _position_current_value({"fund_code": "X", "current_value": 100}) == 100.0

    def test_returns_none_for_malformed_value(self):
        assert _position_current_value({"fund_code": "X", "current_value": "not_a_number"}) is None


# ── contribution_stage ────────────────────────────────────────────────────


class TestContributionCashflowOnly:
    def _positions(self):
        return [
            {"fund_code": "A", "fund_name": "Fund A", "current_value": 10000, "total_cost": 9000},
            {"fund_code": "B", "fund_name": "Fund B", "current_value": None},
            {"fund_code": "C", "fund_name": "Fund C", "current_value": 5000, "valuation_type": "cashflow_only"},
        ]

    def test_cashflow_only_position_has_none_values(self):
        result = compute_position_contribution(_make_bundle(self._positions()), _make_metrics())
        positions = result["positions"]

        pos_a = next(p for p in positions if p["fund_code"] == "A")
        assert pos_a["current_value"] == 10000
        assert pos_a["absolute_pnl"] == 1000
        assert pos_a["portfolio_weight"] is not None

        pos_b = next(p for p in positions if p["fund_code"] == "B")
        assert pos_b["current_value"] is None
        assert pos_b["absolute_pnl"] is None
        assert pos_b["portfolio_weight"] is None

        pos_c = next(p for p in positions if p["fund_code"] == "C")
        assert pos_c["current_value"] is None
        assert pos_c["absolute_pnl"] is None
        assert pos_c["portfolio_weight"] is None

    def test_cashflow_only_does_not_contribute_to_total_abs_pnl(self):
        result = compute_position_contribution(_make_bundle(self._positions()), _make_metrics())
        positions = result["positions"]
        # Only Fund A has absolute_pnl != None, so total_abs_pnl = |1000|
        pos_a = next(p for p in positions if p["fund_code"] == "A")
        assert pos_a["pnl_contribution_pct"] == 1.0  # 100% of the only PnL


# ── cash_deployment_rules ─────────────────────────────────────────────────


class TestCashDeploymentCashflowOnly:
    def _positions(self):
        return [
            {"fund_code": "A", "current_value": 10000, "total_cost": 9000},
            {"fund_code": "B", "current_value": None, "total_cost": 5000},
            {"fund_code": "C", "current_value": 5000, "valuation_type": "cashflow_only"},
        ]

    def test_cashflow_only_position_has_none_value_and_weight(self):
        result = compute_cash_deployment_diagnostics(_make_bundle(self._positions()), _make_metrics())
        items = result["items"]

        pos_c = next(i for i in items if i.get("bucket") and i["value"] is None)
        assert pos_c["weight"] is None

    def test_position_total_value_excludes_cashflow_only(self):
        result = compute_cash_deployment_diagnostics(_make_bundle(self._positions()), _make_metrics())
        # Only Fund A has valuation (10000), Fund B and C are excluded
        assert result["summary"]["position_total_value"] == 10000.0


# ── profit_protection_rules ───────────────────────────────────────────────


class TestProfitProtectionCashflowOnly:
    def _positions(self):
        return [
            {"fund_code": "A", "fund_name": "Fund A", "current_value": 10000, "total_cost": 9000},
            {"fund_code": "B", "fund_name": "Fund B", "current_value": None, "total_cost": 5000},
            {"fund_code": "C", "fund_name": "Fund C", "current_value": 5000, "valuation_type": "cashflow_only", "total_cost": 4000},
        ]

    def test_cashflow_only_position_has_none_pnl(self):
        result = compute_profit_protection_diagnostics(_make_bundle(self._positions()), _make_metrics())
        items = result["items"]

        pos_c = next(i for i in items if i["fund_code"] == "C")
        assert pos_c["current_value"] is None
        assert pos_c["absolute_pnl"] is None
        assert pos_c["pnl_pct"] is None
        assert pos_c["profit_level"] == "unknown"
        assert pos_c["portfolio_weight"] is None


# ── metrics_stage: build_portfolio_summary ─────────────────────────────────


class TestBuildPortfolioSummaryCashflowOnly:
    def test_detects_valuation_when_positions_have_valuation(self):
        positions = [
            {"fund_code": "A", "current_value": 10000},
            {"fund_code": "B", "current_value": None},
        ]
        summary = build_portfolio_summary(
            {"total_value": 10000, "positions": positions},
            ["A", "B"],
            {},
        )
        assert summary["current_value_likely_missing"] is False

    def test_detects_missing_valuation_when_all_cashflow_only(self):
        positions = [
            {"fund_code": "A", "current_value": None},
            {"fund_code": "B", "current_value": 5000, "valuation_type": "cashflow_only"},
        ]
        summary = build_portfolio_summary(
            {"total_value": 0, "positions": positions},
            ["A", "B"],
            {},
        )
        assert summary["current_value_likely_missing"] is True


# ── Full pipeline: FundAnalysisSkill with cashflow_only ────────────────────


class TestFundAnalysisSkillCashflowOnly:
    def _payload(self):
        return {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 10000.0,
                "positions": [
                    {"fund_code": "A", "fund_name": "Fund A", "current_value": 10000.0, "total_cost": 9000.0},
                    {"fund_code": "B", "fund_name": "Fund B", "current_value": None, "total_cost": 5000.0},
                    {"fund_code": "C", "fund_name": "Fund C", "current_value": 5000.0, "valuation_type": "cashflow_only"},
                ],
            },
            "fund_profiles": {
                "A": {"fund_code": "A", "fund_type": "equity"},
                "B": {"fund_code": "B", "fund_type": "bond"},
                "C": {"fund_code": "C", "fund_type": "money_market"},
            },
            "nav_history": {
                "A": [{"date": "2026-01-01", "nav": 1.0}, {"date": "2026-06-01", "nav": 1.1}],
            },
        }

    def test_skill_output_does_not_convert_none_to_zero(self):
        output = FundAnalysisSkill().run(
            SkillInput(
                task_id="test",
                step_id="test",
                skill_name="fund_analysis",
                payload=self._payload(),
            )
        )
        assert output.status in ("OK", "PARTIAL")
        # Verify that the contribution artifact doesn't have 0.0 for cashflow_only
        contribution = output.artifacts.get("position_contribution", {})
        if contribution:
            positions = contribution.get("positions", [])
            pos_b = next((p for p in positions if p.get("fund_code") == "B"), None)
            pos_c = next((p for p in positions if p.get("fund_code") == "C"), None)
            if pos_b:
                assert pos_b.get("current_value") is None
                assert pos_b.get("absolute_pnl") is None
            if pos_c:
                assert pos_c.get("current_value") is None
                assert pos_c.get("absolute_pnl") is None
