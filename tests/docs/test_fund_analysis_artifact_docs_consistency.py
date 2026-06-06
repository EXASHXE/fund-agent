"""Drift checks between fund_analysis artifact YAML and Markdown docs."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "skillpack" / "artifact-contracts.yaml"
DOC_PATH = ROOT / "docs" / "contracts" / "fund-analysis-artifacts.v1.md"


def _fund_contract() -> dict:
    data = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["fund_analysis"]


def test_fund_analysis_artifact_doc_exists() -> None:
    assert DOC_PATH.exists()


def test_all_yaml_artifact_keys_appear_in_markdown_doc() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    for artifact in _fund_contract()["artifacts"]:
        assert artifact["key"] in content


def test_forbidden_artifacts_appear_in_decision_boundary() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "Decision Boundary" in content
    for forbidden in _fund_contract()["forbidden_artifacts"]:
        assert forbidden in content


def test_doc_references_report_output_contract() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "report-output-contract.v1.md" in content


def test_doc_assigns_formal_decisions_to_decision_support() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "Formal decisions belong only to `decision_support`" in content
    assert "Only `decision_support` may produce formal `Decision`" in content
    assert "`ExecutionLedger`" in content
