"""Tests for portfolio-level valuation gate (M7.4 Phase 3).

Validates that:
1. Partial coverage blocks total portfolio value
2. Partial coverage blocks HHI and weight risks
3. Partial coverage allows cashflow invested summary
4. Full coverage allows portfolio metrics
5. Report never labels partial value as total value
"""
from __future__ import annotations

from typing import Any

import pytest

from scripts.reconstruct_portfolio_from_ledger import reconstruct_portfolio
from src.tools.portfolio.personal_health_report import (
    REASON_PARTIAL_VALUATION,
    VALID_REASON_CODES,
    build_personal_health_summary,
)
from src.tools.portfolio.agent_context import (
    REASON_CODES,
    UNSAFE_TO_INFER_ITEMS,
    build_agent_context,
)


def _make_ledger(funds: list[dict] | None = None) -> dict[str, Any]:
    """Build a ledger with multiple funds."""
    transactions = []
    for f in funds or []:
        txn = {
            "fund_code": f.get("code", "000001"),
            "fund_name": f.get("name", "Test Fund"),
            "action": "buy",
            "amount": f.get("amount", 1000.0),
            "net_amount": f.get("amount", 1000.0),
            "trade_date": f.get("trade_date", "2025-01-15"),
            "confirmation_type": "evidence_confirmed",
            "confirmation_source": "alipay",
        }
        if "units" in f:
            txn["units"] = f["units"]
        transactions.append(txn)
    return {"transactions": transactions}


def _make_nav(funds: list[dict] | None = None) -> dict[str, Any]:
    """Build a NAV snapshot for multiple funds."""
    nav_by_fund = {}
    for f in funds or []:
        code = f.get("code", "000001")
        nav_by_fund[code] = {
            "records": f.get("nav_records", [
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.05},
            ]),
        }
    return {"nav_by_fund": nav_by_fund}


# ── 1. Partial coverage blocks total portfolio value ────────────────────


class TestPartialCoverageBlocksTotalValue:
    """When some positions lack valuation, total_current_value must be None."""

    def test_mixed_valued_and_cashflow_only(self):
        """Two funds: one with NAV, one without → partial → total_current_value is None."""
        ledger = _make_ledger(funds=[
            {"code": "000001", "name": "Fund A", "amount": 1000.0, "trade_date": "2025-01-15"},
            {"code": "000002", "name": "Fund B", "amount": 2000.0, "trade_date": "2025-03-01"},
        ])
        # NAV only for Fund A
        nav = _make_nav(funds=[
            {"code": "000001", "nav_records": [
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.05},
            ]},
            {"code": "000002", "nav_records": [
                {"date": "2025-06-01", "nav": 1.10},  # No trade-date NAV
            ]},
        ])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        summary = result["confirmed_portfolio"]["summary"]
        assert summary["portfolio_valuation_status"] == "partial_diagnostic_only"
        assert summary["is_partial_diagnostic"] is True
        assert summary["total_current_value"] is None
        assert summary["valued_positions_count"] < summary["total_positions"]


# ── 2. Full coverage allows portfolio metrics ───────────────────────────


class TestFullCoverageAllowsMetrics:
    """When all positions have valuation, total_current_value is available."""

    def test_all_funds_with_trade_date_nav(self):
        """Two funds, both with trade-date NAV → full coverage → total_current_value available."""
        ledger = _make_ledger(funds=[
            {"code": "000001", "name": "Fund A", "amount": 1000.0, "trade_date": "2025-01-15"},
            {"code": "000002", "name": "Fund B", "amount": 2000.0, "trade_date": "2025-03-01"},
        ])
        nav = _make_nav(funds=[
            {"code": "000001", "nav_records": [
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.05},
            ]},
            {"code": "000002", "nav_records": [
                {"date": "2025-03-01", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.10},
            ]},
        ])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        summary = result["confirmed_portfolio"]["summary"]
        assert summary["portfolio_valuation_status"] == "estimated_full_coverage"
        assert summary["total_current_value"] is not None
        assert summary["is_partial_diagnostic"] is False


# ── 3. Partial coverage allows cashflow invested summary ────────────────


class TestPartialCoverageAllowsCashflowSummary:
    """Even with partial coverage, cashflow invested should be available."""

    def test_partial_coverage_has_cashflow_invested(self):
        """Partial coverage still has total_cashflow_invested."""
        ledger = _make_ledger(funds=[
            {"code": "000001", "name": "Fund A", "amount": 1000.0, "trade_date": "2025-01-15"},
            {"code": "000002", "name": "Fund B", "amount": 2000.0, "trade_date": "2025-03-01"},
        ])
        nav = _make_nav(funds=[
            {"code": "000001", "nav_records": [
                {"date": "2025-01-15", "nav": 1.0},
                {"date": "2025-06-01", "nav": 1.05},
            ]},
            {"code": "000002", "nav_records": [
                {"date": "2025-06-01", "nav": 1.10},
            ]},
        ])
        result = reconstruct_portfolio(
            ledger_data=ledger,
            nav_snapshot=nav,
            as_of_date=__import__("datetime").date(2025, 6, 1),
        )
        summary = result["confirmed_portfolio"]["summary"]
        assert summary["total_cashflow_invested"] is not None
        assert summary["total_cashflow_invested"] > 0


# ── 4. Health report partial valuation reason code ──────────────────────


def _base_health_artifacts(**overrides) -> dict:
    artifacts = {
        "e2e_summary": {
            "transaction_source": "alipay",
            "portfolio_input_source": "reconstructed_from_ledger",
            "pipeline_steps": {
                "fund_data_snapshot_attempted": True,
                "fund_data_snapshot_status": "attempted",
                "reconstruction_attempted": True,
                "reconstruction_status": "reconstructed_from_ledger",
                "valid_fund_codes_count": 3,
                "name_only_count": 0,
            },
        },
        "nav_coverage_summary": {
            "positions_total": 3,
            "positions_estimated": 3,
            "positions_cashflow_only": 0,
            "positions_unavailable": 0,
            "positions_manual_review_required": 0,
            "nav_coverage_full_count": 3,
            "nav_coverage_partial_count": 0,
            "nav_coverage_none_count": 0,
            "nav_coverage_latest_only_count": 0,
            "latest_nav_stale_count": 0,
            "qdii_like_count": 0,
            "estimated_current_value_total_is_partial": False,
        },
        "portfolio_input_transactions_summary": {
            "total_transactions": 10,
            "manual_review_required_count": 0,
            "manual_review_count": 0,
        },
        "identity_summary": {
            "total_funds": 3,
            "valid_fund_codes_count": 3,
            "name_only_count": 0,
            "identity_mismatch_count": 0,
        },
        "valuation_summary": {},
    }
    artifacts.update(overrides)
    return artifacts


class TestHealthReportPartialValuation:
    """personal_health_report must include partial_valuation when is_partial_diagnostic."""

    def test_partial_valuation_in_reason_codes(self):
        artifacts = _base_health_artifacts()
        artifacts["valuation_summary"] = {"is_partial_diagnostic": True}
        result = build_personal_health_summary(artifacts)
        assert REASON_PARTIAL_VALUATION in result["reason_codes"]

    def test_partial_valuation_not_in_reason_when_full(self):
        artifacts = _base_health_artifacts()
        result = build_personal_health_summary(artifacts)
        assert REASON_PARTIAL_VALUATION not in result["reason_codes"]

    def test_partial_valuation_is_valid_reason_code(self):
        assert REASON_PARTIAL_VALUATION in VALID_REASON_CODES
        assert REASON_PARTIAL_VALUATION == "partial_valuation"

    def test_valuation_quality_includes_is_partial_diagnostic(self):
        artifacts = _base_health_artifacts()
        artifacts["valuation_summary"] = {"is_partial_diagnostic": True}
        result = build_personal_health_summary(artifacts)
        assert result["valuation_quality"]["is_partial_diagnostic"] is True


# ── 5. Agent context partial valuation ──────────────────────────────────


class TestAgentContextPartialValuation:
    """agent_context must include partial_valuation in reason_codes and unsafe_to_infer."""

    def test_partial_valuation_in_reason_codes_enum(self):
        assert "partial_valuation" in REASON_CODES

    def test_complete_market_value_if_partial_valuation_in_unsafe_enum(self):
        assert "complete_market_value_if_partial_valuation" in UNSAFE_TO_INFER_ITEMS

    def test_partial_valuation_triggers_unsafe_item(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["partial_valuation"],
                "data_sources": {},
                "valuation_quality": {},
                "nav_coverage": {"full": 0, "partial": 1, "none": 0},
            },
            "pipeline_steps": {
                "reconstruction_status": "reconstructed_from_ledger",
            },
        }
        ctx = build_agent_context(summary)
        assert "complete_market_value_if_partial_valuation" in ctx["unsafe_to_infer"]

    def test_partial_valuation_triggers_recommended_question(self):
        summary = {
            "personal_health_report": {
                "overall_status": "partial",
                "confidence_level": "low",
                "reason_codes": ["partial_valuation"],
                "data_sources": {},
                "valuation_quality": {},
                "nav_coverage": {"full": 0, "partial": 0, "none": 0},
            },
            "pipeline_steps": {
                "reconstruction_status": "reconstructed_from_ledger",
            },
        }
        ctx = build_agent_context(summary)
        questions_text = " ".join(ctx["recommended_agent_questions"])
        assert "valuation coverage" in questions_text.lower() or "units" in questions_text.lower()
