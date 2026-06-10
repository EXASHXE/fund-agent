"""Runtime bridge error shape tests — subprocess-level end-to-end.

Verifies that runtime bridge error envelopes produced by real CLI
invocations use canonical error objects with code, message, details
(dict), and recoverable (bool) fields.

CLI boundary tests use subprocess. Skill-level error shape tests
use in-process bridge for speed.
"""

from __future__ import annotations

import json
import tempfile

import pytest

from tests.support.bridge_runner import (
    parse_stdout_json,
    project_root,
    run_bridge_inprocess_json,
    run_bridge_subprocess,
    write_temp_json,
)
from tests.support.error_shape import (
    assert_envelope_errors_are_canonical,
    assert_top_level_error_is_canonical,
)

ROOT = project_root()


class TestBridgeMissingSkill:
    @pytest.mark.subprocess
    def test_missing_skill_returns_canonical_error(self):
        result = run_bridge_subprocess(["--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is False
        assert_top_level_error_is_canonical(data)

    @pytest.mark.subprocess
    def test_missing_skill_error_has_code_invalid_input(self):
        result = run_bridge_subprocess(["--pretty"])
        data = parse_stdout_json(result)
        assert data["error"]["code"] == "INVALID_INPUT"


class TestBridgeUnknownSkill:
    @pytest.mark.subprocess
    def test_unknown_skill_returns_canonical_error(self):
        result = run_bridge_subprocess(["--skill", "nonexistent_skill", "--pretty"])
        data = parse_stdout_json(result)
        assert data.get("ok") is False
        assert_top_level_error_is_canonical(data)
        assert data["error"]["code"] == "UNKNOWN_SKILL"


class TestBridgeInvalidJsonInput:
    @pytest.mark.subprocess
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

    @pytest.mark.subprocess
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
        result = run_bridge_inprocess_json(
            skill="decision_support",
            input_data={"payload": {"evidence_graph": {"items": {}}}},
            emit_report="markdown",
        )
        assert result.get("ok") is False
        assert_top_level_error_is_canonical(result)


class TestSkillLevelErrorsCanonical:
    def test_decision_support_active_buy_without_evidence(self):
        inp = str(ROOT / "examples" / "decision_support" / "single_active_buy_without_evidence_invalid.json")
        fixture = json.loads(open(inp, encoding="utf-8").read())
        result = run_bridge_inprocess_json(
            skill="decision_support",
            input_data=fixture,
        )
        assert_envelope_errors_are_canonical(result)

    def test_news_research_without_mcp(self):
        result = run_bridge_inprocess_json(
            skill="news_research",
            input_data={"payload": {"query": "test"}},
        )
        assert_envelope_errors_are_canonical(result)
        assert_top_level_error_is_canonical(result)

    def test_sentiment_analysis_without_mcp(self):
        result = run_bridge_inprocess_json(
            skill="sentiment_analysis",
            input_data={"payload": {"query": "test"}},
        )
        assert_envelope_errors_are_canonical(result)
        assert_top_level_error_is_canonical(result)


class TestNoStringErrorsInOutput:
    def test_bridge_errors_are_never_strings(self):
        result = run_bridge_inprocess_json(
            skill="news_research",
            input_data={"payload": {"query": "test"}},
        )
        for err in result.get("errors", []):
            assert isinstance(err, dict), f"errors[] item is not dict: {err!r}"
            assert not isinstance(err, str), f"errors[] item is a string: {err!r}"
        if "error" in result:
            assert isinstance(result["error"], dict), f"top-level error is not dict: {result['error']!r}"
