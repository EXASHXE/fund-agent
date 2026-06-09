"""Runtime bridge error shape tests — subprocess-level end-to-end.

Verifies that runtime bridge error envelopes produced by real CLI
invocations use canonical error objects with code, message, details
(dict), and recoverable (bool) fields.
"""

from __future__ import annotations

import json
import tempfile

import pytest

from tests.support.bridge_runner import (
    parse_stdout_json,
    project_root,
    run_bridge_subprocess,
    stdout_text,
    write_temp_json,
)
from tests.support.error_shape import (
    assert_envelope_errors_are_canonical,
    assert_top_level_error_is_canonical,
)

ROOT = project_root()


class TestBridgeMissingSkill:
    def test_missing_skill_returns_canonical_error(self):
        result = run_bridge_subprocess(["--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is False
        assert_top_level_error_is_canonical(data)

    def test_missing_skill_error_has_code_invalid_input(self):
        result = run_bridge_subprocess(["--pretty"])
        data = parse_stdout_json(result)
        assert data["error"]["code"] == "INVALID_INPUT"


class TestBridgeUnknownSkill:
    def test_unknown_skill_returns_canonical_error(self):
        result = run_bridge_subprocess(["--skill", "nonexistent_skill", "--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is False
        assert_top_level_error_is_canonical(data)
        assert data["error"]["code"] == "UNKNOWN_SKILL"


class TestBridgeInvalidJsonInput:
    def test_invalid_json_returns_canonical_error(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        f.write("not json at all")
        f.flush()
        f.close()
        result = run_bridge_subprocess(["--skill", "fund_analysis", "--input", f.name, "--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is False
        assert_top_level_error_is_canonical(data)
        assert data["error"]["code"] == "INVALID_INPUT"

    def test_input_payload_not_object(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        json.dump([1, 2, 3], f)
        f.flush()
        f.close()
        result = run_bridge_subprocess(["--skill", "fund_analysis", "--input", f.name, "--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is False
        assert_top_level_error_is_canonical(data)
        assert data["error"]["code"] == "INVALID_INPUT"


class TestBridgeUnsupportedEmitReport:
    def test_emit_report_markdown_for_decision_support(self):
        inp = str(write_temp_json({"payload": {"evidence_graph": {"items": {}}}}))
        result = run_bridge_subprocess(["--skill", "decision_support", "--input", inp, "--emit-report", "markdown", "--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is False
        assert_top_level_error_is_canonical(data)
        assert data["error"]["code"] == "UNSUPPORTED_EMIT_REPORT"


class TestSkillLevelErrorsCanonical:
    def test_decision_support_active_buy_without_evidence(self):
        inp = str(ROOT / "examples" / "decision_support" / "single_active_buy_without_evidence_invalid.json")
        result = run_bridge_subprocess(["--skill", "decision_support", "--input", inp, "--pretty"])
        data = parse_stdout_json(result)
        assert_envelope_errors_are_canonical(data)

    def test_news_research_without_mcp(self):
        inp = str(write_temp_json({"payload": {"query": "test"}}))
        result = run_bridge_subprocess(["--skill", "news_research", "--input", inp, "--pretty"])
        data = parse_stdout_json(result)
        assert_envelope_errors_are_canonical(data)
        assert_top_level_error_is_canonical(data)

    def test_sentiment_analysis_without_mcp(self):
        inp = str(write_temp_json({"payload": {"query": "test"}}))
        result = run_bridge_subprocess(["--skill", "sentiment_analysis", "--input", inp, "--pretty"])
        data = parse_stdout_json(result)
        assert_envelope_errors_are_canonical(data)
        assert_top_level_error_is_canonical(data)


class TestNoStringErrorsInOutput:
    def test_bridge_errors_are_never_strings(self):
        inp = str(write_temp_json({"payload": {"query": "test"}}))
        result = run_bridge_subprocess(["--skill", "news_research", "--input", inp, "--pretty"])
        data = parse_stdout_json(result)
        for err in data.get("errors", []):
            assert isinstance(err, dict), f"errors[] item is not dict: {err!r}"
            assert not isinstance(err, str), f"errors[] item is a string: {err!r}"
        if "error" in data:
            assert isinstance(data["error"], dict), f"top-level error is not dict: {data['error']!r}"
