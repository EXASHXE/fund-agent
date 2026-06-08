"""Decision support contract YAML tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.skillpack.decision_contracts import (
    active_actions_for_skill,
    decision_artifact_keys,
    get_decision_contract,
    load_decision_contracts,
    passive_actions_for_skill,
)

DECISION_CONTRACTS_PATH = Path("skillpack/decision-contracts.yaml")


def _doc() -> dict:
    return yaml.safe_load(DECISION_CONTRACTS_PATH.read_text(encoding="utf-8"))


def _contract() -> dict:
    return _doc()["contracts"]["decision_support"]


def test_decision_contracts_yaml_exists_and_parses():
    assert DECISION_CONTRACTS_PATH.exists()
    data = _doc()
    assert isinstance(data, dict)


def test_schema_version():
    assert _doc()["schema_version"] == "decision-contracts.v1"


def test_contracts_decision_support_exists():
    assert "decision_support" in _doc()["contracts"]


def test_runtime_id():
    assert _contract()["runtime_id"] == "decision_support"


def test_doc_slug():
    assert _contract()["doc_slug"] == "decision-support"


def test_doc_points_to_markdown():
    assert _contract()["doc"] == "docs/contracts/decision-support-contract.v1.md"


def test_formal_output_owner_is_true():
    assert _contract()["formal_output_owner"] is True


def test_consumes_includes_evidence_graph():
    assert "EvidenceGraph" in _contract()["consumes"]


def test_formal_outputs_include_decision_and_execution_ledger():
    assert "Decision" in _contract()["formal_outputs"]
    assert "ExecutionLedger" in _contract()["formal_outputs"]


def test_active_actions():
    assert set(_contract()["active_actions"]) == {"BUY", "SELL", "INCREASE", "REDUCE"}


def test_passive_actions():
    assert set(_contract()["passive_actions"]) == {"WAIT", "HOLD", "PAUSE_DCA"}


def test_input_modes():
    modes = {m["mode"] for m in _contract()["input_modes"]}
    assert "single_decision" in modes
    assert "trade_plan_decision" in modes


def test_artifact_keys():
    keys = {a["key"] for a in _contract()["artifact_keys"]}
    expected = {"decision", "decisions", "execution_ledger", "decision_status",
                "decision_count", "audit_trail", "warnings"}
    assert keys == expected


def test_status_values():
    assert set(_contract()["status_values"]) == {"OK", "PARTIAL", "FAILED"}


def test_boundary_rules_mention_only_decision_support():
    rules_text = " ".join(_contract()["boundary_rules"])
    assert "only decision_support may emit" in rules_text.lower() or \
           "only decision_support may emit decision" in rules_text.lower()


def test_loader_load_decision_contracts():
    result = load_decision_contracts()
    assert isinstance(result, dict)
    assert result["schema_version"] == "decision-contracts.v1"


def test_loader_get_decision_contract_with_runtime_id():
    contract = get_decision_contract("decision_support")
    assert contract["runtime_id"] == "decision_support"


def test_loader_get_decision_contract_with_doc_slug():
    contract = get_decision_contract("decision-support")
    assert contract["runtime_id"] == "decision_support"


def test_loader_decision_artifact_keys():
    keys = decision_artifact_keys("decision_support")
    assert "decision" in keys
    assert "execution_ledger" in keys
    assert "warnings" in keys


def test_loader_active_actions():
    actions = active_actions_for_skill("decision_support")
    assert "BUY" in actions
    assert "SELL" in actions


def test_loader_passive_actions():
    actions = passive_actions_for_skill("decision_support")
    assert "WAIT" in actions
    assert "HOLD" in actions


def test_loader_accepts_hyphen_slug():
    keys_hyphen = decision_artifact_keys("decision-support")
    keys_underscore = decision_artifact_keys("decision_support")
    assert keys_hyphen == keys_underscore


def test_loader_raises_for_unknown_skill():
    try:
        get_decision_contract("nonexistent_skill")
        assert False, "expected KeyError"
    except KeyError:
        pass
