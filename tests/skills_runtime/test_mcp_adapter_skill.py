"""Tests for shared MCP adapter skill base class."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas.skill import SkillInput, SkillOutput
from src.skills_runtime.mcp_adapter_skill import MCPAdapterSkill
from src.tools.adapters.mcp import InMemoryMCPHostAdapter, MCPCapability


def _skill_input(
    payload=None,
    required_mcp=None,
    kg_context=None,
    evidence_context=None,
):
    return SkillInput(
        task_id="test-task",
        step_id="test-step",
        skill_name="test_skill",
        payload=payload or {},
        required_mcp_capabilities=required_mcp or [],
        kg_context=kg_context or {},
        evidence_context=evidence_context or [],
    )


class TestSelectCapability:
    def test_no_adapter_returns_none(self):
        skill = MCPAdapterSkill()
        result = skill.select_capability(["web_search"])
        assert result is None

    def test_preferred_capability_selected(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="financial_news", input_schema={}, output_schema={}),
                MCPCapability(name="web_search", input_schema={}, output_schema={}),
            ],
            handlers={
                "financial_news": lambda p: {"items": []},
                "web_search": lambda p: {"items": []},
            },
        )
        skill = MCPAdapterSkill(mcp_adapter=adapter)
        skill.preferred_capabilities = ("financial_news", "web_search")
        result = skill.select_capability([], preferred=skill.preferred_capabilities)
        assert result == "financial_news"

    def test_fallback_to_secondary(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="web_search", input_schema={}, output_schema={}),
            ],
            handlers={"web_search": lambda p: {"items": []}},
        )
        skill = MCPAdapterSkill(mcp_adapter=adapter)
        skill.preferred_capabilities = ("financial_news", "web_search")
        result = skill.select_capability([], preferred=skill.preferred_capabilities)
        assert result == "web_search"

    def test_no_matching_capability_returns_none(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[
                MCPCapability(name="other", input_schema={}, output_schema={}),
            ],
            handlers={"other": lambda p: {"items": []}},
        )
        skill = MCPAdapterSkill(mcp_adapter=adapter)
        skill.preferred_capabilities = ("financial_news", "web_search")
        result = skill.select_capability([], preferred=skill.preferred_capabilities)
        assert result is None


class TestItemsFromResponse:
    def test_dict_with_items_key(self):
        skill = MCPAdapterSkill()
        result = skill.items_from_response({"items": [{"a": 1}, {"b": 2}]})
        assert len(result) == 2

    def test_dict_with_results_key(self):
        skill = MCPAdapterSkill()
        result = skill.items_from_response({"results": [{"a": 1}]})
        assert len(result) == 1

    def test_custom_keys(self):
        skill = MCPAdapterSkill()
        result = skill.items_from_response(
            {"articles": [{"a": 1}]},
            item_keys=("articles",),
        )
        assert len(result) == 1

    def test_custom_keys_news_sentiments_signals(self):
        skill = MCPAdapterSkill()
        for key in ("articles", "news", "sentiments", "signals"):
            result = skill.items_from_response({key: [{"a": 1}]}, item_keys=(key,))
            assert len(result) == 1, f"key={key}"

    def test_single_object_returns_wrapped_list(self):
        skill = MCPAdapterSkill()
        data = {"title": "single item", "content": "test"}
        result = skill.items_from_response(data)
        assert result == [data]

    def test_non_dict_returns_empty(self):
        skill = MCPAdapterSkill()
        result = skill.items_from_response("not a dict")
        assert result == []

    def test_list_value_preserves_only_dicts(self):
        skill = MCPAdapterSkill()
        result = skill.items_from_response({"items": [{"a": 1}, "string", 42, {"b": 2}]})
        assert result == [{"a": 1}, {"b": 2}]

    def test_empty_dict_returns_empty(self):
        skill = MCPAdapterSkill()
        result = skill.items_from_response({})
        assert result == []

    def test_prefers_items_over_results(self):
        skill = MCPAdapterSkill()
        result = skill.items_from_response({"items": [{"a": 1}], "results": [{"b": 2}]})
        assert len(result) == 1
        assert result[0]["a"] == 1


class TestBuildSoftEvidenceItems:
    def test_builds_evidence_from_valid_items(self):
        adapter = InMemoryMCPHostAdapter(
            capabilities=[MCPCapability(name="web_search", input_schema={}, output_schema={})],
            handlers={"web_search": lambda p: {"items": []}},
        )
        skill = MCPAdapterSkill(mcp_adapter=adapter)
        si = _skill_input()
        items = [{"claim": "test claim", "source_type": "web"}]
        evidence_list, errors = skill.build_soft_evidence_items(items, "web_search", ["fund:001"], si)
        assert len(evidence_list) == 1
        assert evidence_list[0].claim == "test claim"
        assert errors == []

    def test_captures_evidence_build_failed_for_malformed(self):
        skill = MCPAdapterSkill()
        si = _skill_input()
        items = [{"source_type": "", "timestamp": "", "related_entities": []}]
        evidence_list, errors = skill.build_soft_evidence_items(
            items, "web_search", [], si,
        )
        assert any(e.get("code") == "EVIDENCE_BUILD_FAILED" for e in errors)
        assert len(evidence_list) == 0

    def test_empty_items_returns_empty(self):
        skill = MCPAdapterSkill()
        si = _skill_input()
        evidence_list, errors = skill.build_soft_evidence_items([], "web_search", ["fund:001"], si)
        assert evidence_list == []
        assert errors == []


class TestFailedMissingCapability:
    def test_returns_failed_status(self):
        skill = MCPAdapterSkill()
        si = _skill_input()
        result = skill.failed_missing_capability(si, "Missing capability")
        assert result.status == "FAILED"
        assert any(e.get("code") == "MISSING_MCP_CAPABILITY" for e in result.errors)


class TestFailedMcpCall:
    def test_returns_failed_status(self):
        skill = MCPAdapterSkill()
        si = _skill_input()
        response = {"ok": False, "error": {"message": "call failed"}}
        result = skill.failed_mcp_call(si, "web_search", response)
        assert result.status == "FAILED"
        assert any(e.get("code") == "MCP_CALL_FAILED" for e in result.errors)


class TestEmptyResultOutput:
    def test_returns_failed_status(self):
        skill = MCPAdapterSkill()
        si = _skill_input()
        result = skill.empty_result_output(si, "web_search", {}, [])
        assert result.status == "FAILED"
        assert any(e.get("code") == "EMPTY_RESULT" for e in result.errors)


class TestStatusFromEvidence:
    def test_no_evidence_is_failed(self):
        result = MCPAdapterSkill._status_from_evidence([], [])
        assert result == "FAILED"

    def test_evidence_with_errors_is_partial(self):
        from src.schemas.evidence import EvidenceItem
        item = EvidenceItem(
            evidence_id="ev-1",
            evidence_type="SoftEvidence",
            source_type="test",
            timestamp=datetime.now(),
            related_entities=["fund:001"],
            claim="test",
            value={},
        )
        result = MCPAdapterSkill._status_from_evidence([item], [{"code": "ERR"}])
        assert result == "PARTIAL"

    def test_evidence_no_errors_is_ok(self):
        from src.schemas.evidence import EvidenceItem
        item = EvidenceItem(
            evidence_id="ev-1",
            evidence_type="SoftEvidence",
            source_type="test",
            timestamp=datetime.now(),
            related_entities=["fund:001"],
            claim="test",
            value={},
        )
        result = MCPAdapterSkill._status_from_evidence([item], [])
        assert result == "OK"
