"""Golden snapshot tests for thesis_generation."""

from __future__ import annotations

import pytest

from tests.golden.thesis_generation_golden import (
    THESIS_GENERATION_GOLDEN_FIXTURES,
    normalize_bridge_json,
    run_thesis_generation_json,
    serialize_snapshot,
    UPDATE_COMMAND,
)


@pytest.mark.parametrize("fixture", THESIS_GENERATION_GOLDEN_FIXTURES, ids=lambda f: f.snapshot_name)
def test_thesis_generation_golden_snapshot(fixture):
    output = run_thesis_generation_json(fixture)
    normalized = normalize_bridge_json(output)

    if not fixture.json_snapshot_path.exists():
        pytest.skip(
            f"Golden snapshot {fixture.json_snapshot_path} does not exist. "
            f"Run `{UPDATE_COMMAND}` to create it."
        )

    expected_text = fixture.json_snapshot_path.read_text(encoding="utf-8")
    actual_text = serialize_snapshot(normalized)
    assert actual_text == expected_text, (
        f"Golden snapshot mismatch for {fixture.snapshot_name}. "
        f"Run `{UPDATE_COMMAND}` to update if intentional."
    )


from tests.support.formal_boundary import FORMAL_DECISION_ARTIFACT_KEYS


@pytest.mark.parametrize("fixture", THESIS_GENERATION_GOLDEN_FIXTURES, ids=lambda f: f.snapshot_name)
def test_thesis_generation_no_formal_decision_artifacts(fixture):
    output = run_thesis_generation_json(fixture)
    artifacts = output.get("artifacts", {})
    for key in FORMAL_DECISION_ARTIFACT_KEYS:
        assert key not in artifacts, f"Forbidden artifact '{key}' in thesis_generation output"
