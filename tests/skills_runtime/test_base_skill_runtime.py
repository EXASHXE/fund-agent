"""Tests for BaseSkillRuntime shared helpers."""

from __future__ import annotations

import pytest

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.base import BaseSkillRuntime


_BASE = BaseSkillRuntime()


def _skill_input(**overrides):
    defaults = {
        "task_id": "t-1",
        "step_id": "s-1",
        "skill_name": "test_skill",
        "payload": {},
        "required_mcp_capabilities": [],
        "kg_context": {},
        "evidence_context": [],
    }
    defaults.update(overrides)
    return SkillInput(**defaults)


class TestMakeSkillError:
    def test_returns_dict_with_code_message_details_recoverable(self):
        err = _BASE.make_skill_error("ERR_TEST", "test message", {"x": 1}, recoverable=False)
        assert isinstance(err, dict)
        assert err["code"] == "ERR_TEST"
        assert err["message"] == "test message"
        assert err["details"] == {"x": 1}
        assert err["recoverable"] is False

    def test_defaults(self):
        err = _BASE.make_skill_error("ERR_X", "msg")
        assert err["details"] == {}
        assert err["recoverable"] is True


class TestFailedOutput:
    def test_returns_failed_status(self):
        si = _skill_input()
        out = _BASE.failed_output(si, "ERR_A", "bad thing")
        assert isinstance(out, SkillOutput)
        assert out.status == "FAILED"
        assert out.step_id == si.step_id
        assert out.skill_name == si.skill_name
        assert "bad thing" in out.warnings
        assert any(e["code"] == "ERR_A" for e in out.errors)


class TestOkOutput:
    def test_preserves_artifacts_evidence_errors_capabilities(self):
        si = _skill_input()
        out = _BASE.ok_output(
            si,
            artifacts={"x": 1},
            evidence_items=[{"e": 1}],
            warnings=["w"],
            errors=[{"code": "E"}],
            used_mcp_capabilities=["web_search"],
        )
        assert out.status == "OK"
        assert out.artifacts == {"x": 1}
        assert out.evidence_items == [{"e": 1}]
        assert out.warnings == ["w"]
        assert out.errors == [{"code": "E"}]
        assert out.used_mcp_capabilities == ["web_search"]

    def test_defaults_to_empty(self):
        si = _skill_input()
        out = _BASE.ok_output(si)
        assert out.status == "OK"
        assert out.artifacts == {}
        assert out.evidence_items == []
        assert out.warnings == []
        assert out.errors == []
        assert out.used_mcp_capabilities == []


class TestPartialOutput:
    def test_returns_partial_status(self):
        si = _skill_input()
        out = _BASE.partial_output(
            si,
            artifacts={"k": "v"},
            evidence_items=[{"e": 1}],
            warnings=["partial result"],
            used_mcp_capabilities=["social_sentiment"],
        )
        assert out.status == "PARTIAL"
        assert out.artifacts == {"k": "v"}
        assert out.evidence_items == [{"e": 1}]
        assert out.warnings == ["partial result"]
        assert out.used_mcp_capabilities == ["social_sentiment"]


class TestNormalizeEntities:
    def test_uses_payload_related_entities(self):
        si = _skill_input(payload={"related_entities": ["fund:ABC", "fund:DEF"]})
        result = _BASE.normalize_entities_from_input(si)
        assert result == ["fund:ABC", "fund:DEF"]

    def test_falls_back_to_kg_context_fund_codes_with_prefix(self):
        si = _skill_input(kg_context={"fund_codes": ["001", "002"]})
        result = _BASE.normalize_entities_from_input(si)
        assert result == ["fund:001", "fund:002"]

    def test_kg_context_fund_codes_already_prefixed(self):
        si = _skill_input(kg_context={"fund_codes": ["fund:ABC"]})
        result = _BASE.normalize_entities_from_input(si)
        assert result == ["fund:ABC"]

    def test_falls_back_to_research_task(self):
        si = _skill_input()
        result = _BASE.normalize_entities_from_input(si)
        assert result == ["research_task"]

    def test_empty_payload_related_entities_falls_back(self):
        si = _skill_input(payload={"related_entities": []})
        result = _BASE.normalize_entities_from_input(si)
        assert result == ["research_task"]


class TestUniqueStrings:
    def test_preserves_order_removes_duplicates(self):
        result = BaseSkillRuntime._unique_strings(["a", "b", "a", "c", "b", "d"])
        assert result == ["a", "b", "c", "d"]

    def test_empty_list(self):
        assert BaseSkillRuntime._unique_strings([]) == []
