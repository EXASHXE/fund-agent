"""Tests for current holdings snapshot importer (M7.5 Phase 2)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.tools.portfolio.current_holdings_snapshot import (
    load_current_holdings_snapshot,
    normalize_current_holdings_snapshot,
    validate_current_holdings_snapshot,
)


class TestLoadCsv:
    def test_load_valid_csv(self, tmp_path: Path):
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(
            "as_of_date,fund_code,fund_name,shares,latest_nav,nav_date,current_value,holding_cost,holding_profit,holding_profit_pct,source,user_verified\n"
            "2026-06-26,000001,Test Fund,1000.00,1.50,2026-06-25,1500.00,1000.00,500.00,0.50,alipay,true\n",
            encoding="utf-8",
        )
        result = load_current_holdings_snapshot(csv_path)
        assert result["schema_version"] == "current_holdings_snapshot.v1"
        assert result["as_of_date"] == "2026-06-26"
        assert len(result["positions"]) == 1
        pos = result["positions"][0]
        assert pos["fund_code"] == "000001"
        assert pos["fund_name"] == "Test Fund"
        assert pos["shares"] == 1000.00
        assert pos["latest_nav"] == 1.50
        assert pos["current_value"] == 1500.00
        assert pos["user_verified"] is True
        assert pos["identity_verification_status"] == "user_verified_override"
        assert pos["valuation_source"] == "authoritative_holdings_snapshot"

    def test_load_csv_empty_fund_code(self, tmp_path: Path):
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(
            "as_of_date,fund_code,fund_name,shares,latest_nav,nav_date,current_value,holding_cost,holding_profit,holding_profit_pct,source,user_verified\n"
            "2026-06-26,,Test Fund,1000.00,1.50,2026-06-25,1500.00,,,,,\n",
            encoding="utf-8",
        )
        result = load_current_holdings_snapshot(csv_path)
        pos = result["positions"][0]
        assert pos["fund_code"] is None
        assert pos["identity_verification_status"] == "name_only"

    def test_load_csv_missing_values_stay_none(self, tmp_path: Path):
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(
            "as_of_date,fund_code,fund_name,shares,latest_nav,nav_date,current_value,holding_cost,holding_profit,holding_profit_pct,source,user_verified\n"
            "2026-06-26,000001,Test Fund,,,,,,,\n",
            encoding="utf-8",
        )
        result = load_current_holdings_snapshot(csv_path)
        pos = result["positions"][0]
        assert pos["shares"] is None
        assert pos["latest_nav"] is None
        assert pos["current_value"] is None
        assert pos["valuation_source"] == "holdings_snapshot_no_valuation"


class TestLoadJson:
    def test_load_valid_json(self, tmp_path: Path):
        json_path = tmp_path / "test.json"
        data = {
            "schema_version": "current_holdings_snapshot.v1",
            "as_of_date": "2026-06-26",
            "positions": [
                {
                    "fund_code": "000001",
                    "fund_name": "Test Fund",
                    "shares": 1000.00,
                    "latest_nav": 1.50,
                    "current_value": 1500.00,
                    "user_verified": True,
                }
            ],
        }
        json_path.write_text(json.dumps(data), encoding="utf-8")
        result = load_current_holdings_snapshot(json_path)
        assert len(result["positions"]) == 1
        assert result["positions"][0]["fund_code"] == "000001"


class TestValidation:
    def test_valid_snapshot_no_errors(self):
        data = {
            "positions": [
                {"fund_name": "Test Fund", "fund_code": "000001", "shares": 100},
            ]
        }
        errors = validate_current_holdings_snapshot(data)
        assert errors == []

    def test_missing_fund_name(self):
        data = {"positions": [{"fund_code": "000001"}]}
        errors = validate_current_holdings_snapshot(data)
        assert any("fund_name is required" in e for e in errors)

    def test_invalid_fund_code(self):
        data = {"positions": [{"fund_name": "Test", "fund_code": "abc"}]}
        errors = validate_current_holdings_snapshot(data)
        assert any("6 digits" in e for e in errors)

    def test_negative_shares(self):
        data = {"positions": [{"fund_name": "Test", "shares": -100}]}
        errors = validate_current_holdings_snapshot(data)
        assert any("non-negative" in e for e in errors)

    def test_non_numeric_shares(self):
        data = {"positions": [{"fund_name": "Test", "shares": "abc"}]}
        errors = validate_current_holdings_snapshot(data)
        assert any("numeric" in e for e in errors)


class TestNormalization:
    def test_empty_string_becomes_none(self):
        data = {"positions": [{"fund_name": "Test", "fund_code": "", "shares": ""}]}
        result = normalize_current_holdings_snapshot(data)
        pos = result["positions"][0]
        assert pos["fund_code"] is None
        assert pos["shares"] is None

    def test_user_verified_override_status(self):
        data = {"positions": [{"fund_name": "Test", "fund_code": "000001", "user_verified": True}]}
        result = normalize_current_holdings_snapshot(data)
        assert result["positions"][0]["identity_verification_status"] == "user_verified_override"

    def test_unverified_code_status(self):
        data = {"positions": [{"fund_name": "Test", "fund_code": "000001", "user_verified": False}]}
        result = normalize_current_holdings_snapshot(data)
        assert result["positions"][0]["identity_verification_status"] == "unverified_code"

    def test_name_only_status(self):
        data = {"positions": [{"fund_name": "Test"}]}
        result = normalize_current_holdings_snapshot(data)
        assert result["positions"][0]["identity_verification_status"] == "name_only"

    def test_valuation_source_shares_nav(self):
        data = {"positions": [{"fund_name": "Test", "shares": 100, "latest_nav": 1.5}]}
        result = normalize_current_holdings_snapshot(data)
        assert result["positions"][0]["valuation_source"] == "authoritative_holdings_snapshot"

    def test_valuation_source_current_value_only(self):
        data = {"positions": [{"fund_name": "Test", "current_value": 1500}]}
        result = normalize_current_holdings_snapshot(data)
        assert result["positions"][0]["valuation_source"] == "platform_reported_current_value"

    def test_valuation_source_no_valuation(self):
        data = {"positions": [{"fund_name": "Test"}]}
        result = normalize_current_holdings_snapshot(data)
        assert result["positions"][0]["valuation_source"] == "holdings_snapshot_no_valuation"

    def test_summary_counts(self):
        data = {
            "positions": [
                {"fund_name": "A", "fund_code": "000001", "shares": 100, "latest_nav": 1.5, "current_value": 150, "user_verified": True},
                {"fund_name": "B", "current_value": 300},
                {"fund_name": "C"},
            ]
        }
        result = normalize_current_holdings_snapshot(data)
        s = result["summary"]
        assert s["positions_total"] == 3
        assert s["shares_available_count"] == 1
        assert s["current_value_available_count"] == 2
        assert s["user_verified_count"] == 1
        assert s["fund_code_available_count"] == 1
        assert s["valued_from_shares_nav_count"] == 1
        assert s["valued_from_current_value_only_count"] == 1
        assert s["valued_count"] == 2


class TestFileNotFound:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_current_holdings_snapshot(Path("/nonexistent/file.csv"))

    def test_unsupported_format_raises(self, tmp_path: Path):
        bad_path = tmp_path / "test.xlsx"
        bad_path.write_text("data", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            load_current_holdings_snapshot(bad_path)
