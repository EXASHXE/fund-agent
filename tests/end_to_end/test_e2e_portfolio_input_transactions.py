"""End-to-end tests for portfolio_input.transactions fallback in E2E pipeline.

Tests the integration of portfolio_input.transactions as a transaction source
when no Alipay CSV is available. All data is synthetic.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.tools.portfolio.portfolio_input_transactions import (
    build_ledger_from_portfolio_input_transactions,
    load_portfolio_input_transactions,
    validate_portfolio_input_transactions,
)


def _make_portfolio_input_with_transactions(
    tmp_path: Path,
    transactions: list[dict[str, Any]],
    holdings: list[dict[str, Any]] | None = None,
) -> Path:
    """Create a synthetic portfolio_input.private.json with transactions."""
    data: dict[str, Any] = {
        "schema_version": "portfolio_input.v1",
        "as_of_date": "2026-06-30",
        "transactions": transactions,
    }
    if holdings:
        data["holdings"] = holdings
    p = tmp_path / "portfolio_input.private.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ── Scenario A: Transactions only, no holdings ────────────────────────


class TestScenarioATransactionsOnly:
    """portfolio_input has transactions, no Alipay CSV, no holdings."""

    def test_ledger_built_from_transactions(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-15", "fund_code": "000002", "transaction_type": "buy", "amount": 200.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        assert len(loaded) == 2

        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        assert ledger["summary"]["total_transactions"] == 2
        assert ledger["summary"]["with_fund_code"] == 2
        assert ledger["source"] == "portfolio_input_transactions"

    def test_transaction_source_is_portfolio_input(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        txn = ledger["transactions"][0]
        assert txn["source"] == "portfolio_input.transactions"
        assert txn["confirmation_source"] == "portfolio_input_transactions"


# ── Scenario B: Transactions + identity overrides, no NAV ──────────────


class TestScenarioBTransactionsWithIdentityNoNAV:
    """Transactions have fund_codes but no NAV for reconstruction."""

    def test_valid_codes_counted(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-02", "fund_code": "000002", "transaction_type": "buy", "amount": 200.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        validation = validate_portfolio_input_transactions(loaded)
        assert validation["with_fund_code"] == 2
        assert validation["valid"] == 2


# ── Scenario C: Transactions with NAV ─────────────────────────────────


class TestScenarioCTransactionsWithNAV:
    """Transactions with NAV data enable reconstruction."""

    def test_with_nav_and_units(self, tmp_path: Path):
        txns = [
            {
                "trade_date": "2026-06-01",
                "fund_code": "000001",
                "transaction_type": "buy",
                "amount": 100.0,
                "units": 81.0,
                "nav": 1.2345,
            },
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        txn = ledger["transactions"][0]
        assert txn["units"] == 81.0
        assert txn["nav"] == 1.2345
        assert ledger["summary"]["with_units"] == 1
        assert ledger["summary"]["with_nav"] == 1


# ── Scenario D: Transactions + holdings fallback ──────────────────────


class TestScenarioDTransactionsWithHoldings:
    """Transactions provide cashflow, holdings provide valuation."""

    def test_both_loaded(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        holdings = [
            {"fund_code": "000001", "fund_name": "示例基金A", "units": 81.0, "current_value": 100.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns, holdings)
        loaded = load_portfolio_input_transactions(path)
        assert len(loaded) == 1

        # Verify the portfolio_input file has both
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "transactions" in data
        assert "holdings" in data


# ── Scenario E: Name-only transactions ────────────────────────────────


class TestScenarioENameOnlyTransactions:
    """Transactions with fund_name but no fund_code."""

    def test_name_only_counted(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_name": "仅有名称的基金", "transaction_type": "buy", "amount": 100.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        assert ledger["summary"]["name_only"] == 1
        assert ledger["summary"]["with_fund_code"] == 0

    def test_no_chinese_name_in_fund_code(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_name": "中文名基金", "transaction_type": "buy", "amount": 100.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        txn = ledger["transactions"][0]
        assert txn["fund_code"] is None
        assert txn["fund_name"] == "中文名基金"


# ── Scenario F: Invalid transactions ──────────────────────────────────


class TestScenarioFInvalidTransactions:
    """Invalid transactions produce warnings but don't crash."""

    def test_bad_date_warning(self, tmp_path: Path):
        txns = [
            {"trade_date": "bad", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        assert len(ledger["warnings"]) > 0
        assert any("trade_date" in w for w in ledger["warnings"])

    def test_bad_amount_warning(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": "bad"},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        assert any("amount" in w for w in ledger["warnings"])

    def test_bad_fund_code_warning(self, tmp_path: Path):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "ABC", "transaction_type": "buy", "amount": 100.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        assert any("fund_code" in w for w in ledger["warnings"])

    def test_no_crash_on_completely_invalid(self, tmp_path: Path):
        txns = [{}]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)
        assert len(ledger["transactions"]) == 1

    def test_validation_no_private_data_leaked(self, tmp_path: Path):
        txns = [
            {"trade_date": "bad", "fund_code": "ABC", "transaction_type": "buy", "amount": "bad"},
        ]
        result = validate_portfolio_input_transactions(txns)
        output = json.dumps(result, default=str)
        # No real fund names, amounts, or IDs in validation output
        assert "ABC" not in output  # fund_code values not in output


# ── Scenario G: Alipay path regression ────────────────────────────────


class TestScenarioGAlipayRegression:
    """Verify Alipay CSV path still works when both exist."""

    def test_load_from_portfolio_input_does_not_require_alipay(self, tmp_path: Path):
        """portfolio_input.transactions can be loaded independently."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        assert len(loaded) == 1
        # This should work even without any Alipay CSV present


# ── Scenario H: Validation visibility in E2E summary ─────────────────────


class TestScenarioHValidationVisibility:
    """Validation warnings must surface in e2e_summary and not leak private data."""

    def test_e2e_summary_surfaces_portfolio_input_warning_counts(self, tmp_path: Path):
        """portfolio_input.transactions with invalid rows → e2e_summary warning_count > 0,
        warnings list has counts-only hint, no real field values leaked."""
        txns = [
            {"trade_date": "bad-date", "fund_code": "ABC", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000002", "transaction_type": "badtype", "amount": "bad"},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)

        # Simulate what e2e_summary would contain
        pi_summary = ledger.get("summary", {})
        assert pi_summary["warning_count"] > 0
        assert pi_summary["manual_review_count"] > 0

        # Warnings must not contain real fund names or amounts
        # (transaction_type labels like 'badtype' are not private data)
        warning_text = " ".join(ledger.get("warnings", []))
        assert "ABC" not in warning_text  # fund_code values not leaked
        assert "100.0" not in warning_text  # amounts not leaked

    def test_e2e_invalid_portfolio_input_transactions_status_partial(self, tmp_path: Path):
        """When portfolio_input.transactions has valid + invalid rows,
        status should reflect partial parsing."""
        txns = [
            {"trade_date": "bad-date", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000002", "transaction_type": "buy", "amount": 200.0},
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)

        # Some valid, some invalid → partial
        assert ledger["summary"]["valid_count"] >= 1
        assert ledger["summary"]["invalid_count"] >= 1
        assert ledger["summary"]["total_transactions"] == 2

        # Source should still be portfolio_input_transactions
        assert ledger["source"] == "portfolio_input_transactions"


# ── Scenario I: Privacy redaction in E2E summary ──────────────────────


class TestScenarioIPrivacyRedaction:
    """E2E summary warnings must be counts-only, no raw user input."""

    def test_e2e_summary_warning_is_counts_only(self, tmp_path: Path):
        """Invalid transaction_type must not appear in e2e_summary warnings."""
        txns = [
            {
                "trade_date": "2026-06-01",
                "fund_code": "000001",
                "fund_name": "Sensitive Fund Name",
                "transaction_type": "private_type_xyz",
                "amount": 99999.99,
            },
            {
                "trade_date": "2026-06-01",
                "fund_code": "000002",
                "transaction_type": "buy",
                "amount": 100.0,
            },
        ]
        path = _make_portfolio_input_with_transactions(tmp_path, txns)
        loaded = load_portfolio_input_transactions(path)
        ledger = build_ledger_from_portfolio_input_transactions(loaded)

        # Warnings must exist (unknown type)
        assert ledger["summary"]["warning_count"] > 0

        # Warnings must not contain raw user input
        warning_text = " ".join(ledger.get("warnings", []))
        assert "private_type_xyz" not in warning_text
        assert "Sensitive Fund Name" not in warning_text
        assert "99999.99" not in warning_text
