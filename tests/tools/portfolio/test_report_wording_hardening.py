"""Tests for report wording hardening under partial diagnostic mode (M7.4 Phase 5).

Validates that:
1. Partial mode forbids total valuation wording (总估值, 总浮亏, etc.)
2. Partial mode forbids HHI and concentration metrics
3. Partial mode forbids cash reserve ratio
4. Partial mode suppresses unrealized PnL
5. Partial mode suppresses market-value-dependent risk flags
6. Agent context warns about missing portfolio metrics
"""
from __future__ import annotations

from typing import Any

import pytest

from src.tools.portfolio.report_sections.builders import (
    _build_allocation_and_exposure,
    _build_pnl_and_cost_basis,
    _build_position_contribution,
    _build_professional_diagnostics,
    _build_risk_flags,
)
from src.tools.portfolio.report_sections.helpers import (
    FORBIDDEN_PARTIAL_WORDING,
    REQUIRED_PARTIAL_WORDING,
    _is_partial_diagnostic,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_partial_context(**overrides: Any) -> dict[str, Any]:
    """Build a minimal context that triggers partial diagnostic mode."""
    context: dict[str, Any] = {
        "artifacts": {
            "portfolio_summary": {
                "is_partial_diagnostic": True,
                "portfolio_valuation_status": "partial_diagnostic_only",
            },
        },
        "report": {},
        "data_completeness": {},
        "analysis_coverage": {},
    }
    for key, value in overrides.items():
        if key in ("artifacts", "report", "data_completeness", "analysis_coverage"):
            context[key].update(value)
        else:
            context[key] = value
    return context


def _make_full_context(**overrides: Any) -> dict[str, Any]:
    """Build a minimal context with full valuation (not partial)."""
    context: dict[str, Any] = {
        "artifacts": {
            "portfolio_summary": {
                "portfolio_valuation_status": "estimated_full_coverage",
            },
        },
        "report": {},
        "data_completeness": {},
        "analysis_coverage": {},
    }
    for key, value in overrides.items():
        if key in ("artifacts", "report", "data_completeness", "analysis_coverage"):
            context[key].update(value)
        else:
            context[key] = value
    return context


# ── _is_partial_diagnostic ──────────────────────────────────────────────

class TestIsPartialDiagnostic:
    def test_partial_from_portfolio_summary_flag(self):
        ctx = _make_partial_context()
        assert _is_partial_diagnostic(ctx) is True

    def test_partial_from_portfolio_valuation_status(self):
        ctx = _make_full_context()
        ctx["artifacts"]["portfolio_summary"] = {
            "portfolio_valuation_status": "partial_diagnostic_only",
        }
        assert _is_partial_diagnostic(ctx) is True

    def test_partial_from_confirmed_portfolio(self):
        ctx = _make_full_context()
        ctx["artifacts"]["confirmed_portfolio"] = {
            "summary": {"is_partial_diagnostic": True},
        }
        assert _is_partial_diagnostic(ctx) is True

    def test_not_partial_when_full(self):
        ctx = _make_full_context()
        assert _is_partial_diagnostic(ctx) is False


# ── Forbidden / Required Wording Constants ──────────────────────────────

class TestWordingConstants:
    def test_forbidden_wording_not_empty(self):
        assert len(FORBIDDEN_PARTIAL_WORDING) > 0

    def test_required_wording_not_empty(self):
        assert len(REQUIRED_PARTIAL_WORDING) > 0

    def test_key_forbidden_terms(self):
        assert "总估值" in FORBIDDEN_PARTIAL_WORDING
        assert "HHI" in FORBIDDEN_PARTIAL_WORDING
        assert "现金占比" in FORBIDDEN_PARTIAL_WORDING

    def test_key_required_terms(self):
        assert "已估值部分" in REQUIRED_PARTIAL_WORDING
        assert "partial diagnostic" in REQUIRED_PARTIAL_WORDING
        assert "不能代表组合总市值" in REQUIRED_PARTIAL_WORDING


# ── PnL Section ─────────────────────────────────────────────────────────

class TestPnlPartialMode:
    def test_partial_suppresses_unrealized_pnl(self):
        ctx = _make_partial_context(
            artifacts={
                "pnl_summary": {
                    "unrealized_pnl": 5000.0,
                    "unrealized_pnl_pct": 0.05,
                    "total_cost": 100000.0,
                    "positions": {"000001": {"pnl": 5000.0}},
                },
                "cost_basis_summary": {"000001": {"cost": 100000.0}},
                "portfolio_summary": {
                    "is_partial_diagnostic": True,
                    "portfolio_valuation_status": "partial_diagnostic_only",
                },
            },
        )
        result = _build_pnl_and_cost_basis(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        # Must NOT contain unrealized PnL value
        assert "5,000.00" not in all_text
        # Must contain cost-only wording
        assert "仅成本维度可用" in all_text

    def test_full_mode_shows_unrealized_pnl(self):
        ctx = _make_full_context(
            artifacts={
                "pnl_summary": {
                    "unrealized_pnl": 5000.0,
                    "unrealized_pnl_pct": 0.05,
                    "total_cost": 100000.0,
                },
                "portfolio_summary": {
                    "portfolio_valuation_status": "estimated_full_coverage",
                },
            },
        )
        result = _build_pnl_and_cost_basis(ctx)
        all_text = " ".join(result["bullets"])
        assert "Unrealized PnL" in all_text


# ── Allocation / Concentration Section ──────────────────────────────────

class TestAllocationPartialMode:
    def test_partial_suppresses_hhi_and_weights(self):
        ctx = _make_partial_context(
            report={
                "concentration": {
                    "single_fund_max_weight": 0.45,
                    "hhi": 0.23,
                },
            },
        )
        result = _build_allocation_and_exposure(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        # Must NOT contain HHI value
        assert "0.23" not in all_text
        assert "45.00%" not in all_text
        # Must contain required wording
        assert "权重和集中度需要所有持仓的完整估值覆盖" in all_text

    def test_full_mode_shows_hhi(self):
        ctx = _make_full_context(
            report={
                "concentration": {
                    "single_fund_max_weight": 0.45,
                    "hhi": 0.23,
                },
            },
        )
        result = _build_allocation_and_exposure(ctx)
        all_text = " ".join(result["bullets"])
        assert "HHI" in all_text
        assert "45.00%" in all_text


# ── Position Contribution Section ───────────────────────────────────────

class TestPositionContributionPartialMode:
    def test_partial_suppresses_largest_contributors(self):
        ctx = _make_partial_context(
            artifacts={
                "position_contribution": {
                    "positions": [{"fund_code": "000001"}],
                    "summary": {
                        "largest_value_position": "000001",
                        "largest_profit_contributor": "000001",
                        "largest_loss_contributor": "000002",
                    },
                },
                "portfolio_summary": {
                    "is_partial_diagnostic": True,
                    "portfolio_valuation_status": "partial_diagnostic_only",
                },
            },
        )
        result = _build_position_contribution(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        # Must NOT contain contributor info
        assert "Largest profit contributor" not in all_text
        assert "Largest loss contributor" not in all_text
        assert "Largest value position" not in all_text
        # Must have limitation
        assert "complete valuation coverage" in all_text

    def test_full_mode_shows_contributors(self):
        ctx = _make_full_context(
            artifacts={
                "position_contribution": {
                    "positions": [{"fund_code": "000001"}],
                    "summary": {
                        "largest_profit_contributor": "000001",
                    },
                },
                "portfolio_summary": {
                    "portfolio_valuation_status": "estimated_full_coverage",
                },
            },
        )
        result = _build_position_contribution(ctx)
        all_text = " ".join(result["bullets"])
        assert "Largest profit contributor" in all_text


# ── Risk Flags Section ──────────────────────────────────────────────────

class TestRiskFlagsPartialMode:
    def test_partial_filters_overweight_flag(self):
        ctx = _make_partial_context(
            artifacts={
                "risk_flags": [
                    {"flag_type": "overweight", "severity": "high", "message": "Single fund overweight"},
                    {"flag_type": "redemption_fee", "severity": "medium", "message": "Recent buy within fee window"},
                ],
                "portfolio_summary": {
                    "is_partial_diagnostic": True,
                    "portfolio_valuation_status": "partial_diagnostic_only",
                },
            },
        )
        result = _build_risk_flags(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        # Must mention suppression
        assert "suppressed" in all_text.lower() or "market-value-dependent" in all_text.lower()
        # Must still show non-market-value flags
        assert "Risk flags by severity" in all_text

    def test_partial_filters_cash_reserve_flag(self):
        ctx = _make_partial_context(
            artifacts={
                "risk_flags": [
                    {"flag_type": "cash_reserve_deficit", "severity": "high", "message": "Cash reserve deficit"},
                ],
                "portfolio_summary": {
                    "is_partial_diagnostic": True,
                    "portfolio_valuation_status": "partial_diagnostic_only",
                },
            },
        )
        result = _build_risk_flags(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        assert "suppressed" in all_text.lower() or "market-value-dependent" in all_text.lower()

    def test_full_mode_shows_all_flags(self):
        ctx = _make_full_context(
            artifacts={
                "risk_flags": [
                    {"flag_type": "overweight", "severity": "high", "message": "Single fund overweight"},
                ],
                "portfolio_summary": {
                    "portfolio_valuation_status": "estimated_full_coverage",
                },
            },
        )
        result = _build_risk_flags(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        # No suppression in full mode
        assert "suppressed" not in all_text.lower()


# ── Professional Diagnostics Section ────────────────────────────────────

class TestProfessionalDiagnosticsPartialMode:
    def test_partial_suppresses_cash_ratio(self):
        ctx = _make_partial_context(
            artifacts={
                "professional_diagnostics": {
                    "cash_budget_diagnostics": {
                        "cash_ratio": 0.15,
                        "reserve_gap": 5000.0,
                        "short_term_budget_status": "ok",
                    },
                },
                "portfolio_summary": {
                    "is_partial_diagnostic": True,
                    "portfolio_valuation_status": "partial_diagnostic_only",
                },
            },
        )
        result = _build_professional_diagnostics(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        # Must NOT contain cash ratio value
        assert "15.0%" not in all_text
        assert "Cash ratio is" not in all_text
        assert "5,000" not in all_text
        # Must have limitation
        assert "complete portfolio valuation" in all_text.lower()
        # Budget status is still OK to show
        assert "ok" in all_text

    def test_full_mode_shows_cash_ratio(self):
        ctx = _make_full_context(
            artifacts={
                "professional_diagnostics": {
                    "cash_budget_diagnostics": {
                        "cash_ratio": 0.15,
                        "reserve_gap": 5000.0,
                        "short_term_budget_status": "ok",
                    },
                },
                "portfolio_summary": {
                    "portfolio_valuation_status": "estimated_full_coverage",
                },
            },
        )
        result = _build_professional_diagnostics(ctx)
        all_text = " ".join(result["bullets"])
        assert "Cash ratio is" in all_text
        assert "15.0%" in all_text


# ── Cross-Section: No Forbidden Wording in Partial Mode ─────────────────

class TestNoForbiddenWordingInPartialMode:
    """All sections combined must not contain forbidden wording under partial diagnostic."""

    def test_no_forbidden_wording_in_pnl(self):
        ctx = _make_partial_context(
            artifacts={
                "pnl_summary": {
                    "unrealized_pnl": 5000.0,
                    "unrealized_pnl_pct": 0.05,
                    "total_cost": 100000.0,
                },
                "portfolio_summary": {
                    "is_partial_diagnostic": True,
                    "portfolio_valuation_status": "partial_diagnostic_only",
                },
            },
        )
        result = _build_pnl_and_cost_basis(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        for word in FORBIDDEN_PARTIAL_WORDING:
            assert word not in all_text, f"Forbidden wording '{word}' found in PnL section"

    def test_no_forbidden_wording_in_allocation(self):
        ctx = _make_partial_context(
            report={
                "concentration": {"single_fund_max_weight": 0.5, "hhi": 0.3},
            },
        )
        result = _build_allocation_and_exposure(ctx)
        all_text = " ".join(result["bullets"] + result["limitations"])
        for word in FORBIDDEN_PARTIAL_WORDING:
            assert word not in all_text, f"Forbidden wording '{word}' found in allocation section"
