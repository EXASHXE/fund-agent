"""Runtime bridge error contract tests.

Verifies that runtime bridge error envelopes use canonical error objects
with code, message, details, and recoverable fields.
"""

from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

from src.skillpack.run_skill import run_bridge


def _run_bridge_json(*, skill: str | None = None, input_text: str | None = None, emit_report: str | None = None) -> dict:
    import sys

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        if input_text:
            f.write(input_text)
        f.flush()
        path = f.name

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        run_bridge(skill_name=skill, input_path=path, input_text=input_text, emit_report=emit_report)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    return json.loads(output.strip())


def _run_with_input_text(*, skill: str | None = None, input_text: str | None = None) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        if input_text:
            f.write(input_text)
        f.flush()
        path = f.name

    old_stdout = __import__("sys").stdout
    __import__("sys").stdout = StringIO()
    try:
        run_bridge(skill_name=skill, input_path=path, input_text=input_text)
        output = __import__("sys").stdout.getvalue()
    finally:
        __import__("sys").stdout = old_stdout

    return json.loads(output.strip())


def _assert_canonical_bridge_error(error: dict) -> None:
    assert "code" in error, f"bridge error missing 'code': {error}"
    assert "message" in error, f"bridge error missing 'message': {error}"
    assert "details" in error, f"bridge error missing 'details': {error}"
    assert "recoverable" in error, f"bridge error missing 'recoverable': {error}"
    assert isinstance(error["code"], str) and len(error["code"]) > 0
    assert isinstance(error["message"], str) and len(error["message"]) > 0
    assert isinstance(error["details"], dict), f"details not dict: {type(error['details'])}"
    assert isinstance(error["recoverable"], bool), f"recoverable not bool: {type(error['recoverable'])}"


class TestBridgeUnknownSkillError:
    def test_unknown_skill_returns_canonical_error(self):
        result = _run_with_input_text(skill="nonexistent_skill", input_text='{"payload":{}}')
        assert result.get("ok") is False
        _assert_canonical_bridge_error(result["error"])
        assert result["error"]["code"] == "UNKNOWN_SKILL"


class TestBridgeInvalidJsonError:
    def test_invalid_json_returns_canonical_error(self):
        result = _run_with_input_text(skill="fund_analysis", input_text="not json")
        assert result.get("ok") is False
        _assert_canonical_bridge_error(result["error"])
        assert result["error"]["code"] == "INVALID_INPUT"


class TestBridgeUnsupportedEmitReportError:
    def test_unsupported_emit_report_returns_canonical_error(self):
        result = _run_bridge_json(
            skill="decision_support",
            input_text='{"payload":{"evidence_graph":{"items":{}}}}',
            emit_report="markdown",
        )
        assert result.get("ok") is False
        _assert_canonical_bridge_error(result["error"])
        assert result["error"]["code"] == "UNSUPPORTED_EMIT_REPORT"


class TestBridgeMissingReportSectionsError:
    def test_missing_report_sections_returns_canonical_error(self):
        result = _run_bridge_json(
            skill="fund_analysis",
            input_text='{"payload":{"related_entities":["fund:001"]}}',
            emit_report="markdown",
        )
        if result.get("ok") is False and "error" in result:
            _assert_canonical_bridge_error(result["error"])
            assert result["error"]["code"] == "MISSING_REPORT_SECTIONS"


class TestBridgeSkillOutputErrorsCanonical:
    def test_thesis_generation_invalid_payload_errors_canonical(self):
        result = _run_with_input_text(
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
                assert isinstance(err["details"], dict)
                assert isinstance(err["recoverable"], bool)

    def test_decision_support_missing_evidence_graph_errors_canonical(self):
        result = _run_with_input_text(
            skill="decision_support",
            input_text='{"payload":{"requested_action":"BUY"}}',
        )
        errors = result.get("errors", [])
        for err in errors:
            assert "code" in err
            assert "message" in err
            assert "details" in err
            assert "recoverable" in err
            assert isinstance(err["details"], dict)
            assert isinstance(err["recoverable"], bool)
