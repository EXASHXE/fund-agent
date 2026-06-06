"""Contract tests for fund_analysis artifact contract v1."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.skillpack.artifact_contracts import (
    artifact_keys_for_skill,
    forbidden_artifacts_for_skill,
    get_skill_artifact_contract,
    load_artifact_contracts,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "skillpack" / "artifact-contracts.yaml"
DOC_PATH = ROOT / "docs" / "contracts" / "fund-analysis-artifacts.v1.md"

REQUIRED_ARTIFACT_FIELDS = {
    "key",
    "category",
    "required",
    "type",
    "produced_when",
    "description",
}

MINIMUM_PUBLIC_KEYS = {
    "fund_analysis_report",
    "portfolio_summary",
    "position_summary",
    "exposure_summary",
    "risk_flags",
    "pnl_summary",
    "trade_budget",
    "short_term_trade_budget",
    "dca_plan_review",
    "transaction_summary",
    "cost_basis_summary",
    "reconciliation",
    "suggested_rebalance_plan",
    "data_completeness",
    "analysis_coverage",
    "report_limitations",
    "report_sections",
    "report_outline",
    "report_quality_gate",
    "warnings",
}

FORMAL_DECISION_ARTIFACTS = {
    "decision",
    "decisions",
    "execution_ledger",
    "execution_ledgers",
}


def _contracts_doc() -> dict:
    assert CONTRACT_PATH.exists()
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def _fund_contract() -> dict:
    return _contracts_doc()["contracts"]["fund_analysis"]


def _artifact_keys() -> list[str]:
    return [artifact["key"] for artifact in _fund_contract()["artifacts"]]


def test_artifact_contract_yaml_exists_and_parses() -> None:
    data = _contracts_doc()
    assert data["schema_version"] == "artifact-contracts.v1"
    assert "fund_analysis" in data["contracts"]


def test_fund_analysis_contract_metadata() -> None:
    contract = _fund_contract()
    assert contract["doc"] == "docs/contracts/fund-analysis-artifacts.v1.md"
    assert contract["runtime_id"] == "fund_analysis"
    assert contract["doc_slug"] == "fund-analysis"
    assert DOC_PATH.exists()


def test_artifact_keys_are_unique() -> None:
    keys = _artifact_keys()
    assert len(keys) == len(set(keys))


def test_artifact_categories_exist_and_fields_are_complete() -> None:
    contract = _fund_contract()
    categories = set(contract["artifact_categories"])
    assert categories >= {
        "core_portfolio",
        "ledger_and_pnl",
        "exposure_and_risk",
        "planning_and_budget",
        "optional_context",
        "report_output",
        "diagnostics",
    }
    for artifact in contract["artifacts"]:
        missing = REQUIRED_ARTIFACT_FIELDS - set(artifact)
        assert not missing, f"{artifact.get('key', '<unknown>')} missing {missing}"
        assert artifact["category"] in categories
        assert isinstance(artifact["required"], bool)


def test_forbidden_artifacts_and_status_values_are_declared() -> None:
    contract = _fund_contract()
    forbidden = set(contract["forbidden_artifacts"])
    assert {"decision", "execution_ledger"} <= forbidden
    assert FORMAL_DECISION_ARTIFACTS <= forbidden
    assert {"OK", "PARTIAL", "FAILED"} <= set(contract["status_values"])


def test_required_public_keys_are_documented_in_yaml() -> None:
    keys = set(_artifact_keys())
    assert MINIMUM_PUBLIC_KEYS <= keys


def test_formal_decision_artifacts_are_not_public_artifact_keys() -> None:
    assert not (set(_artifact_keys()) & FORMAL_DECISION_ARTIFACTS)


def test_artifact_contract_loader_accepts_runtime_id_and_doc_slug() -> None:
    by_runtime = get_skill_artifact_contract("fund_analysis", CONTRACT_PATH)
    by_slug = get_skill_artifact_contract("fund-analysis", CONTRACT_PATH)
    assert by_runtime == by_slug
    assert artifact_keys_for_skill("fund_analysis", CONTRACT_PATH) == _artifact_keys()
    assert set(forbidden_artifacts_for_skill("fund-analysis", CONTRACT_PATH)) == set(
        _fund_contract()["forbidden_artifacts"]
    )


def test_load_artifact_contracts_returns_plain_mapping() -> None:
    loaded = load_artifact_contracts(CONTRACT_PATH)
    assert loaded == _contracts_doc()
