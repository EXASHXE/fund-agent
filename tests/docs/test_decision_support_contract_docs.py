"""Decision support contract documentation drift tests.

Verifies that the human-readable Markdown contract doc and the machine-readable
YAML stay in sync.
"""

from __future__ import annotations

from pathlib import Path

from src.skillpack.decision_contracts import (
    active_actions_for_skill,
    decision_artifact_keys,
    get_decision_contract,
    passive_actions_for_skill,
)

MARKDOWN_DOC = Path("docs/contracts/decision-support-contract.v1.md")
DECISION_CONTRACTS_YAML = "skillpack/decision-contracts.yaml"


def _content() -> str:
    return MARKDOWN_DOC.read_text(encoding="utf-8").lower()


def contract() -> dict:
    return get_decision_contract("decision_support", DECISION_CONTRACTS_YAML)


def test_markdown_doc_exists():
    assert MARKDOWN_DOC.exists()


def test_every_active_action_appears_in_markdown():
    for action in active_actions_for_skill("decision_support", DECISION_CONTRACTS_YAML):
        assert action.lower() in _content()


def test_every_passive_action_appears_in_markdown():
    for action in passive_actions_for_skill("decision_support", DECISION_CONTRACTS_YAML):
        # PAUSE_DCA appears as an acronym in the doc
        assert action.lower() in _content() or action.lower().replace("_", " ") in _content()


def test_every_input_mode_appears_in_markdown():
    contract_data = contract()
    for mode_obj in contract_data.get("input_modes") or []:
        mode_name = mode_obj.get("mode", "")
        assert mode_name in _content().replace("-", " ")


def test_every_artifact_key_appears_in_markdown():
    for key in decision_artifact_keys("decision_support", DECISION_CONTRACTS_YAML):
        assert key in _content()


def test_markdown_references_decision_contracts_yaml():
    assert "skillpack/decision-contracts.yaml" in _content()


def test_markdown_references_skill_md():
    text = _content()
    assert "skills/decision-support/skill.md" in text


def test_markdown_states_only_decision_support_may_emit_formal_decisions():
    text = _content()
    assert "only" in text
    assert "decision_support" in text
    assert "formal decision" in text or "formal `decision`" in text or (
        "formal decision" in text
    )
    assert "executionledger" in text or "execution ledger" in text or (
        "execution_ledger" in text
    )


def test_markdown_states_fund_analysis_plans_are_not_formal_decisions():
    text = _content()
    assert (
        "suggested_rebalance_plan" in text
        or "suggested plan" in text
    )
    assert "not a formal decision" in text or "not an order" in text or (
        "not formal" in text
    )


def test_markdown_states_host_owns_data_fetching():
    text = _content()
    assert "host owns" in text or "host" in text
    assert "data fetching" in text or "provider sdk" in text or "provider" in text


def test_markdown_states_decision_support_does_not_execute_trades():
    text = _content()
    assert "does not execute trade" in text or "does not execute trade" in text
