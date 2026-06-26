"""Tests for private data doctor and override schema validation.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

# ── Schema validation helpers (extracted for direct testing) ──────────

FUND_CODE_RE = __import__("re").compile(r"^\d{6}$")
DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_identity_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Validate identity override schema. Returns {status, details}."""
    if not isinstance(data, dict) or "funds" not in data:
        return {"status": "FAILED", "message": "Missing top-level 'funds' key"}

    funds = data["funds"]
    if not isinstance(funds, list):
        return {"status": "FAILED", "message": "'funds' must be a list"}

    invalid_codes: list[int] = []
    missing_raw_name: list[int] = []

    for i, entry in enumerate(funds):
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("fund_code", ""))
        if code and not FUND_CODE_RE.match(code):
            invalid_codes.append(i)
        if not entry.get("raw_name"):
            missing_raw_name.append(i)

    details: dict[str, Any] = {"total_entries": len(funds)}
    status = "OK"
    message = f"Identity overrides valid: {len(funds)} entries"

    if invalid_codes:
        details["invalid_code_indices"] = invalid_codes
        status = "WARNING"
        message = f"{len(invalid_codes)} entry/entries have invalid fund_code"
    if missing_raw_name:
        details["missing_raw_name_indices"] = missing_raw_name
        status = "WARNING"
        message += f"; {len(missing_raw_name)} entry/entries missing raw_name"

    return {"status": status, "message": message, "details": details}


def _validate_nav_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Validate NAV override schema. Returns {status, details}."""
    if not isinstance(data, dict):
        return {"status": "FAILED", "message": "Top-level value must be an object"}

    invalid_codes: list[str] = []
    invalid_dates: list[str] = []
    invalid_navs: list[str] = []

    for code, nav_map in data.items():
        if not FUND_CODE_RE.match(str(code)):
            invalid_codes.append(str(code))
        if not isinstance(nav_map, dict):
            continue
        for date_str, nav_val in nav_map.items():
            if not DATE_RE.match(str(date_str)):
                invalid_dates.append(f"{code}:{date_str}")
            if not isinstance(nav_val, (int, float)) or nav_val <= 0:
                invalid_navs.append(f"{code}:{date_str}")

    details: dict[str, Any] = {"total_funds": len(data)}
    status = "OK"
    message = f"NAV overrides valid: {len(data)} fund(s)"

    if invalid_codes:
        details["invalid_code_count"] = len(invalid_codes)
        status = "WARNING"
        message = f"{len(invalid_codes)} fund code(s) are not 6-digit"
    if invalid_dates:
        details["invalid_date_count"] = len(invalid_dates)
        status = "WARNING"
        message += f"; {len(invalid_dates)} date(s) not in YYYY-MM-DD format"
    if invalid_navs:
        details["invalid_nav_count"] = len(invalid_navs)
        status = "WARNING"
        message += f"; {len(invalid_navs)} NAV value(s) not positive"

    return {"status": status, "message": message, "details": details}


# ── Identity override tests ───────────────────────────────────────────


class TestIdentityOverrideSchema:
    def test_valid_fake_overrides_pass(self):
        data = {
            "funds": [
                {"raw_name": "Fake Fund A", "fund_code": "000001", "fund_name": "Fake Fund A"},
                {"raw_name": "Fake Fund B", "fund_code": "000002", "fund_name": "Fake Fund B"},
            ]
        }
        result = _validate_identity_overrides(data)
        assert result["status"] == "OK"
        assert result["details"]["total_entries"] == 2

    def test_invalid_fund_code_fails(self):
        data = {
            "funds": [
                {"raw_name": "Bad Code Fund", "fund_code": "ABC123", "fund_name": "Bad Code Fund"},
            ]
        }
        result = _validate_identity_overrides(data)
        assert result["status"] == "WARNING"
        assert 0 in result["details"]["invalid_code_indices"]

    def test_missing_funds_key_fails(self):
        data = {"overrides": []}
        result = _validate_identity_overrides(data)
        assert result["status"] == "FAILED"

    def test_missing_raw_name_warns(self):
        data = {
            "funds": [
                {"fund_code": "000001", "fund_name": "No Raw Name"},
            ]
        }
        result = _validate_identity_overrides(data)
        assert result["status"] == "WARNING"
        assert 0 in result["details"]["missing_raw_name_indices"]

    def test_chinese_name_in_raw_name_is_ok(self):
        data = {
            "funds": [
                {"raw_name": "虚构基金A", "fund_code": "000001", "fund_name": "虚构基金A"},
            ]
        }
        result = _validate_identity_overrides(data)
        assert result["status"] == "OK"

    def test_empty_fund_code_is_not_flagged(self):
        """Empty fund_code is allowed (identity not yet resolved)."""
        data = {
            "funds": [
                {"raw_name": "Unresolved Fund", "fund_code": "", "fund_name": "Unresolved Fund"},
            ]
        }
        result = _validate_identity_overrides(data)
        assert result["status"] == "OK"


# ── NAV override tests ────────────────────────────────────────────────


class TestNavOverrideSchema:
    def test_valid_fake_nav_overrides_pass(self):
        data = {
            "000001": {"2026-01-15": 1.2345},
            "000002": {"2026-01-15": 0.9876},
        }
        result = _validate_nav_overrides(data)
        assert result["status"] == "OK"
        assert result["details"]["total_funds"] == 2

    def test_invalid_fund_code_warns(self):
        data = {
            "ABC": {"2026-01-15": 1.0},
        }
        result = _validate_nav_overrides(data)
        assert result["status"] == "WARNING"
        assert result["details"]["invalid_code_count"] == 1

    def test_invalid_date_format_warns(self):
        data = {
            "000001": {"01-15-2026": 1.0},
        }
        result = _validate_nav_overrides(data)
        assert result["status"] == "WARNING"
        assert result["details"]["invalid_date_count"] == 1

    def test_non_positive_nav_warns(self):
        data = {
            "000001": {"2026-01-15": -1.0},
        }
        result = _validate_nav_overrides(data)
        assert result["status"] == "WARNING"
        assert result["details"]["invalid_nav_count"] == 1

    def test_zero_nav_warns(self):
        data = {
            "000001": {"2026-01-15": 0},
        }
        result = _validate_nav_overrides(data)
        assert result["status"] == "WARNING"
        assert result["details"]["invalid_nav_count"] == 1

    def test_string_nav_warns(self):
        data = {
            "000001": {"2026-01-15": "not_a_number"},
        }
        result = _validate_nav_overrides(data)
        assert result["status"] == "WARNING"
        assert result["details"]["invalid_nav_count"] == 1

    def test_top_level_not_dict_fails(self):
        result = _validate_nav_overrides([1, 2, 3])
        assert result["status"] == "FAILED"


# ── Doctor output redaction tests ─────────────────────────────────────


class TestDoctorOutputRedaction:
    def test_doctor_no_real_fund_names_in_output(self, tmp_path: Path):
        """Doctor output must not contain real fund names from overrides."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        fake_private = tmp_path / "private_data"
        fake_private.mkdir()

        # Write identity overrides with fake names
        yaml_content = textwrap.dedent("""\
            funds:
              - raw_name: "Fake Test Fund Alpha"
                fund_code: "000001"
                fund_name: "Fake Test Fund Alpha"
        """)
        (fake_private / "fund_identity_overrides.private.yaml").write_text(yaml_content, encoding="utf-8")

        result = run_doctor(fake_private)
        output = json.dumps(result, default=str)

        # The fake name should appear only in the YAML file, not in doctor output
        # Doctor should only report counts, not names
        for check in result["checks"]:
            # No raw_name or fund_name values in details
            assert "Fake Test Fund Alpha" not in json.dumps(check.get("details", {}), default=str)

    def test_doctor_reports_identity_template_counts_only(self, tmp_path: Path):
        """Doctor should report generated template counts without names."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        fake_private = tmp_path / "private_data"
        fake_private.mkdir()

        yaml_content = textwrap.dedent("""\
            funds:
              - raw_name: "Fake Template Fund Alpha"
                fund_code: ""
                fund_name: "Fake Template Fund Alpha"
              - raw_name: "Fake Template Fund Beta"
                fund_code: "000002"
                fund_name: "Fake Template Fund Beta"
        """)
        (fake_private / "fund_identity_overrides.template.private.yaml").write_text(
            yaml_content, encoding="utf-8"
        )

        result = run_doctor(fake_private)
        template_check = next(
            c for c in result["checks"]
            if c["id"] == "identity_overrides_template.exists"
        )

        assert template_check["status"] == "INFO"
        assert template_check["details"]["total_entries"] == 2
        assert template_check["details"]["missing_code_count"] == 1
        output = json.dumps(result, default=str)
        assert "Fake Template Fund Alpha" not in output
        assert "Fake Template Fund Beta" not in output

    def test_doctor_reports_news_key_count_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Doctor should report news key readiness without leaking values."""
        from scripts.fund_agent_private_data_doctor import NEWS_API_ENV_VARS, run_doctor

        fake_private = tmp_path / "private_data"
        fake_private.mkdir()
        for key in NEWS_API_ENV_VARS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("TAVILY_API_KEY", "synthetic-secret-value")

        result = run_doctor(fake_private)
        key_check = next(
            c for c in result["checks"]
            if c["id"] == "news_api_keys.configured"
        )

        assert key_check["status"] == "OK"
        assert key_check["details"]["configured_count"] == 1
        output = json.dumps(result, default=str)
        assert "synthetic-secret-value" not in output

    def test_doctor_no_amounts_in_output(self, tmp_path: Path):
        """Doctor output must not contain NAV values."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        fake_private = tmp_path / "private_data"
        fake_private.mkdir()

        nav_data = {"000001": {"2026-01-15": 1.2345}}
        (fake_private / "nav_overrides.private.json").write_text(
            json.dumps(nav_data), encoding="utf-8"
        )

        result = run_doctor(fake_private)
        output = json.dumps(result, default=str)

        # NAV values should not appear in output
        assert "1.2345" not in output

    def test_doctor_reports_csv_count_only(self, tmp_path: Path):
        """Doctor should report CSV file count, not content."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        fake_private = tmp_path / "private_data"
        fake_private.mkdir()

        (fake_private / "test_export.csv").write_text("header\nrow1\n", encoding="utf-8")
        (fake_private / "test_export2.csv").write_text("header\nrow1\n", encoding="utf-8")

        result = run_doctor(fake_private)
        csv_check = next(c for c in result["checks"] if c["id"] == "alipay_csv.exists")
        assert csv_check["details"]["count"] == 2
        # No CSV content in output
        assert "header" not in json.dumps(result, default=str)

    def test_doctor_respects_custom_private_data_dir(self, tmp_path: Path):
        """run_doctor(private_data_dir=custom) checks custom dir."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        custom_pd = tmp_path / "custom_private"
        custom_pd.mkdir()

        # Place portfolio_input in custom dir
        pi = {"schema_version": "portfolio_input.v1", "holdings": []}
        (custom_pd / "portfolio_input.private.json").write_text(
            json.dumps(pi), encoding="utf-8"
        )

        result = run_doctor(custom_pd)

        # Should find the directory
        dir_check = next(c for c in result["checks"] if c["id"] == "private_data.exists")
        assert dir_check["status"] == "OK"

        # Should find portfolio_input
        pi_check = next(c for c in result["checks"] if c["id"] == "portfolio_input.exists")
        assert pi_check["status"] == "OK"

        # Output must not contain the absolute path
        output = json.dumps(result, default=str)
        assert str(custom_pd) not in output

    def test_doctor_default_dir_backward_compat(self):
        """run_doctor() without args still works (backward compat)."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        result = run_doctor()
        assert "ok" in result
        assert "checks" in result
