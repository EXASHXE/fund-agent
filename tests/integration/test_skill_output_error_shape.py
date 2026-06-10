"""Integration-level cross-skill error shape tests.

Verifies that representative failed outputs across all skills produce
canonical error objects with code, message, details (dict), and
recoverable (bool) fields.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import project_root, run_bridge_inprocess_json
from tests.support.error_shape import (
    assert_envelope_errors_are_canonical,
    assert_top_level_error_is_canonical,
)

ROOT = project_root()


class TestFundAnalysisErrorShape:
    def test_invalid_payload_shape(self):
        result = run_bridge_inprocess_json(
            skill="fund_analysis",
            input_text='{"payload":"not a dict"}',
        )
        assert_envelope_errors_are_canonical(result)

    def test_missing_required_payload(self):
        result = run_bridge_inprocess_json(
            skill="fund_analysis",
            input_text='{"payload":{}}',
        )
        assert_envelope_errors_are_canonical(result)


class TestDecisionSupportErrorShape:
    def test_active_buy_without_evidence_downgrades_without_errors(self):
        fixture_path = str(ROOT / "examples" / "decision_support" / "single_active_buy_without_evidence_invalid.json")
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        result = run_bridge_inprocess_json(
            skill="decision_support",
            input_text=json.dumps(fixture),
        )
        assert result["status"] == "OK"
        assert result.get("errors") == []
        decision = result.get("artifacts", {}).get("decision") or {}
        assert decision.get("action") in {"WAIT", "HOLD"}
        assert "EVIDENCE_MISSING" in decision.get("decision_reason_codes", [])

    def test_missing_evidence_graph(self):
        result = run_bridge_inprocess_json(
            skill="decision_support",
            input_text='{"payload":{"requested_action":"BUY"}}',
        )
        assert_envelope_errors_are_canonical(result)


class TestNewsResearchErrorShape:
    def test_missing_mcp_capability(self):
        result = run_bridge_inprocess_json(
            skill="news_research",
            input_text='{"payload":{"query":"test"}}',
        )
        assert_envelope_errors_are_canonical(result)
        assert_top_level_error_is_canonical(result)
        errors = result.get("errors", [])
        for err in errors:
            assert isinstance(err, dict)
            assert err.get("code") == "MISSING_MCP_CAPABILITY" or "MISSING_MCP_CAPABILITY" in str(err.get("code", ""))


class TestSentimentAnalysisErrorShape:
    def test_missing_mcp_capability(self):
        result = run_bridge_inprocess_json(
            skill="sentiment_analysis",
            input_text='{"payload":{"query":"test"}}',
        )
        assert_envelope_errors_are_canonical(result)
        assert_top_level_error_is_canonical(result)
        errors = result.get("errors", [])
        for err in errors:
            assert isinstance(err, dict)
            assert err.get("code") == "MISSING_MCP_CAPABILITY" or "MISSING_MCP_CAPABILITY" in str(err.get("code", ""))


class TestThesisGenerationErrorShape:
    def test_malformed_input(self):
        result = run_bridge_inprocess_json(
            skill="thesis_generation",
            input_text='{"payload":"not a dict"}',
        )
        assert_envelope_errors_are_canonical(result)


class TestNoStringErrorsAcrossSkills:
    @pytest.mark.parametrize("skill,input_text", [
        ("fund_analysis", '{"payload":{}}'),
        ("decision_support", '{"payload":{"requested_action":"BUY"}}'),
        ("news_research", '{"payload":{"query":"test"}}'),
        ("sentiment_analysis", '{"payload":{"query":"test"}}'),
        ("thesis_generation", '{"payload":"not a dict"}'),
    ])
    def test_no_string_errors(self, skill, input_text):
        result = run_bridge_inprocess_json(skill=skill, input_text=input_text)
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
        result = run_bridge_inprocess_json(skill=skill, input_text=input_text)
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
        result = run_bridge_inprocess_json(skill=skill, input_text=input_text)
        for err in result.get("errors", []):
            assert isinstance(err.get("recoverable"), bool), f"recoverable not bool in {skill}: {err!r}"
        if "error" in result:
            assert isinstance(result["error"].get("recoverable"), bool), f"bridge error recoverable not bool in {skill}: {result['error']!r}"
