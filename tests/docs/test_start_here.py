"""Docs tests for START_HERE.md."""

from __future__ import annotations

from pathlib import Path

DOC_PATH = Path("docs/START_HERE.md")


def _content() -> str:
    return DOC_PATH.read_text(encoding="utf-8").lower()


def test_start_here_exists():
    assert DOC_PATH.exists()


def test_references_runtime_bridge():
    assert "runtime bridge" in _content()


def test_references_list_skills():
    assert "--list-skills" in _content()


def test_references_explain_input():
    assert "--explain-input" in _content()


def test_references_validate_input():
    assert "--validate-input" in _content()


def test_references_emit_report_markdown():
    assert "--emit-report markdown" in _content()


def test_references_decision_support():
    assert "decision_support" in _content()


def test_references_host_integrations():
    assert "docs/host-integrations/readme.md" in _content() or "host-integrations" in _content()


def test_references_fund_analysis_input_contract():
    assert "fund-analysis-input-contract" in _content()


def test_references_fund_analysis_artifact_contract():
    assert "fund-analysis-artifacts" in _content()


def test_references_decision_support_contract():
    assert "decision-support-contract" in _content()


def test_states_host_owns_data_fetching_providers():
    text = _content()
    assert "host owns" in text or "host" in text
    assert "data fetching" in text or "provider sdk" in text or "provider" in text


def test_states_fund_analysis_does_not_produce_formal_decisions():
    text = _content()
    assert "decision" in text
    assert "executionledger" in text or "execution ledger" in text
    assert "only" in text and "decision_support" in text


def test_states_decision_support_is_only_formal_output():
    text = _content()
    assert "only" in text and "decision_support" in text
    assert "executionledger" in text or "execution_ledger" in text or "execution ledger" in text


def test_does_not_present_opencode_plugin_as_python_runtime():
    text = _content()
    assert "does not invoke python" in text or "doc-reader only" in text
