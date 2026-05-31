"""Contract freeze documentation tests."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/CONTRACT_FREEZE.md")


def _content() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_contract_freeze_doc_exists():
    assert DOC_PATH.exists()


def test_mentions_skill_input():
    assert "SkillInput" in _content()


def test_mentions_skill_output():
    assert "SkillOutput" in _content()


def test_mentions_evidence_item():
    assert "EvidenceItem" in _content()


def test_mentions_evidence_graph():
    assert "EvidenceGraph" in _content()


def test_mentions_decision():
    assert "Decision" in _content()


def test_mentions_execution_ledger():
    assert "ExecutionLedger" in _content()


def test_mentions_mcp_host_adapter():
    assert "MCPHostAdapter" in _content()


def test_mentions_skillpack_v1():
    assert "skillpack.v1" in _content()
