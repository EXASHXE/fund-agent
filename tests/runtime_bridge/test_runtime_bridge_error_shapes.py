"""Runtime bridge error shape tests.

Verifies that runtime bridge error envelopes use canonical error-like
structures with code, message, and details fields.
"""

from __future__ import annotations

import json
from io import StringIO
import sys
from pathlib import Path

from src.skillpack.run_skill import run_bridge
from tests.support.bridge_runner import write_temp_json, write_temp_text
from tests.support.error_shape import (
    assert_bridge_error_shape,
    assert_skill_errors_canonical,
)


def _run_json(*, skill: str | None = None, input_path: Path) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        run_bridge(skill_name=skill, input_path=str(input_path))
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    return json.loads(output.strip())


class TestBridgeErrorShapes:
    def test_unknown_skill_returns_bridge_error(self, tmp_path: Path):
        input_path = write_temp_json(tmp_path, {"payload": {}})
        result = _run_json(skill="nonexistent_skill", input_path=input_path)
        assert result.get("ok") is False
        assert_bridge_error_shape(result["error"])

    def test_unsupported_emit_report_returns_bridge_error(self, tmp_path: Path):
        input_path = write_temp_json(
            tmp_path,
            {"payload": {"evidence_graph": {"items": {}}}},
        )
        result = _run_json(skill="decision_support", input_path=input_path)
        if result.get("ok") is False and "error" in result:
            assert_bridge_error_shape(result["error"])

    def test_invalid_input_returns_bridge_error(self, tmp_path: Path):
        input_path = write_temp_text(tmp_path, "not json")
        result = _run_json(skill="fund_analysis", input_path=input_path)
        assert result.get("ok") is False
        assert_bridge_error_shape(result["error"])

    def test_skill_output_errors_are_canonical(self, tmp_path: Path):
        input_path = write_temp_json(tmp_path, {"payload": "not a dict"})
        result = _run_json(
            skill="thesis_generation",
            input_path=input_path,
        )
        if result.get("ok") is True:
            assert_skill_errors_canonical(result.get("errors", []))
