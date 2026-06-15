"""Tests for manual transaction entries template and schema extensions (v0.10.1)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT / "examples" / "user_portfolio_templates"
SCHEMAS_DIR = ROOT / "schemas"

EXPECTED_CSV_HEADER = [
    "date",
    "fund_name",
    "fund_code",
    "action",
    "amount",
    "status",
    "source_platform",
    "source_ref",
    "settlement_account",
    "confidence",
    "notes",
]

ALLOWED_ACTIONS = {
    "buy",
    "sell",
    "cash_dividend",
    "conversion",
    "refund",
    "fee",
    "transfer_in",
    "transfer_out",
    "manual_adjustment",
    "unknown",
}

ALLOWED_STATUSES = {
    "confirmed",
    "pending_confirmation",
    "estimated",
    "cancelled",
    "unknown",
}


class TestManualTransactionEntriesTemplate:
    """Tests for the manual_transaction_entries_template.csv file."""

    def test_template_file_exists(self):
        path = TEMPLATES_DIR / "manual_transaction_entries_template.csv"
        assert path.exists(), f"Template file not found: {path}"

    def test_csv_header_fields_complete_and_correct_order(self):
        path = TEMPLATES_DIR / "manual_transaction_entries_template.csv"
        content = path.read_text(encoding="utf-8")
        reader = csv.reader(content.splitlines())
        header = next(reader)
        assert header == EXPECTED_CSV_HEADER, (
            f"CSV header mismatch.\nExpected: {EXPECTED_CSV_HEADER}\nGot:      {header}"
        )

    def test_csv_has_at_least_one_data_row(self):
        path = TEMPLATES_DIR / "manual_transaction_entries_template.csv"
        content = path.read_text(encoding="utf-8")
        reader = csv.reader(content.splitlines())
        rows = list(reader)
        # Header + at least 1 data row
        assert len(rows) >= 2, "Template should have header + at least 1 example row"

    def test_csv_action_values_are_allowed(self):
        path = TEMPLATES_DIR / "manual_transaction_entries_template.csv"
        content = path.read_text(encoding="utf-8")
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            action = row.get("action", "")
            assert action in ALLOWED_ACTIONS, (
                f"Invalid action '{action}' in template. Allowed: {ALLOWED_ACTIONS}"
            )

    def test_csv_status_values_are_allowed(self):
        path = TEMPLATES_DIR / "manual_transaction_entries_template.csv"
        content = path.read_text(encoding="utf-8")
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            status = row.get("status", "")
            assert status in ALLOWED_STATUSES, (
                f"Invalid status '{status}' in template. Allowed: {ALLOWED_STATUSES}"
            )

    def test_csv_no_real_user_data(self):
        """Template must not contain real user data — only fictional examples."""
        path = TEMPLATES_DIR / "manual_transaction_entries_template.csv"
        content = path.read_text(encoding="utf-8")
        # Check for fictional indicators
        assert "虚构" in content or "示例" in content or "example" in content.lower() or "demo" in content.lower(), (
            "Template should clearly indicate data is fictional/demo"
        )

    def test_csv_fund_code_can_be_empty(self):
        """Template should demonstrate that fund_code can be left empty."""
        path = TEMPLATES_DIR / "manual_transaction_entries_template.csv"
        content = path.read_text(encoding="utf-8")
        reader = csv.DictReader(content.splitlines())
        has_empty_fund_code = any(row.get("fund_code", "MISSING") == "" for row in reader)
        assert has_empty_fund_code, (
            "Template should have at least one row with empty fund_code to show it's allowed"
        )


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestManualTransactionSchemaExtensions:
    """Tests for schema extensions added in v0.10.1."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.schema = json.loads(
            (SCHEMAS_DIR / "fund_portfolio_input.schema.json").read_text(encoding="utf-8")
        )

    def test_schema_accepts_manual_transactions_ref(self):
        """Top-level optional field manual_transactions_ref."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "manual_transactions_ref": "private_data/manual_transactions.private.csv",
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_accepts_manual_transactions_format(self):
        """Top-level optional field manual_transactions_format."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "manual_transactions_format": "manual_csv",
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_accepts_source_notes(self):
        """Top-level optional field source_notes."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "source_notes": "Manual entry from Alipay records",
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_accepts_transaction_evidence_refs(self):
        """Top-level optional field transaction_evidence_refs."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "transaction_evidence_refs": ["manual_transactions.private.csv"],
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_accepts_pending_transaction_count(self):
        """Top-level optional field pending_transaction_count."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "pending_transaction_count": 2,
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_data_quality_validated_against_manual_transactions(self):
        """data_quality optional field validated_against_manual_transactions."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "data_quality": {
                "validated_against_manual_transactions": True,
            },
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_data_quality_transaction_history_incomplete(self):
        """data_quality optional field transaction_history_incomplete."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "data_quality": {
                "transaction_history_incomplete": True,
            },
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_data_quality_fund_code_missing(self):
        """data_quality optional field fund_code_missing."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "data_quality": {
                "fund_code_missing": True,
            },
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_data_quality_units_missing(self):
        """data_quality optional field units_missing."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "data_quality": {
                "units_missing": True,
            },
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_data_quality_nav_missing(self):
        """data_quality optional field nav_missing."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "data_quality": {
                "nav_missing": False,
            },
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_data_quality_cost_basis_partial(self):
        """data_quality optional field cost_basis_partial."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "data_quality": {
                "cost_basis_partial": True,
            },
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_holding_source_platform(self):
        """Holding-level optional field source_platform."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000, "source_platform": "alipay"}
            ],
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_holding_holding_source(self):
        """Holding-level optional field holding_source."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000, "holding_source": "manual_snapshot"}
            ],
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_holding_holding_source_all_values(self):
        """All allowed holding_source values should validate."""
        for value in ["manual_snapshot", "provider_snapshot", "transaction_derived", "unknown"]:
            minimal = {
                "schema_version": "fund_portfolio_input.v1",
                "as_of_date": "2024-12-31",
                "holdings": [
                    {"fund_code": "000001", "current_value": 10000, "holding_source": value}
                ],
            }
            jsonschema.validate(minimal, self.schema)

    def test_schema_holding_source_notes(self):
        """Holding-level optional field source_notes."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000, "source_notes": "From Alipay records"}
            ],
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_holding_transaction_evidence_refs(self):
        """Holding-level optional field transaction_evidence_refs."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000, "transaction_evidence_refs": ["row_5"]}
            ],
        }
        jsonschema.validate(minimal, self.schema)

    def test_schema_holding_pending_transaction_count(self):
        """Holding-level optional field pending_transaction_count."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000, "pending_transaction_count": 1}
            ],
        }
        jsonschema.validate(minimal, self.schema)

    def test_backward_compatibility_minimal_input(self):
        """Existing minimal portfolio input without new fields must still validate."""
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
        }
        jsonschema.validate(minimal, self.schema)

    def test_backward_compatibility_existing_demo(self):
        """Existing demo portfolio input must still validate."""
        demo = json.loads(
            (TEMPLATES_DIR / "fund_portfolio_input_demo.json").read_text(encoding="utf-8")
        )
        jsonschema.validate(demo, self.schema)

    def test_backward_compatibility_existing_template(self):
        """Existing template portfolio input must still validate."""
        template = json.loads(
            (TEMPLATES_DIR / "fund_portfolio_input_template.json").read_text(encoding="utf-8")
        )
        jsonschema.validate(template, self.schema)

    def test_invalid_manual_transactions_format_rejected(self):
        """Invalid manual_transactions_format value should be rejected."""
        invalid = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [{"fund_code": "000001", "current_value": 10000}],
            "manual_transactions_format": "invalid_format",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, self.schema)

    def test_invalid_holding_source_rejected(self):
        """Invalid holding_source value should be rejected."""
        invalid = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000, "holding_source": "invalid_source"}
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, self.schema)
