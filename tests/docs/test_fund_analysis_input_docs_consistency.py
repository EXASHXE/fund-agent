"""Drift checks between fund_analysis input YAML and Markdown docs."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "skillpack" / "input-contracts.yaml"
DOC_PATH = ROOT / "docs" / "contracts" / "fund-analysis-input-contract.v1.md"


def _fund_contract() -> dict:
    data = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    return data["contracts"]["fund_analysis"]


def test_fund_analysis_input_doc_exists() -> None:
    assert DOC_PATH.exists()


def test_minimum_modes_appear_in_markdown_doc() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    for mode in _fund_contract()["minimum_required"]:
        assert mode["mode"] in content


def test_recommended_fields_appear_in_markdown_doc() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    for field in _fund_contract()["recommended_fields"]:
        assert field["key"] in content


def test_optional_fields_appear_in_markdown_doc() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    for field in _fund_contract()["optional_fields"]:
        assert field["key"] in content


def test_host_data_capability_keys_appear_in_markdown_doc() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    for capability in _fund_contract()["host_data_capability_fields"]:
        assert capability in content


def test_doc_references_related_contracts() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "skillpack/input-contracts.yaml" in content
    assert "fund-analysis-artifacts.v1.md" in content
    assert "report-output-contract.v1.md" in content


def test_doc_states_host_data_and_validation_boundaries() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "`fund-agent` does not fetch" in content
    assert "Validation is structural and host-assistive" in content
    assert "not a guarantee of investment correctness" in content
    assert "Formal action decisions belong to `decision_support`" in content
