"""JSON Schema validation tests for portfolio input and provider snapshot.

Uses jsonschema (available in project dependencies) for real validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
TEMPLATES_DIR = ROOT / "examples" / "user_portfolio_templates"


def _load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestFundPortfolioInputSchemaValidation:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.schema = _load_schema("fund_portfolio_input.schema.json")

    def test_demo_validates(self):
        demo = _load_json(TEMPLATES_DIR / "fund_portfolio_input_demo.json")
        jsonschema.validate(demo, self.schema)

    def test_template_validates(self):
        template = _load_json(TEMPLATES_DIR / "fund_portfolio_input_template.json")
        jsonschema.validate(template, self.schema)

    def test_invalid_missing_required_fields(self):
        invalid = {"base_currency": "CNY"}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, self.schema)

    def test_invalid_wrong_schema_version(self):
        invalid = {
            "schema_version": "wrong_version",
            "as_of_date": "2024-12-31",
            "holdings": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, self.schema)

    def test_invalid_analysis_mode(self):
        invalid = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [],
            "analysis_mode": "invalid_mode",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, self.schema)

    def test_minimal_valid_input(self):
        minimal = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000}
            ],
        }
        jsonschema.validate(minimal, self.schema)

    def test_holding_with_null_cost_basis(self):
        data = {
            "schema_version": "fund_portfolio_input.v1",
            "as_of_date": "2024-12-31",
            "holdings": [
                {"fund_code": "000001", "current_value": 10000, "cost_basis": None}
            ],
        }
        jsonschema.validate(data, self.schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestProviderDataSnapshotSchemaValidation:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.schema = _load_schema("provider_data_snapshot.schema.json")

    def test_demo_validates(self):
        demo = _load_json(TEMPLATES_DIR / "provider_data_snapshot_demo.json")
        jsonschema.validate(demo, self.schema)

    def test_template_validates(self):
        template = _load_json(TEMPLATES_DIR / "provider_data_snapshot_template.json")
        jsonschema.validate(template, self.schema)

    def test_invalid_missing_required_fields(self):
        invalid = {"fund_nav_history": {}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, self.schema)

    def test_invalid_wrong_schema_version(self):
        invalid = {
            "schema_version": "wrong_version",
            "as_of_date": "2024-12-31",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, self.schema)

    def test_minimal_valid_snapshot(self):
        minimal = {
            "schema_version": "provider_data_snapshot.v1",
            "as_of_date": "2024-12-31",
        }
        jsonschema.validate(minimal, self.schema)


class TestTemplateFileFormats:
    def test_portfolio_input_template_is_valid_json(self):
        path = TEMPLATES_DIR / "fund_portfolio_input_template.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_provider_snapshot_template_is_valid_json(self):
        path = TEMPLATES_DIR / "provider_data_snapshot_template.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_risk_profile_template_is_valid_yaml(self):
        import yaml
        path = TEMPLATES_DIR / "risk_profile_template.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_investment_constraints_template_is_valid_yaml(self):
        import yaml
        path = TEMPLATES_DIR / "investment_constraints_template.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_transaction_history_template_is_valid_csv(self):
        import csv
        path = TEMPLATES_DIR / "transaction_history_template.csv"
        content = path.read_text(encoding="utf-8")
        reader = csv.reader(content.splitlines())
        rows = list(reader)
        assert len(rows) >= 1
