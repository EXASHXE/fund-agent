"""Tests for runtime bridge capability discovery (--list-capabilities, --describe-capability)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_metadata, run_bridge_subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _list_capabilities() -> dict:
    return run_bridge_inprocess_metadata(list_capabilities=True, pretty=True)


def _describe_capability(name: str) -> dict:
    return run_bridge_inprocess_metadata(describe_capability=name, pretty=True)


class TestListCapabilities:
    def test_lists_capabilities(self):
        output = _list_capabilities()
        assert output["ok"] is True
        assert "capabilities" in output
        assert len(output["capabilities"]) > 0

    def test_includes_15_host_owned_capabilities(self):
        output = _list_capabilities()
        caps = {c["name"] for c in output["capabilities"]}
        expected = {
            "fund_profile", "fund_nav_history", "fund_holdings",
            "fund_transactions", "fund_fee_schedule", "fund_benchmark",
            "benchmark_history", "fund_peer_group", "fund_manager_profile",
            "fund_flow", "index_constituents", "macro_events",
            "market_calendar", "portfolio_snapshot", "user_investment_plan",
        }
        for name in expected:
            assert name in caps, f"Missing capability: {name}"

    def test_includes_mcp_capabilities(self):
        output = _list_capabilities()
        caps = {c["name"] for c in output["capabilities"]}
        for name in ("web_search", "financial_news", "social_sentiment"):
            assert name in caps

    def test_includes_local_capabilities(self):
        output = _list_capabilities()
        caps = {c["name"] for c in output["capabilities"]}
        for name in ("evidence_compile", "evidence_review", "decision_support"):
            assert name in caps

    def test_all_host_owned_are_marked_host(self):
        output = _list_capabilities()
        host_caps = [c for c in output["capabilities"] if c["category"] in ("mcp_capability", "host_data_capability")]
        for c in host_caps:
            assert c["owner"] == "host", f"{c['name']} should be host-owned"

    def test_local_capabilities_marked_fund_agent(self):
        output = _list_capabilities()
        local = [c for c in output["capabilities"] if c["category"] == "local_capability"]
        for c in local:
            assert c["owner"] == "fund-agent", f"{c['name']} should be fund-agent-owned"

    @pytest.mark.subprocess
    def test_stdout_is_json_only(self):
        proc = run_bridge_subprocess(["--list-capabilities"])
        json.loads(proc.stdout)


class TestDescribeCapability:
    def test_describes_fund_nav_history(self):
        output = _describe_capability("fund_nav_history")
        assert output["ok"] is True
        assert output["capability"]["name"] == "fund_nav_history"
        assert output["capability"]["owner"] == "host"
        assert "purpose" in output["capability"]
        assert "required_by" in output["capability"]
        assert output["capability"]["required_by"] == ["fund_analysis"]

    def test_unknown_capability_fails(self):
        output = _describe_capability("nonexistent_cap")
        assert output["ok"] is False
        assert output["error"]["code"] == "UNKNOWN_CAPABILITY"
        assert "valid_capabilities" in output["error"]["details"]

    def test_describes_mcp_capability(self):
        output = _describe_capability("web_search")
        assert output["ok"] is True
        assert output["capability"]["name"] == "web_search"
        assert output["capability"]["category"] == "mcp_capability"

    def test_describes_local_capability(self):
        output = _describe_capability("evidence_compile")
        assert output["ok"] is True
        assert output["capability"]["name"] == "evidence_compile"
        assert output["capability"]["owner"] == "fund-agent"

    @pytest.mark.subprocess
    def test_json_stdout_only(self):
        proc = run_bridge_subprocess(["--describe-capability", "fund_nav_history"])
        json.loads(proc.stdout)


class TestCapabilityListSkillsIndependence:
    def test_list_skills_still_works(self):
        output = run_bridge_inprocess_metadata(list_skills=True, pretty=True)
        assert output["ok"] is True
        assert "skills" in output
        assert len(output["skills"]) >= 5

    def test_list_capabilities_is_separate(self):
        caps_output = _list_capabilities()
        skills_output = run_bridge_inprocess_metadata(list_skills=True, pretty=True)
        assert "skills" in skills_output
        assert "capabilities" in caps_output
        assert "skills" not in caps_output
