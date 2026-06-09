"""Integration-level cross-skill error shape tests.

Verifies that representative failed outputs across all skills produce
canonical error objects with code, message, details (dict), and
recoverable (bool) fields.
"""

from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from src.skillpack.run_skill import run_bridge


ROOT = Path(__file__).resolve().parents[2]


def _run_bridge_captured(*, skill: str, input_text: str, emit_report: str | None = None) -> dict[str, Any]:
    import sys as _sys

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(input_text)
        f.flush()
        path = f.name

    old_stdout = _sys.stdout
    _sys.stdout = StringIO()
    try:
        run_bridge(skill_name=skill, input_path=path, input_text=input_text, emit_report=emit_report)
        output = _sys.stdout.getvalue()
    finally:
        _sys.stdout = old_stdout

    return json.loads(output.strip())


def _assert_canonical_error(error: object) -> None:
    assert isinstance(error, dict), f"error must be dict, got {type(error).__name__}: {error!r}"
    assert "code" in error, f"error missing 'code': {error}"
    assert "message" in error, f"error missing 'message': {error}"
    assert "details" in error, f"error missing 'details': {error}"
    assert "recoverable" in error, f"error missing 'recoverable': {error}"
    assert isinstance(error["code"], str) and len(error["code"]) > 0
    assert isinstance(error["message"], str) and len(error["message"]) > 0
    assert isinstance(error["details"], dict), f"details must be dict, got {type(error['details']).__name__}"
    assert isinstance(error["recoverable"], bool), f"recoverable must be bool, got {type(error['recoverable']).__name__}"


def _assert_envelope_errors_canonical(envelope: dict) -> None:
    errors = envelope.get("errors", [])
    assert isinstance(errors, list), f"errors must be list, got {type(errors).__name__}"
    for err in errors:
        _assert_canonical_error(err)


def _assert_bridge_error_canonical(envelope: dict) -> None:
    if "error" in envelope:
        _assert_canonical_error(envelope["error"])


class TestFundAnalysisErrorShape:
    def test_invalid_payload_shape(self):
        result = _run_bridge_captured(
            skill="fund_analysis",
            input_text='{"payload":"not a dict"}',
        )
        _assert_envelope_errors_canonical(result)

    def test_missing_required_payload(self):
        result = _run_bridge_captured(
            skill="fund_analysis",
            input_text='{"payload":{}}',
        )
        _assert_envelope_errors_canonical(result)


class TestDecisionSupportErrorShape:
    def test_contract_violation_active_buy_without_evidence(self):
        fixture_path = str(ROOT / "examples" / "decision_support" / "single_active_buy_without_evidence_invalid.json")
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        result = _run_bridge_captured(
            skill="decision_support",
            input_text=json.dumps(fixture),
        )
        _assert_envelope_errors_canonical(result)
        if result.get("status") == "FAILED":
            errors = result.get("errors", [])
            assert len(errors) > 0, "FAILED status should have errors"

    def test_missing_evidence_graph(self):
        result = _run_bridge_captured(
            skill="decision_support",
            input_text='{"payload":{"requested_action":"BUY"}}',
        )
        _assert_envelope_errors_canonical(result)


class TestNewsResearchErrorShape:
    def test_missing_mcp_capability(self):
        result = _run_bridge_captured(
            skill="news_research",
            input_text='{"payload":{"query":"test"}}',
        )
        _assert_envelope_errors_canonical(result)
        _assert_bridge_error_canonical(result)
        errors = result.get("errors", [])
        for err in errors:
            assert isinstance(err, dict)
            assert err.get("code") == "MISSING_MCP_CAPABILITY" or "MISSING_MCP_CAPABILITY" in str(err.get("code", ""))


class TestSentimentAnalysisErrorShape:
    def test_missing_mcp_capability(self):
        result = _run_bridge_captured(
            skill="sentiment_analysis",
            input_text='{"payload":{"query":"test"}}',
        )
        _assert_envelope_errors_canonical(result)
        _assert_bridge_error_canonical(result)
        errors = result.get("errors", [])
        for err in errors:
            assert isinstance(err, dict)
            assert err.get("code") == "MISSING_MCP_CAPABILITY" or "MISSING_MCP_CAPABILITY" in str(err.get("code", ""))


class TestThesisGenerationErrorShape:
    def test_malformed_input(self):
        result = _run_bridge_captured(
            skill="thesis_generation",
            input_text='{"payload":"not a dict"}',
        )
        _assert_envelope_errors_canonical(result)


class TestNoStringErrorsAcrossSkills:
    @pytest.mark.parametrize("skill,input_text", [
        ("fund_analysis", '{"payload":{}}'),
        ("decision_support", '{"payload":{"requested_action":"BUY"}}'),
        ("news_research", '{"payload":{"query":"test"}}'),
        ("sentiment_analysis", '{"payload":{"query":"test"}}'),
        ("thesis_generation", '{"payload":"not a dict"}'),
    ])
    def test_no_string_errors(self, skill, input_text):
        result = _run_bridge_captured(skill=skill, input_text=input_text)
        for err in result.get("errors", []):
            assert isinstance(err, dict), f"errors[] item is not dict in {skill}: {err!r}"
            assert not isinstance(err, str), f"errors[] item is a string in {skill}: {err!r}"
        if "error" in result:
            assert isinstance(result["error"], dict), f"top-level error is not dict in {skill}: {result['error']!r}"

    @pytest.mark.parametrize("skill,input_text", [
        ("fund_analysis", '{"payload":{}}'),
        ("decision_support", '{"payload":{"requested_action":"BUY"}}'),
        ("news_research", '{"payload":{"query":"test"}}'),
        ("sentiment_analysis", '{"payload":{"query":"test"}}'),
        ("thesis_generation", '{"payload":"not a dict"}'),
    ])
    def test_details_always_dict(self, skill, input_text):
        result = _run_bridge_captured(skill=skill, input_text=input_text)
        for err in result.get("errors", []):
            assert isinstance(err.get("details"), dict), f"details not dict in {skill}: {err!r}"
        if "error" in result:
            assert isinstance(result["error"].get("details"), dict), f"bridge error details not dict in {skill}: {result['error']!r}"

    @pytest.mark.parametrize("skill,input_text", [
        ("fund_analysis", '{"payload":{}}'),
        ("decision_support", '{"payload":{"requested_action":"BUY"}}'),
        ("news_research", '{"payload":{"query":"test"}}'),
        ("sentiment_analysis", '{"payload":{"query":"test"}}'),
        ("thesis_generation", '{"payload":"not a dict"}'),
    ])
    def test_recoverable_always_bool(self, skill, input_text):
        result = _run_bridge_captured(skill=skill, input_text=input_text)
        for err in result.get("errors", []):
            assert isinstance(err.get("recoverable"), bool), f"recoverable not bool in {skill}: {err!r}"
        if "error" in result:
            assert isinstance(result["error"].get("recoverable"), bool), f"bridge error recoverable not bool in {skill}: {result['error']!r}"
