"""Contract tests for fund_analysis input contract v1."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.skillpack.input_contract_catalog import (
    capability_field_mapping_for_skill,
    get_skill_input_contract,
    load_input_contracts,
    optional_fields_for_skill,
    recommended_fields_for_skill,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "skillpack" / "input-contracts.yaml"
DOC_PATH = ROOT / "docs" / "contracts" / "fund-analysis-input-contract.v1.md"

RECOMMENDED_FIELDS = {
    "risk_profile",
    "constraints",
    "fund_profiles",
    "nav_history",
    "holdings",
    "transactions",
    "dca_plans",
}

OPTIONAL_FIELDS = {
    "benchmarks",
    "benchmark_history",
    "peer_group",
    "factor_exposures",
    "manager_profiles",
    "fee_schedules",
    "redemption_rules",
    "market_scenario",
    "report_options",
    "research_planning",
}

CAPABILITY_KEYS = {
    "portfolio_snapshot",
    "fund_profile",
    "fund_nav_history",
    "fund_holdings",
    "fund_transactions",
    "fund_fee_schedule",
    "fund_benchmark",
    "benchmark_history",
    "fund_peer_group",
    "fund_manager_profile",
    "fund_flow",
    "index_constituents",
    "macro_events",
    "market_calendar",
    "user_investment_plan",
}


def _contracts_doc() -> dict:
    assert CONTRACT_PATH.exists()
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def _fund_contract() -> dict:
    return _contracts_doc()["contracts"]["fund_analysis"]


def _mode(name: str) -> dict:
    modes = {item["mode"]: item for item in _fund_contract()["minimum_required"]}
    return modes[name]


def _field_keys(section: str) -> set[str]:
    return {item["key"] for item in _fund_contract()[section]}


def test_input_contract_yaml_exists_and_parses() -> None:
    data = _contracts_doc()
    assert data["schema_version"] == "input-contracts.v1"
    assert "fund_analysis" in data["contracts"]


def test_fund_analysis_input_contract_metadata() -> None:
    contract = _fund_contract()
    assert contract["doc"] == "docs/contracts/fund-analysis-input-contract.v1.md"
    assert contract["runtime_id"] == "fund_analysis"
    assert contract["doc_slug"] == "fund-analysis"
    assert DOC_PATH.exists()


def test_accepted_envelope_shapes_are_declared() -> None:
    shapes = {item["name"] for item in _fund_contract()["accepted_envelope_shapes"]}
    assert {"full_skill_input", "payload_only"} <= shapes


def test_minimum_required_modes_are_declared() -> None:
    modes = {item["mode"] for item in _fund_contract()["minimum_required"]}
    assert {"portfolio_snapshot", "ledger_derived", "related_entities_baseline"} <= modes


def test_portfolio_snapshot_required_fields() -> None:
    required = set(_mode("portfolio_snapshot")["required"])
    assert {
        "payload.portfolio",
        "payload.portfolio.positions[]",
        "payload.portfolio.positions[].fund_code",
    } <= required


def test_ledger_derived_required_fields() -> None:
    required = set(_mode("ledger_derived")["required"])
    assert {
        "payload.transactions[]",
        "payload.current_nav",
        "payload.as_of_date or payload.portfolio.as_of_date",
    } <= required


def test_related_entities_baseline_is_degraded() -> None:
    assert _mode("related_entities_baseline")["degraded"] is True


def test_recommended_and_optional_fields_are_declared() -> None:
    assert RECOMMENDED_FIELDS <= _field_keys("recommended_fields")
    assert OPTIONAL_FIELDS <= _field_keys("optional_fields")


def test_host_data_capability_mapping_is_declared() -> None:
    mapping = _fund_contract()["host_data_capability_fields"]
    assert CAPABILITY_KEYS <= set(mapping)
    assert mapping["portfolio_snapshot"]["payload_fields"] == ["portfolio"]
    assert mapping["fund_profile"]["payload_fields"] == ["fund_profiles", "fund_profile"]
    assert mapping["macro_events"]["payload_fields"] == ["macro_events", "market_scenario"]


def test_required_mcp_and_validation_severity_values() -> None:
    contract = _fund_contract()
    assert contract["required_mcp_capabilities"] == []
    assert {"OK", "PARTIAL", "INVALID"} <= set(contract["validation"]["severity_values"])


def test_input_contract_loader_accepts_runtime_id_and_doc_slug() -> None:
    by_runtime = get_skill_input_contract("fund_analysis", CONTRACT_PATH)
    by_slug = get_skill_input_contract("fund-analysis", CONTRACT_PATH)
    assert by_runtime == by_slug
    assert set(recommended_fields_for_skill("fund_analysis", CONTRACT_PATH)) == RECOMMENDED_FIELDS
    assert set(optional_fields_for_skill("fund-analysis", CONTRACT_PATH)) == OPTIONAL_FIELDS
    mapping = capability_field_mapping_for_skill("fund_analysis", CONTRACT_PATH)
    assert set(mapping) >= CAPABILITY_KEYS
    assert mapping["fund_benchmark"] == ["benchmarks", "benchmark", "fund_benchmark"]


def test_load_input_contracts_returns_plain_mapping() -> None:
    loaded = load_input_contracts(CONTRACT_PATH)
    assert loaded == _contracts_doc()
