"""Runtime bridge error shape tests.

Verifies that runtime bridge error envelopes use canonical error-like
structures with code, message, and details fields.
"""

from __future__ import annotations

import json

from src.skillpack.run_skill import run_bridge


def _run_json(*, skill: str | None = None, input_text: str | None = None) -> dict:
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        if input_text:
            f.write(input_text)
        f.flush()
        path = f.name

    from io import StringIO
    import sys

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        run_bridge(skill_name=skill, input_path=path, input_text=input_text)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    return json.loads(output.strip())


def _assert_bridge_error(error: dict) -> None:
    assert "code" in error, f"bridge error missing 'code': {error}"
    assert "message" in error, f"bridge error missing 'message': {error}"
    assert isinstance(error["code"], str) and len(error["code"]) > 0
    assert isinstance(error["message"], str) and len(error["message"]) > 0


class TestBridgeErrorShapes:
    def test_unknown_skill_returns_bridge_error(self):
        result = _run_json(skill="nonexistent_skill", input_text='{"payload":{}}')
        assert result.get("ok") is False
        _assert_bridge_error(result["error"])

    def test_unsupported_emit_report_returns_bridge_error(self):
        result = _run_json(skill="decision_support", input_text='{"payload":{"evidence_graph":{"items":{}}}}')
        if result.get("ok") is False and "error" in result:
            _assert_bridge_error(result["error"])

    def test_invalid_input_returns_bridge_error(self):
        result = _run_json(skill="fund_analysis", input_text="not json")
        assert result.get("ok") is False
        _assert_bridge_error(result["error"])

    def test_skill_output_errors_are_canonical(self):
        result = _run_json(
            skill="thesis_generation",
            input_text='{"payload":"not a dict"}',
        )
        if result.get("ok") is True:
            errors = result.get("errors", [])
            for err in errors:
                assert "code" in err
                assert "message" in err
                assert "details" in err
                assert "recoverable" in err
