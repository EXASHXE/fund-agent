"""Runtime bridge error shape tests — subprocess-level end-to-end.

Verifies that runtime bridge error envelopes produced by real CLI
invocations use canonical error objects with code, message, details
(dict), and recoverable (bool) fields.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_SKILL_SCRIPT = ROOT / "scripts" / "run_skill.py"


def _run_bridge(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(RUN_SKILL_SCRIPT)] + args
    return subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(ROOT))


def _stdout_text(result: subprocess.CompletedProcess) -> str:
    return result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")


def _parse_json(stdout: str) -> dict:
    return json.loads(stdout)


def _write_temp_input(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f)
    f.flush()
    f.close()
    return f.name


def _assert_canonical_error(error: object) -> None:
    assert isinstance(error, dict), f"error must be dict, got {type(error).__name__}: {error!r}"
    assert "code" in error, f"error missing 'code': {error}"
    assert "message" in error, f"error missing 'message': {error}"
    assert "details" in error, f"error missing 'details': {error}"
    assert "recoverable" in error, f"error missing 'recoverable': {error}"
    assert isinstance(error["code"], str) and len(error["code"]) > 0, f"code must be non-empty str: {error['code']!r}"
    assert isinstance(error["message"], str) and len(error["message"]) > 0, f"message must be non-empty str: {error['message']!r}"
    assert isinstance(error["details"], dict), f"details must be dict, got {type(error['details']).__name__}: {error['details']!r}"
    assert isinstance(error["recoverable"], bool), f"recoverable must be bool, got {type(error['recoverable']).__name__}: {error['recoverable']!r}"


def _assert_envelope_errors_canonical(envelope: dict) -> None:
    errors = envelope.get("errors", [])
    assert isinstance(errors, list), f"errors must be list, got {type(errors).__name__}"
    for err in errors:
        _assert_canonical_error(err)


def _assert_bridge_error_canonical(envelope: dict) -> None:
    if "error" in envelope:
        _assert_canonical_error(envelope["error"])


class TestBridgeMissingSkill:
    def test_missing_skill_returns_canonical_error(self):
        result = _run_bridge(["--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        assert data.get("ok") is False
        _assert_bridge_error_canonical(data)

    def test_missing_skill_error_has_code_invalid_input(self):
        result = _run_bridge(["--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        assert data["error"]["code"] == "INVALID_INPUT"


class TestBridgeUnknownSkill:
    def test_unknown_skill_returns_canonical_error(self):
        result = _run_bridge(["--skill", "nonexistent_skill", "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        assert data.get("ok") is False
        _assert_bridge_error_canonical(data)
        assert data["error"]["code"] == "UNKNOWN_SKILL"


class TestBridgeInvalidJsonInput:
    def test_invalid_json_returns_canonical_error(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        f.write("not json at all")
        f.flush()
        f.close()
        result = _run_bridge(["--skill", "fund_analysis", "--input", f.name, "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        assert data.get("ok") is False
        _assert_bridge_error_canonical(data)
        assert data["error"]["code"] == "INVALID_INPUT"

    def test_input_payload_not_object(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump([1, 2, 3], f)
        f.flush()
        f.close()
        result = _run_bridge(["--skill", "fund_analysis", "--input", f.name, "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        assert data.get("ok") is False
        _assert_bridge_error_canonical(data)
        assert data["error"]["code"] == "INVALID_INPUT"


class TestBridgeUnsupportedEmitReport:
    def test_emit_report_markdown_for_decision_support(self):
        inp = _write_temp_input({"payload": {"evidence_graph": {"items": {}}}})
        result = _run_bridge(["--skill", "decision_support", "--input", inp, "--emit-report", "markdown", "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        assert data.get("ok") is False
        _assert_bridge_error_canonical(data)
        assert data["error"]["code"] == "UNSUPPORTED_EMIT_REPORT"


class TestSkillLevelErrorsCanonical:
    def test_decision_support_active_buy_without_evidence(self):
        inp = str(ROOT / "examples" / "decision_support" / "single_active_buy_without_evidence_invalid.json")
        result = _run_bridge(["--skill", "decision_support", "--input", inp, "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        _assert_envelope_errors_canonical(data)

    def test_news_research_without_mcp(self):
        inp = _write_temp_input({"payload": {"query": "test"}})
        result = _run_bridge(["--skill", "news_research", "--input", inp, "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        _assert_envelope_errors_canonical(data)
        _assert_bridge_error_canonical(data)

    def test_sentiment_analysis_without_mcp(self):
        inp = _write_temp_input({"payload": {"query": "test"}})
        result = _run_bridge(["--skill", "sentiment_analysis", "--input", inp, "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        _assert_envelope_errors_canonical(data)
        _assert_bridge_error_canonical(data)


class TestNoStringErrorsInOutput:
    def test_bridge_errors_are_never_strings(self):
        inp = _write_temp_input({"payload": {"query": "test"}})
        result = _run_bridge(["--skill", "news_research", "--input", inp, "--pretty"])
        stdout = _stdout_text(result)
        data = _parse_json(stdout)
        for err in data.get("errors", []):
            assert isinstance(err, dict), f"errors[] item is not dict: {err!r}"
            assert not isinstance(err, str), f"errors[] item is a string: {err!r}"
        if "error" in data:
            assert isinstance(data["error"], dict), f"top-level error is not dict: {data['error']!r}"
