"""Golden regression tests for decision_support JSON output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.golden.decision_support_golden import (
    DECISION_SUPPORT_GOLDEN_FIXTURES,
    UPDATE_COMMAND,
    normalize_bridge_json,
    run_decision_support_json,
    serialize_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]


def _intentional_update_message(path: Path) -> str:
    return (
        f"golden snapshot mismatch for {path}. If this decision_support behavior "
        f"change is intentional, run: {UPDATE_COMMAND}"
    )


@pytest.mark.parametrize("fixture", DECISION_SUPPORT_GOLDEN_FIXTURES)
def test_decision_support_json_snapshot_exists(fixture) -> None:
    assert fixture.json_snapshot_path.exists(), (
        f"Missing snapshot: {fixture.json_snapshot_path}. "
        f"Run: {UPDATE_COMMAND}"
    )


@pytest.mark.parametrize("fixture", DECISION_SUPPORT_GOLDEN_FIXTURES)
def test_decision_support_json_snapshot_matches_current_output(fixture) -> None:
    current = normalize_bridge_json(run_decision_support_json(fixture))
    expected_text = fixture.json_snapshot_path.read_text(encoding="utf-8")
    assert serialize_snapshot(current) == expected_text, _intentional_update_message(
        fixture.json_snapshot_path
    )


@pytest.mark.parametrize("fixture", DECISION_SUPPORT_GOLDEN_FIXTURES)
def test_decision_support_snapshots_contain_no_real_personal_data(fixture) -> None:
    text = fixture.json_snapshot_path.read_text(encoding="utf-8").lower()
    assert "password" not in text
    assert "token" not in text
    assert "api_key" not in text
    assert "secret" not in text
    assert "credential" not in text


def test_failure_message_mentions_generator_script() -> None:
    message = _intentional_update_message(Path("tests/golden/decision_support/example.json"))
    assert UPDATE_COMMAND in message
