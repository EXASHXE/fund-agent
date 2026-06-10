"""Tests for the v0.4.9-dev release-readiness audit note."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTE = ROOT / "docs" / "release-readiness-v0.4.9-dev.md"


def _text() -> str:
    return NOTE.read_text(encoding="utf-8").lower()


def _flat_text() -> str:
    return " ".join(_text().split())


def test_release_readiness_note_exists() -> None:
    assert NOTE.is_file()


def test_release_readiness_note_states_not_published_or_tagged() -> None:
    text = _flat_text()
    assert "not a release tag" in text
    assert "no tag was created" in text
    assert "no pypi or npm package was published" in text


def test_release_readiness_note_lists_working_host_surfaces() -> None:
    text = _text()
    for phrase in (
        "scripts/run_skill.py",
        "skill discovery",
        "fund_analysis",
        "--emit-report markdown",
        "decision_support",
        "thesis_generation",
        "news_research",
        "sentiment_analysis",
        "opencode plugin metadata + doc-reader",
    ):
        assert phrase in text


def test_release_readiness_note_states_host_responsibilities() -> None:
    text = _text()
    for phrase in (
        "data fetching",
        "provider sdks",
        "network access",
        "credentials",
        "orchestration",
        "memory",
        "retries",
        "final ux",
        "brokerage/order execution",
    ):
        assert phrase in text


def test_release_readiness_note_states_formal_boundaries() -> None:
    text = _text()
    flat = _flat_text().replace("`", "")
    assert "fund_analysis" in text and "does not emit formal `decision`" in text
    assert "thesis_generation" in text and "does not emit formal `decision`" in text
    assert "decision_support is the only runtime skill" in flat
    assert "executionledger" in text.replace(" ", "")


def test_release_readiness_note_states_runtime_boundaries() -> None:
    text = _flat_text()
    for phrase in (
        "source-checkout",
        "metadata + doc-reader only",
        "does not invoke python",
        "provider sdk integration or network calls",
        "broker/order execution",
        "autonomous planner, daemon, server, scheduler, or http api",
        "fixtures are fake/sample data only",
    ):
        assert phrase in text


def test_release_readiness_note_lists_expected_gates() -> None:
    text = _text()
    for phrase in (
        "python -m compileall src tests scripts",
        "python -m pytest -q",
        "node --check opencode.plugin.js",
        "bash scripts/check_plugin_gate.sh",
        "local build metadata dry-run may skip",
        "editable install smoke may skip",
    ):
        assert phrase in text
