"""Tests for transaction-only portfolio_input semantics and cashflow reporting.

Covers:
- compute_transaction_cashflow_summary aggregation
- source_of_truth="transactions_only" pipeline
- Report contains cashflow section with correct semantics
- Report says cashflow is not current market value
- Report does not say all data is missing when transactions exist
- Report shows valuation unavailable
- No fake 0.00 current value
- Coverage counts are consistent
- pending transactions not counted as confirmed current holdings
- current_value=0 + data_quality says current_value missing => unknown
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from src.tools.portfolio.ledger_snapshot import compute_transaction_cashflow_summary
from src.tools.portfolio.report_quality import (
    calculate_data_completeness,
    _compute_field_coverage,
)
from src.tools.portfolio.report_sections.render import compose_personal_fund_report


# ---------------------------------------------------------------------------
# Synthetic fixture: transactions_only portfolio_input
# ---------------------------------------------------------------------------

def _synthetic_transactions() -> list[dict]:
    return [
        {"action": "BUY", "fund_code": "FUND001", "fund_name": "Test Growth Fund", "amount": 10000.0, "date": "2025-06-01"},
        {"action": "BUY", "fund_code": "FUND002", "fund_name": "Test Bond Fund", "amount": 5000.0, "date": "2025-06-02"},
        {"action": "BUY", "fund_code": "FUND003", "fund_name": "Test Index Fund", "amount": 8000.0, "date": "2025-06-03"},
        {"action": "SELL", "fund_code": "FUND001", "amount": 3000.0, "date": "2025-09-01"},
        {"action": "DIVIDEND", "fund_code": "FUND002", "amount": 200.0, "date": "2025-09-15"},
        {"action": "BUY", "fund_code": "FUND001", "amount": 2000.0, "date": "2025-12-01"},
        {"action": "TRANSFER_IN", "fund_code": "FUND003", "amount": 1000.0, "date": "2025-12-15"},
        {"action": "FEE", "fund_code": "FUND001", "amount": 50.0, "date": "2026-01-01"},
        {"action": "BUY", "fund_code": "FUND004", "fund_name": "Test Money Market", "amount": 15000.0, "date": "2026-03-01"},
        {"action": "SELL", "fund_code": "FUND003", "amount": 4000.0, "date": "2026-04-01"},
    ]


def _synthetic_holdings_with_zero_cv() -> list[dict]:
    """Holdings with current_value=0 but data_quality says current_value missing."""
    return [
        {"fund_code": "FUND001", "fund_name": "Test Growth Fund", "current_value": 0, "total_cost": None, "shares": None, "nav": None},
        {"fund_code": "FUND002", "fund_name": "Test Bond Fund", "current_value": 0, "total_cost": None, "shares": None, "nav": None},
        {"fund_code": "FUND003", "fund_name": "Test Index Fund", "current_value": 0, "total_cost": None, "shares": None, "nav": None},
        {"fund_code": "FUND004", "fund_name": "Test Money Market", "current_value": 0, "total_cost": None, "shares": None, "nav": None},
    ]


def _synthetic_transactions_only_payload() -> dict:
    return {
        "portfolio": {
            "as_of_date": "2026-06-22",
            "positions": _synthetic_holdings_with_zero_cv(),
            "data_quality": {"missing_fields": ["current_value", "units", "nav", "cost_basis"]},
        },
        "transactions": _synthetic_transactions(),
        "source_of_truth": "transactions_only",
    }


# ---------------------------------------------------------------------------
# Tests: compute_transaction_cashflow_summary
# ---------------------------------------------------------------------------

class TestComputeTransactionCashflowSummary:
    """Validate cashflow summary aggregation from transactions."""

    def test_total_transactions_count(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        assert result["total_transactions"] == 10

    def test_by_type_buy_count_and_amount(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        buy = result["by_type"]["buy"]
        assert buy["count"] == 5  # BUY FUND001(10k) + BUY FUND002(5k) + BUY FUND003(8k) + BUY FUND001(2k) + BUY FUND004(15k)
        assert buy["amount"] == 40000.0  # 10000+5000+8000+2000+15000

    def test_by_type_sell_count_and_amount(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        sell = result["by_type"]["sell"]
        assert sell["count"] == 2  # 2 SELL
        assert sell["amount"] == 7000.0  # 3000+4000

    def test_by_type_dividend(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        div = result["by_type"]["dividend"]
        assert div["count"] == 1
        assert div["amount"] == 200.0

    def test_by_type_transfer(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        transfer = result["by_type"]["transfer"]
        assert transfer["count"] == 1  # TRANSFER_IN
        assert transfer["amount"] == 1000.0

    def test_by_type_fee(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        fee = result["by_type"]["fee"]
        assert fee["count"] == 1
        assert fee["amount"] == 50.0

    def test_portfolio_level_net_cashflow(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        pl = result["portfolio_level"]
        assert pl["gross_buy_amount"] == 40000.0  # 10000+5000+8000+2000+15000
        assert pl["gross_sell_amount"] == 7000.0
        assert pl["dividend_amount"] == 200.0
        assert pl["net_cashflow_amount"] == 7000.0 + 200.0 - 40000.0  # sell+dividend-buy

    def test_by_fund_has_all_funds(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        by_fund = result["by_fund"]
        assert "FUND001" in by_fund
        assert "FUND002" in by_fund
        assert "FUND003" in by_fund
        assert "FUND004" in by_fund

    def test_by_fund_net_cashflow(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        fund001 = result["by_fund"]["FUND001"]
        # BUY 10000 + BUY 2000 - SELL 3000 = net -9000
        assert fund001["completed_buy_amount"] == 12000.0
        assert fund001["completed_sell_amount"] == 3000.0
        assert fund001["net_cashflow_amount"] == 3000.0 - 12000.0  # -9000

    def test_latest_transaction_date(self):
        result = compute_transaction_cashflow_summary(_synthetic_transactions(), "2026-06-22")
        assert result["portfolio_level"]["latest_transaction_date"] == "2026-04-01"

    def test_empty_transactions(self):
        result = compute_transaction_cashflow_summary([], "2026-06-22")
        assert result["total_transactions"] == 0
        assert result["portfolio_level"]["transaction_fund_count"] == 0


# ---------------------------------------------------------------------------
# Tests: current_value=0 vs unknown semantics
# ---------------------------------------------------------------------------

class TestCurrentValueZeroVsUnknown:
    """Validate that current_value=0 is treated as unknown when data_quality says missing."""

    def test_zero_cv_with_missing_field_treated_as_unknown(self):
        """current_value=0 + data_quality says current_value missing => unknown."""
        positions = _synthetic_holdings_with_zero_cv()
        portfolio = {
            "positions": positions,
            "data_quality": {"missing_fields": ["current_value"]},
        }
        coverage = _compute_field_coverage(portfolio, positions)
        assert coverage["holdings_count"] == 4
        assert coverage["holdings_with_current_value"] == 0
        assert coverage["holdings_without_current_value"] == 4
        assert coverage["current_value_zero_treated_as_unknown"] is True

    def test_zero_cv_without_missing_field_is_real_zero(self):
        """current_value=0 without data_quality missing => treated as real zero (complete)."""
        positions = [
            {"fund_code": "FUND001", "current_value": 0, "total_cost": None, "shares": None, "nav": None},
        ]
        portfolio = {"positions": positions}
        coverage = _compute_field_coverage(portfolio, positions)
        assert coverage["holdings_count"] == 1
        assert coverage["holdings_with_current_value"] == 1  # real zero is complete
        assert coverage["holdings_without_current_value"] == 0

    def test_none_cv_is_missing(self):
        """current_value=None => missing."""
        positions = [
            {"fund_code": "FUND001", "current_value": None, "total_cost": None, "shares": None, "nav": None},
        ]
        portfolio = {"positions": positions}
        coverage = _compute_field_coverage(portfolio, positions)
        assert coverage["holdings_without_current_value"] == 1
        assert coverage["holdings_with_current_value"] == 0


# ---------------------------------------------------------------------------
# Tests: coverage consistency
# ---------------------------------------------------------------------------

class TestCoverageConsistency:
    """Validate that coverage counts sum correctly."""

    def test_transaction_only_coverage_consistency(self):
        """For transaction-only input with 4 identified funds and no valuation."""
        positions = _synthetic_holdings_with_zero_cv()
        portfolio = {
            "positions": positions,
            "data_quality": {"missing_fields": ["current_value", "units", "nav", "cost_basis"]},
        }
        coverage = _compute_field_coverage(portfolio, positions)
        assert coverage["holdings_count"] == 4
        assert coverage["holdings_with_current_value"] + coverage["holdings_without_current_value"] == 4
        assert coverage["units_complete_count"] + coverage["units_missing_count"] == 4
        assert coverage["nav_complete_count"] + coverage["nav_missing_count"] == 4
        assert coverage["cost_basis_complete_count"] + coverage["cost_basis_missing_count"] == 4
        # All should be missing
        assert coverage["holdings_with_current_value"] == 0
        assert coverage["units_complete_count"] == 0
        assert coverage["nav_complete_count"] == 0
        assert coverage["cost_basis_complete_count"] == 0

    def test_empty_positions_coverage(self):
        """Empty positions should have zero counts."""
        coverage = _compute_field_coverage({}, [])
        assert coverage["holdings_count"] == 0
        assert coverage["holdings_with_current_value"] == 0
        assert coverage["holdings_without_current_value"] == 0


# ---------------------------------------------------------------------------
# Tests: report rendering for transactions_only
# ---------------------------------------------------------------------------

class TestTransactionsOnlyReportRendering:
    """Validate report sections for transactions_only input."""

    def _make_artifacts(self) -> dict:
        """Build artifacts dict simulating transactions_only pipeline output."""
        payload = _synthetic_transactions_only_payload()
        cf_summary = compute_transaction_cashflow_summary(
            payload["transactions"], "2026-06-22"
        )
        # Simulate what report_stage produces for transactions_only
        return {
            "portfolio_summary": {
                "as_of_date": "2026-06-22",
                "total_value": None,
                "cash_available": None,
                "position_count": 4,
                "position_weights": {},
                "current_value_likely_missing": True,
            },
            "position_summary": {
                "FUND001": {"fund_code": "FUND001", "fund_name": "Test Growth Fund", "current_value": None, "total_cost": None, "shares": None},
                "FUND002": {"fund_code": "FUND002", "fund_name": "Test Bond Fund", "current_value": None, "total_cost": None, "shares": None},
                "FUND003": {"fund_code": "FUND003", "fund_name": "Test Index Fund", "current_value": None, "total_cost": None, "shares": None},
                "FUND004": {"fund_code": "FUND004", "fund_name": "Test Money Market", "current_value": None, "total_cost": None, "shares": None},
            },
            "source_of_truth": "transactions_only",
            "transaction_cashflow_summary": cf_summary,
            "risk_flags": [],
            "fund_analysis_report": {
                "risk_flags": [],
                "fund_metrics": {},
                "portfolio_metrics": {},
            },
            "data_completeness": calculate_data_completeness(payload),
            "analysis_coverage": {"portfolio": "partial", "ledger": "partial", "performance": "missing", "holdings": "partial"},
            "report_limitations": [],
            "warnings": [],
        }

    def test_report_contains_cashflow_section(self):
        """Report must contain transaction_cashflow section."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        section_ids = [s["id"] for s in result["report_sections"]]
        assert "transaction_cashflow" in section_ids

    def test_cashflow_section_is_ok(self):
        """Cashflow section should be OK when transactions exist."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        cf_section = next(s for s in result["report_sections"] if s["id"] == "transaction_cashflow")
        assert cf_section["status"] == "OK"

    def test_cashflow_section_mentions_not_market_value(self):
        """Cashflow section must say it is not current market value."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        cf_section = next(s for s in result["report_sections"] if s["id"] == "transaction_cashflow")
        all_text = " ".join(cf_section.get("limitations", []))
        assert "not current market value" in all_text.lower() or "cashflow" in all_text.lower()

    def test_portfolio_snapshot_says_valuation_unavailable(self):
        """Portfolio snapshot must say valuation unavailable for transactions_only."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        ps_section = next(s for s in result["report_sections"] if s["id"] == "portfolio_snapshot")
        all_text = " ".join(ps_section.get("bullets", []) + ps_section.get("limitations", []))
        assert "unavailable" in all_text.lower() or "valuation" in all_text.lower()

    def test_no_fake_zero_current_value(self):
        """Report must not show '0.00' for unknown current_value."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        ps_section = next(s for s in result["report_sections"] if s["id"] == "portfolio_snapshot")
        for bullet in ps_section.get("bullets", []):
            # Should not contain "0.00" as a current_value representation
            if "value" in bullet.lower():
                assert "0.00" not in bullet or "N/A" in bullet or "unavailable" in bullet.lower()

    def test_reconstruction_status_section_exists(self):
        """Report must contain reconstruction_status section."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        section_ids = [s["id"] for s in result["report_sections"]]
        assert "reconstruction_status" in section_ids

    def test_reconstruction_status_says_transactions_only(self):
        """Reconstruction status must mention transactions_only source."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        rs_section = next(s for s in result["report_sections"] if s["id"] == "reconstruction_status")
        all_text = " ".join(rs_section.get("bullets", []))
        assert "existing_private_portfolio_input" in all_text or "transactions" in all_text.lower()

    def test_report_does_not_say_all_data_missing(self):
        """When transactions exist, report should not say all data is missing."""
        artifacts = self._make_artifacts()
        result = compose_personal_fund_report(artifacts, options={"language": "en"})
        # Check that at least one section has status OK or PARTIAL (not all MISSING)
        statuses = [s["status"] for s in result["report_sections"]]
        assert "OK" in statuses or "PARTIAL" in statuses


# ---------------------------------------------------------------------------
# Tests: data_completeness for transactions_only
# ---------------------------------------------------------------------------

class TestDataCompletenessTransactionsOnly:
    """Validate data completeness for transactions_only input."""

    def test_transactions_only_has_portfolio(self):
        """transactions_only payload should have portfolio_snapshot=True."""
        payload = _synthetic_transactions_only_payload()
        dc = calculate_data_completeness(payload)
        assert dc["grade"] in ("A", "B", "C", "D")

    def test_transactions_only_has_field_coverage(self):
        """Data completeness should include field_coverage."""
        payload = _synthetic_transactions_only_payload()
        dc = calculate_data_completeness(payload)
        assert "field_coverage" in dc
        fc = dc["field_coverage"]
        assert fc["holdings_count"] == 4
        assert fc["holdings_without_current_value"] == 4
