"""Golden regression tests for externally visible fund_analysis output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.golden.fund_analysis_golden import (
    FORMAL_DECISION_ARTIFACTS,
    FUND_ANALYSIS_GOLDEN_FIXTURES,
    UPDATE_COMMAND,
    normalize_bridge_json,
    normalize_markdown,
    run_fund_analysis_json,
    run_fund_analysis_markdown,
    serialize_snapshot,
)


def _intentional_update_message(path: Path) -> str:
    return (
        f"golden snapshot mismatch for {path}. If this fund_analysis behavior "
        f"change is intentional, run: {UPDATE_COMMAND}"
    )


@pytest.mark.parametrize("fixture", FUND_ANALYSIS_GOLDEN_FIXTURES)
def test_fund_analysis_json_snapshot_exists(fixture) -> None:
    assert fixture.json_snapshot_path.exists()


@pytest.mark.parametrize("fixture", FUND_ANALYSIS_GOLDEN_FIXTURES)
def test_fund_analysis_json_snapshot_matches_current_output(fixture) -> None:
    current = normalize_bridge_json(run_fund_analysis_json(fixture))
    expected_text = fixture.json_snapshot_path.read_text(encoding="utf-8")
    assert serialize_snapshot(current) == expected_text, _intentional_update_message(
        fixture.json_snapshot_path
    )


@pytest.mark.parametrize(
    "fixture",
    [item for item in FUND_ANALYSIS_GOLDEN_FIXTURES if item.markdown_snapshot],
)
def test_fund_analysis_markdown_snapshot_exists(fixture) -> None:
    assert fixture.markdown_snapshot_path.exists()


@pytest.mark.parametrize(
    "fixture",
    [item for item in FUND_ANALYSIS_GOLDEN_FIXTURES if item.markdown_snapshot],
)
def test_fund_analysis_markdown_snapshot_matches_current_output(fixture) -> None:
    current = normalize_markdown(run_fund_analysis_markdown(fixture))
    expected = normalize_markdown(
        fixture.markdown_snapshot_path.read_text(encoding="utf-8")
    )
    assert current == expected, _intentional_update_message(
        fixture.markdown_snapshot_path
    )


@pytest.mark.parametrize("fixture", FUND_ANALYSIS_GOLDEN_FIXTURES)
def test_json_snapshots_do_not_contain_formal_decision_artifacts(fixture) -> None:
    snapshot = json.loads(fixture.json_snapshot_path.read_text(encoding="utf-8"))
    artifacts = snapshot.get("artifacts") or {}
    assert isinstance(artifacts, dict)
    assert not (FORMAL_DECISION_ARTIFACTS & set(artifacts))


@pytest.mark.parametrize(
    "fixture",
    [item for item in FUND_ANALYSIS_GOLDEN_FIXTURES if item.markdown_snapshot],
)
def test_markdown_snapshots_do_not_contain_formal_decision_headings(fixture) -> None:
    text = fixture.markdown_snapshot_path.read_text(encoding="utf-8").lower()
    assert "## decision" not in text
    assert "## decisions" not in text
    assert "## execution ledger" not in text
    assert "## execution ledgers" not in text


def test_failure_message_mentions_generator_script() -> None:
    message = _intentional_update_message(Path("tests/golden/example.json"))
    assert UPDATE_COMMAND in message
