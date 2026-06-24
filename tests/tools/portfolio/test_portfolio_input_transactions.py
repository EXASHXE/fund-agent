"""Tests for portfolio_input.transactions → ledger adapter.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.tools.portfolio.portfolio_input_transactions import (
    build_ledger_from_portfolio_input_transactions,
    load_portfolio_input_transactions,
    normalize_portfolio_input_transaction,
    validate_portfolio_input_transactions,
)


# ── Unit tests: normalize_portfolio_input_transaction ──────────────────


class TestNormalizeTransaction:
    def test_valid_buy(self):
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "fund_name": "示例基金A",
            "transaction_type": "buy",
            "amount": 100.00,
            "units": 81.00,
            "nav": 1.2345,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "buy"
        assert result["fund_code"] == "000001"
        assert result["trade_date"] == "2026-06-01"
        assert result["amount"] == 100.0
        assert result["units"] == 81.0
        assert result["nav"] == 1.2345
        assert result["source"] == "portfolio_input.transactions"
        assert result["confirmation_type"] == "user_provided_private_input"
        assert result["confirmation_source"] == "portfolio_input_transactions"
        assert result["confidence"] == "user_provided"
        assert result["transaction_id"] == "pi_txn_000000"

    def test_name_only_transaction(self):
        raw = {
            "trade_date": "2026-06-01",
            "fund_name": "仅有名称的基金",
            "transaction_type": "buy",
            "amount": 200.00,
        }
        result = normalize_portfolio_input_transaction(raw, 5)
        assert result["fund_code"] is None
        assert result["fund_name"] == "仅有名称的基金"
        assert result["normalized_name"] == "仅有名称的基金"

    def test_invalid_fund_code_warning(self):
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "ABC123",
            "transaction_type": "buy",
            "amount": 100.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["fund_code"] is None
        assert any("not 6 digits" in w for w in result.get("warnings", []))

    def test_invalid_date_warning(self):
        raw = {
            "trade_date": "06-01-2026",
            "fund_code": "000001",
            "transaction_type": "buy",
            "amount": 100.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert any("trade_date" in w for w in result.get("warnings", []))

    def test_unknown_transaction_type(self):
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "redeem",
            "amount": 100.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "unknown"
        assert any("unknown transaction_type" in w for w in result.get("warnings", []))
        # Raw type value must NOT appear in warnings
        assert not any("redeem" in w for w in result.get("warnings", []))

    def test_conversion_type_maps_to_conversion(self):
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "conversion_in",
            "amount": 100.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "conversion"
        assert result.get("ambiguous_portfolio_effect") is True

    def test_refund_type_maps_to_refund(self):
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "refund",
            "amount": 50.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "refund"
        assert result.get("ambiguous_portfolio_effect") is True

    def test_missing_amount_warning(self):
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "buy",
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert any("amount" in w for w in result.get("warnings", []))

    def test_empty_fund_code_is_not_flagged(self):
        """Empty fund_code is allowed (identity not yet resolved)."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "",
            "fund_name": "Unresolved Fund",
            "transaction_type": "buy",
            "amount": 100.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["fund_code"] is None
        assert "not 6 digits" not in str(result.get("warnings", []))

    def test_no_fund_code_key_is_ok(self):
        """Missing fund_code key is fine."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_name": "No Code Fund",
            "transaction_type": "buy",
            "amount": 100.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["fund_code"] is None


# ── Unit tests: build_ledger_from_portfolio_input_transactions ─────────


class TestBuildLedger:
    def test_basic_ledger(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-02", "fund_code": "000002", "transaction_type": "sell", "amount": 50.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["schema_version"] == "transaction_ledger.v1"
        assert result["source"] == "portfolio_input_transactions"
        assert len(result["transactions"]) == 2
        assert result["summary"]["total_transactions"] == 2
        assert result["summary"]["with_fund_code"] == 2
        assert result["summary"]["name_only"] == 0

    def test_name_only_counted(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_name": "Name Only Fund", "transaction_type": "buy", "amount": 100.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["name_only"] == 1
        assert result["summary"]["with_fund_code"] == 0

    def test_sorted_by_trade_date(self):
        txns = [
            {"trade_date": "2026-06-15", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 50.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        dates = [t["trade_date"] for t in result["transactions"]]
        assert dates == ["2026-06-01", "2026-06-15"]

    def test_with_units_and_nav(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0, "units": 81.0, "nav": 1.2345},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        txn = result["transactions"][0]
        assert txn["units"] == 81.0
        assert txn["shares"] == 81.0
        assert txn["nav"] == 1.2345

    def test_ambiguous_portfolio_effect_flagged(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "conversion_in", "amount": 100.0},
            {"trade_date": "2026-06-02", "fund_code": "000001", "transaction_type": "refund", "amount": 50.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["ambiguous_portfolio_effect"] == 2

    def test_invalid_entries_still_included(self):
        txns = [
            {"trade_date": "bad-date", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert len(result["transactions"]) == 1
        assert len(result["warnings"]) > 0


# ── Unit tests: validate_portfolio_input_transactions ──────────────────


class TestValidateTransactions:
    def test_all_valid(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-02", "fund_code": "000002", "transaction_type": "sell", "amount": 50.0},
        ]
        result = validate_portfolio_input_transactions(txns)
        assert result["total"] == 2
        assert result["valid"] == 2
        assert result["invalid_fund_code"] == 0
        assert result["invalid_date"] == 0
        assert result["invalid_amount"] == 0

    def test_invalid_fund_code(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "ABC", "transaction_type": "buy", "amount": 100.0},
        ]
        result = validate_portfolio_input_transactions(txns)
        assert result["invalid_fund_code"] == 1

    def test_invalid_date(self):
        txns = [
            {"trade_date": "01-15-2026", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        result = validate_portfolio_input_transactions(txns)
        assert result["invalid_date"] == 1

    def test_invalid_amount(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": "not_a_number"},
        ]
        result = validate_portfolio_input_transactions(txns)
        assert result["invalid_amount"] == 1

    def test_name_only_counted(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_name": "Name Only", "transaction_type": "buy", "amount": 100.0},
        ]
        result = validate_portfolio_input_transactions(txns)
        assert result["name_only"] == 1
        assert result["with_fund_code"] == 0

    def test_empty_list(self):
        result = validate_portfolio_input_transactions([])
        assert result["total"] == 0
        assert result["valid"] == 0


# ── Unit tests: load_portfolio_input_transactions ──────────────────────


class TestLoadTransactions:
    def test_load_from_file(self, tmp_path: Path):
        data = {
            "transactions": [
                {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            ]
        }
        p = tmp_path / "portfolio_input.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = load_portfolio_input_transactions(p)
        assert len(result) == 1

    def test_missing_file(self, tmp_path: Path):
        result = load_portfolio_input_transactions(tmp_path / "nonexistent.json")
        assert result == []

    def test_no_transactions_key(self, tmp_path: Path):
        p = tmp_path / "portfolio_input.json"
        p.write_text(json.dumps({"holdings": []}), encoding="utf-8")
        result = load_portfolio_input_transactions(p)
        assert result == []

    def test_invalid_json(self, tmp_path: Path):
        p = tmp_path / "portfolio_input.json"
        p.write_text("not json", encoding="utf-8")
        result = load_portfolio_input_transactions(p)
        assert result == []


# ── Integration: ledger format compatibility ───────────────────────────


class TestLedgerCompatibility:
    def test_ledger_has_required_fields_for_reconstruction(self):
        """Verify output has all fields expected by reconstruct_portfolio_from_ledger.py."""
        txns = [
            {
                "trade_date": "2026-06-01",
                "fund_code": "000001",
                "fund_name": "示例基金A",
                "transaction_type": "buy",
                "amount": 100.0,
                "units": 81.0,
                "nav": 1.2345,
            },
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        txn = result["transactions"][0]

        # Fields expected by reconstruct_portfolio_from_ledger.py
        required_fields = ["transaction_id", "fund_code", "fund_name", "trade_date", "action", "amount"]
        for field in required_fields:
            assert field in txn, f"Missing required field: {field}"

        # Confirmation fields expected by the pipeline
        assert "confirmation_type" in txn
        assert "confirmation_source" in txn
        assert "confidence" in txn

    def test_ledger_output_is_json_serializable(self):
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        text = json.dumps(result, default=str)
        parsed = json.loads(text)
        assert parsed["summary"]["total_transactions"] == 1

    def test_no_private_data_in_ledger_output(self):
        """Ledger output must not contain real transaction IDs or notes."""
        txns = [
            {
                "trade_date": "2026-06-01",
                "fund_code": "000001",
                "fund_name": "示例基金A",
                "transaction_type": "buy",
                "amount": 100.0,
                "source": "manual_private_input",
                "note": "user private note",
            },
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        txn = result["transactions"][0]
        # source should be overridden to portfolio_input.transactions
        assert txn["source"] == "portfolio_input.transactions"
        # note should not be propagated
        assert "note" not in txn


# ── Validation visibility tests ───────────────────────────────────────


class TestValidationVisibility:
    def test_adapter_summary_counts_validation_warnings(self):
        """Summary must include warning_count, invalid_count, and per-type counts."""
        txns = [
            {"trade_date": "bad-date", "fund_code": "ABC", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000002", "transaction_type": "badtype", "amount": "bad"},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        s = result["summary"]
        assert s["total_transactions"] == 3
        assert s["valid_count"] == 1
        assert s["invalid_count"] == 2
        assert s["warning_count"] > 0
        assert s["invalid_fund_code_count"] == 1
        assert s["invalid_date_count"] == 1
        assert s["invalid_amount_count"] == 1
        assert s["unknown_transaction_type_count"] == 1
        assert s["manual_review_count"] == 2

    def test_warning_text_no_sensitive_content(self):
        """Warning text must not contain real fund names, amounts, or notes."""
        txns = [
            {"trade_date": "bad", "fund_code": "ABC", "transaction_type": "buy", "amount": 100.0, "fund_name": "Sensitive Fund Name"},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        warning_text = " ".join(result["warnings"])
        assert "Sensitive Fund Name" not in warning_text
        assert "100.0" not in warning_text

    def test_needs_manual_review_flag(self):
        """Invalid entries must have needs_manual_review=True."""
        txns = [
            {"trade_date": "bad", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        invalid_entry = next(t for t in result["transactions"] if t.get("trade_date") == "bad")
        valid_entry = next(t for t in result["transactions"] if t.get("trade_date") == "2026-06-01")
        assert invalid_entry["needs_manual_review"] is True
        assert invalid_entry["validation_status"] == "warning"
        assert valid_entry["needs_manual_review"] is False
        assert valid_entry["validation_status"] == "ok"

    def test_valid_ledger_no_manual_review(self):
        """Valid entries must have needs_manual_review=False."""
        txns = [
            {"trade_date": "2026-06-01", "fund_code": "000001", "transaction_type": "buy", "amount": 100.0},
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        assert result["summary"]["manual_review_count"] == 0
        assert result["summary"]["warning_count"] == 0
        assert result["summary"]["invalid_count"] == 0
        assert result["transactions"][0]["needs_manual_review"] is False
        assert result["transactions"][0]["validation_status"] == "ok"


# ── Privacy redaction tests ────────────────────────────────────────────


class TestWarningPrivacyRedaction:
    def test_unknown_transaction_type_warning_redacts_raw_value(self):
        """Warning must not contain the raw transaction_type value."""
        raw = {
            "trade_date": "2026-06-01",
            "fund_code": "000001",
            "transaction_type": "secret_order_123",
            "amount": 100.00,
        }
        result = normalize_portfolio_input_transaction(raw, 0)
        assert result["action"] == "unknown"
        assert result["manual_review_required"] is True
        # Warning must not contain the raw type
        warning_text = " ".join(result.get("warnings", []))
        assert "secret_order_123" not in warning_text
        # Warning must contain index and label
        assert any("unknown transaction_type" in w for w in result.get("warnings", []))
        assert any("transaction index 0" in w for w in result.get("warnings", []))

    def test_adapter_warnings_do_not_leak_fund_name_amount_or_note(self):
        """Warnings must not contain fund_name, amount, or note from input."""
        txns = [
            {
                "trade_date": "bad-date",
                "fund_code": "ABC",
                "fund_name": "Sensitive Fund Name",
                "transaction_type": "private_type_xyz",
                "amount": 99999.99,
                "note": "user private note content",
            },
        ]
        result = build_ledger_from_portfolio_input_transactions(txns)
        warning_text = " ".join(result.get("warnings", []))
        # Must not contain any raw user input
        assert "Sensitive Fund Name" not in warning_text
        assert "99999.99" not in warning_text
        assert "private_type_xyz" not in warning_text
        assert "user private note content" not in warning_text
        # Must contain counts/indexes
        assert "transaction index 0" in warning_text
