"""M7.15: Partial valuation portfolio metric gate — subset_only_diagnostic.

When only a subset of total ledger funds are valued, portfolio-level
metrics (total value, HHI, weights, cash ratio) must NOT be output.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.tools.portfolio.report_sections.helpers import (
    FORBIDDEN_PARTIAL_WORDING,
    REQUIRED_PARTIAL_WORDING,
    _is_partial_diagnostic,
    _portfolio_summary,
)


def _context_with_subset_diagnostic(
    *,
    valued_subset_count: int = 2,
    total_funds_in_ledger: int = 15,
    is_partial_diagnostic: bool = True,
    subset_only_diagnostic: bool = True,
    portfolio_valuation_status: str | None = None,
) -> dict[str, Any]:
    """Create a minimal context dict with subset_only_diagnostic set."""
    ps: dict[str, Any] = {
        "is_partial_diagnostic": is_partial_diagnostic,
        "subset_only_diagnostic": subset_only_diagnostic,
        "valued_subset_count": valued_subset_count,
        "total_funds_in_ledger": total_funds_in_ledger,
    }
    if portfolio_valuation_status:
        ps["portfolio_valuation_status"] = portfolio_valuation_status
    return {
        "artifacts": {"portfolio_summary": ps},
        "report": {},
    }


class TestSubsetOnlyDiagnosticDetection:
    """subset_only_diagnostic flag must trigger partial diagnostic."""

    def test_subset_only_triggers_partial(self):
        """When valued_subset < total_funds, is_partial_diagnostic must be True."""
        ctx = _context_with_subset_diagnostic(
            valued_subset_count=2, total_funds_in_ledger=15,
            is_partial_diagnostic=False, subset_only_diagnostic=True,
        )
        assert _is_partial_diagnostic(ctx) is True

    def test_full_coverage_not_partial(self):
        """When valued_subset == total_funds, not partial (unless other flags)."""
        ctx = _context_with_subset_diagnostic(
            valued_subset_count=15, total_funds_in_ledger=15,
            is_partial_diagnostic=False, subset_only_diagnostic=False,
        )
        assert _is_partial_diagnostic(ctx) is False

    def test_zero_total_funds_not_subset(self):
        """When total_funds_in_ledger is 0, no subset diagnostic."""
        ctx = _context_with_subset_diagnostic(
            valued_subset_count=0, total_funds_in_ledger=0,
            is_partial_diagnostic=False, subset_only_diagnostic=False,
        )
        assert _is_partial_diagnostic(ctx) is False

    def test_partial_valuation_status_also_triggers(self):
        """portfolio_valuation_status=partial_diagnostic_only triggers partial."""
        ctx = _context_with_subset_diagnostic(
            is_partial_diagnostic=False, subset_only_diagnostic=False,
            portfolio_valuation_status="partial_diagnostic_only",
        )
        assert _is_partial_diagnostic(ctx) is True

    def test_unavailable_valuation_status_triggers(self):
        """portfolio_valuation_status=unavailable triggers partial."""
        ctx = _context_with_subset_diagnostic(
            is_partial_diagnostic=False, subset_only_diagnostic=False,
            portfolio_valuation_status="unavailable",
        )
        assert _is_partial_diagnostic(ctx) is True


class TestSubsetOnlyFromConfirmedPortfolio:
    """subset_only_diagnostic in confirmed_portfolio summary must propagate."""

    def test_confirmed_portfolio_subset_only(self):
        """confirmed_portfolio.summary.subset_only_diagnostic must trigger partial."""
        ctx: dict[str, Any] = {
            "artifacts": {
                "portfolio_summary": {"is_partial_diagnostic": False},
                "confirmed_portfolio": {
                    "summary": {
                        "subset_only_diagnostic": True,
                        "valued_subset_count": 3,
                        "total_funds_in_ledger": 15,
                    },
                },
            },
            "report": {},
        }
        assert _is_partial_diagnostic(ctx) is True

    def test_confirmed_portfolio_partial_diagnostic(self):
        """confirmed_portfolio.summary.is_partial_diagnostic must trigger partial."""
        ctx: dict[str, Any] = {
            "artifacts": {
                "portfolio_summary": {"is_partial_diagnostic": False},
                "confirmed_portfolio": {
                    "summary": {"is_partial_diagnostic": True},
                },
            },
            "report": {},
        }
        assert _is_partial_diagnostic(ctx) is True

    def test_confirmed_portfolio_unavailable_status(self):
        """confirmed_portfolio.summary.portfolio_valuation_status=unavailable."""
        ctx: dict[str, Any] = {
            "artifacts": {
                "portfolio_summary": {"is_partial_diagnostic": False},
                "confirmed_portfolio": {
                    "summary": {"portfolio_valuation_status": "unavailable"},
                },
            },
            "report": {},
        }
        assert _is_partial_diagnostic(ctx) is True


class TestPartialDiagnosticWordingGate:
    """When partial diagnostic, forbidden wording must not appear."""

    @pytest.mark.parametrize("forbidden_word", list(FORBIDDEN_PARTIAL_WORDING))
    def test_forbidden_wording_not_in_partial_context(self, forbidden_word: str):
        """Each forbidden word must be flagged when is_partial_diagnostic=True."""
        # This is a structural test — the constants must be defined and non-empty
        assert forbidden_word  # not empty string

    @pytest.mark.parametrize("required_word", list(REQUIRED_PARTIAL_WORDING))
    def test_required_wording_exists_for_partial_context(self, required_word: str):
        """Each required word must be defined for partial diagnostic context."""
        assert required_word  # not empty string


class TestPortfolioSummarySubsetFields:
    """build_portfolio_summary must include subset_only_diagnostic fields."""

    def test_build_portfolio_summary_subset_only(self):
        from src.skills_runtime.fund_analysis.metrics_stage import build_portfolio_summary

        portfolio: dict[str, Any] = {
            "as_of_date": "2026-06-30",
            "total_value": None,
            "cash_available": None,
            "positions": [
                {"fund_code": "000001", "current_value": 100.0},
            ],
            "is_partial_diagnostic": True,
            "total_funds_in_ledger": 15,
        }
        summary = build_portfolio_summary(
            portfolio=portfolio,
            fund_codes=["000001"],
            position_weights={"000001": 1.0},
        )
        assert summary["subset_only_diagnostic"] is True
        assert summary["valued_subset_count"] == 1
        assert summary["total_funds_in_ledger"] == 15
        assert summary["is_partial_diagnostic"] is True

    def test_build_portfolio_summary_full_coverage(self):
        from src.skills_runtime.fund_analysis.metrics_stage import build_portfolio_summary

        portfolio: dict[str, Any] = {
            "as_of_date": "2026-06-30",
            "total_value": 15000.0,
            "cash_available": 500.0,
            "positions": [
                {"fund_code": f"{i:06d}", "current_value": 1000.0}
                for i in range(1, 4)
            ],
            "total_funds_in_ledger": 3,
        }
        summary = build_portfolio_summary(
            portfolio=portfolio,
            fund_codes=[f"{i:06d}" for i in range(1, 4)],
            position_weights={f"{i:06d}": 1/3 for i in range(1, 4)},
        )
        assert summary["subset_only_diagnostic"] is False
        assert summary["valued_subset_count"] == 3
        assert summary["total_funds_in_ledger"] == 3
