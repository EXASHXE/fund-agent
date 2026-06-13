"""Tests for provider data snapshot schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "provider_data_snapshot.schema.json"
TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "examples" / "user_portfolio_templates" / "provider_data_snapshot_template.json"
DEMO_PATH = Path(__file__).resolve().parents[2] / "examples" / "user_portfolio_templates" / "provider_data_snapshot_demo.json"


class TestProviderDataSnapshotSchema:
    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists()

    def test_schema_is_valid_json(self):
        data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        assert data.get("title") == "ProviderDataSnapshot"
        assert data.get("type") == "object"

    def test_schema_has_required_fields(self):
        data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        required = data.get("required", [])
        assert "schema_version" in required
        assert "as_of_date" in required

    def test_schema_defines_all_snapshot_sections(self):
        data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        props = data.get("properties", {})
        expected_sections = [
            "fund_nav_history", "benchmark_index_history", "fund_profiles",
            "fund_holdings", "peer_ranking", "fee_schedules",
            "redemption_rules", "news_evidence_refs", "sentiment_evidence_refs",
            "provider_provenance", "limitations", "warnings",
        ]
        for section in expected_sections:
            assert section in props, f"missing section: {section}"


class TestProviderDataSnapshotTemplate:
    def test_template_file_exists(self):
        assert TEMPLATE_PATH.exists()

    def test_template_is_valid_json(self):
        data = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        assert data.get("schema_version") == "provider_data_snapshot.v1"
        assert "as_of_date" in data

    def test_template_has_all_sections(self):
        data = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        expected_sections = [
            "fund_nav_history", "benchmark_index_history", "fund_profiles",
            "fund_holdings", "peer_ranking", "fee_schedules",
            "redemption_rules", "news_evidence_refs", "sentiment_evidence_refs",
            "provider_provenance", "limitations", "warnings",
        ]
        for section in expected_sections:
            assert section in data, f"missing section: {section}"


class TestProviderDataSnapshotDemo:
    def test_demo_file_exists(self):
        assert DEMO_PATH.exists()

    def test_demo_is_valid_json(self):
        data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        assert data.get("schema_version") == "provider_data_snapshot.v1"

    def test_demo_has_synthetic_data(self):
        data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        assert data.get("as_of_date") != ""
        nav_history = data.get("fund_nav_history", {})
        assert len(nav_history) > 0

    def test_demo_marks_synthetic_limitations(self):
        data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        limitations = data.get("limitations", [])
        assert any("synthetic" in l.lower() or "demo" in l.lower() for l in limitations)

    def test_demo_has_provider_provenance(self):
        data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        prov = data.get("provider_provenance", {})
        assert len(prov) > 0
        for provider_name, prov_data in prov.items():
            assert "provider" in prov_data
            assert "capabilities_fetched" in prov_data

    def test_demo_no_real_private_data(self):
        data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        text = json.dumps(data)
        assert "cookie" not in text.lower() or "<redacted>" in text
        assert "token" not in text.lower() or "<redacted>" in text
