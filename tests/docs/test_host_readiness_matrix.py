"""Tests for docs/host-readiness-matrix.md."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text() -> str:
    return (ROOT / "docs" / "host-readiness-matrix.md").read_text(encoding="utf-8").lower()


def test_matrix_exists():
    assert (ROOT / "docs" / "host-readiness-matrix.md").is_file()


def test_matrix_mentions_source_checkout():
    assert "source checkout" in _text()


def test_matrix_mentions_opencode_plugin_metadata_doc_reader():
    text = _text()
    assert "opencode plugin" in text
    assert "metadata" in text
    assert "doc-reader" in text or "doc reader" in text


def test_matrix_mentions_runtime_bridge():
    assert "runtime bridge" in _text()


def test_matrix_says_host_owns_data_and_network():
    text = _text()
    for phrase in ("data fetching", "provider sdk", "network", "credentials"):
        assert phrase in text


def test_matrix_says_no_broker_order_execution():
    assert "no broker" in _text() or "broker" in _text()


def test_matrix_says_decision_support_only_decision_runtime():
    text = _text()
    assert "decision_support" in text
    assert "only" in text


def test_matrix_says_fund_analysis_and_thesis_no_formal_decisions():
    text = _text()
    assert "fund_analysis" in text
    assert "thesis_generation" in text
    assert "not produce formal" in text or "do not produce" in text


def test_matrix_does_not_mention_deprecated_src_surfaces():
    text = _text()
    deprecated = (
        "src/core", "src/infra", "src/workflows",
        "researchos", "legacy system",
    )
    for term in deprecated:
        assert term not in text, f"matrix mentions deprecated term: {term}"
