"""Tests for workflow trace — v1.6.2."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.skills_runtime.workflow.workflow_trace import WorkflowTrace


class TestWorkflowTraceBasic:
    def test_empty_trace(self):
        trace = WorkflowTrace(scenario_id="test")
        assert trace.event_count == 0
        assert trace.last_event_type() is None

    def test_add_event_increments_sequence(self):
        trace = WorkflowTrace(scenario_id="test")
        trace.add_event("input_loaded", "Loaded fixture")
        trace.add_event("intent_classified", "Classified")
        assert trace.event_count == 2
        d = trace.to_dict()
        assert d["events"][0]["sequence"] == 1
        assert d["events"][1]["sequence"] == 2

    def test_sequence_starts_at_one(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg")
        assert trace.to_dict()["events"][0]["sequence"] == 1

    def test_event_has_required_fields(self):
        trace = WorkflowTrace(scenario_id="s1")
        trace.add_event("input_loaded", "Loaded", {"fixture": "test"})
        event = trace.to_dict()["events"][0]
        assert "sequence" in event
        assert "type" in event
        assert "message" in event
        assert "details" in event

    def test_details_omitted_when_none(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg")
        event = trace.to_dict()["events"][0]
        assert "details" not in event

    def test_last_event_type(self):
        trace = WorkflowTrace()
        trace.add_event("first", "a")
        trace.add_event("second", "b")
        assert trace.last_event_type() == "second"


class TestWorkflowTraceDict:
    def test_to_dict_has_scenario_id(self):
        trace = WorkflowTrace(scenario_id="my_scenario")
        trace.add_event("test", "msg")
        d = trace.to_dict()
        assert d["scenario_id"] == "my_scenario"
        assert d["event_count"] == 1
        assert len(d["events"]) == 1


class TestWorkflowTraceJsonl:
    def test_to_jsonl_one_line_per_event(self):
        trace = WorkflowTrace()
        trace.add_event("a", "first")
        trace.add_event("b", "second")
        jsonl = trace.to_jsonl()
        lines = jsonl.strip().split("\n")
        assert len(lines) == 2

    def test_to_jsonl_valid_json(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg", {"key": "value"})
        jsonl = trace.to_jsonl()
        parsed = json.loads(jsonl)
        assert parsed["type"] == "test"
        assert parsed["details"]["key"] == "value"


class TestWorkflowTraceSecretRedaction:
    def test_api_key_redacted(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg", {"api_key": "secret123"})
        d = trace.to_dict()
        assert d["events"][0]["details"]["api_key"] == "<redacted>"

    def test_token_redacted(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg", {"token": "abc"})
        assert trace.to_dict()["events"][0]["details"]["token"] == "<redacted>"

    def test_cookie_redacted(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg", {"cookie": "xyz"})
        assert trace.to_dict()["events"][0]["details"]["cookie"] == "<redacted>"

    def test_nested_secret_redacted(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg", {"config": {"api_key": "secret"}})
        d = trace.to_dict()
        assert d["events"][0]["details"]["config"]["api_key"] == "<redacted>"

    def test_non_secret_preserved(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg", {"provider": "akshare", "count": 5})
        d = trace.to_dict()
        assert d["events"][0]["details"]["provider"] == "akshare"
        assert d["events"][0]["details"]["count"] == 5


class TestWorkflowTraceDeterminism:
    def test_no_timestamps(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg")
        d = trace.to_dict()
        assert "timestamp" not in d["events"][0]

    def test_events_list_is_copy(self):
        trace = WorkflowTrace()
        trace.add_event("test", "msg")
        events = trace.events
        events.append({"fake": True})
        assert trace.event_count == 1
