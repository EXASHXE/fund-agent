"""Tests for runtime bridge capability discovery (--list-capabilities, --describe-capability)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_SKILL = str(PROJECT_ROOT / "scripts" / "run_skill.py")


def _run(args: list[str]) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        [sys.executable, RUN_SKILL] + args,
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
    )
    return json.loads(result.stdout)


class TestListCapabilities:
    def test_lists_capabilities(self):
        output = _run(["--list-capabilities", "--pretty"])
        assert output["ok"] is True
        assert "capabilities" in output
        assert len(output["capabilities"]) > 0

    def test_includes_15_host_owned_capabilities(self):
        output = _run(["--list-capabilities", "--pretty"])
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
        output = _run(["--list-capabilities", "--pretty"])
        caps = {c["name"] for c in output["capabilities"]}
        for name in ("web_search", "financial_news", "social_sentiment"):
            assert name in caps

    def test_includes_local_capabilities(self):
        output = _run(["--list-capabilities", "--pretty"])
        caps = {c["name"] for c in output["capabilities"]}
        for name in ("evidence_compile", "evidence_review", "decision_support"):
            assert name in caps

    def test_all_host_owned_are_marked_host(self):
        output = _run(["--list-capabilities", "--pretty"])
        host_caps = [c for c in output["capabilities"] if c["category"] in ("mcp_capability", "host_data_capability")]
        for c in host_caps:
            assert c["owner"] == "host", f"{c['name']} should be host-owned"

    def test_local_capabilities_marked_fund_agent(self):
        output = _run(["--list-capabilities", "--pretty"])
        local = [c for c in output["capabilities"] if c["category"] == "local_capability"]
        for c in local:
            assert c["owner"] == "fund-agent", f"{c['name']} should be fund-agent-owned"

    def test_stdout_is_json_only(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        result = subprocess.run(
            [sys.executable, RUN_SKILL, "--list-capabilities"],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
        )
        # stdout should be valid JSON
        json.loads(result.stdout)


class TestDescribeCapability:
    def test_describes_fund_nav_history(self):
        output = _run(["--describe-capability", "fund_nav_history", "--pretty"])
        assert output["ok"] is True
        assert output["capability"]["name"] == "fund_nav_history"
        assert output["capability"]["owner"] == "host"
        assert "purpose" in output["capability"]
        assert "required_by" in output["capability"]
        assert output["capability"]["required_by"] == ["fund_analysis"]

    def test_unknown_capability_fails(self):
        output = _run(["--describe-capability", "nonexistent_cap", "--pretty"])
        assert output["ok"] is False
        assert output["error"]["code"] == "UNKNOWN_CAPABILITY"
        assert "valid_capabilities" in output["error"]["details"]

    def test_describes_mcp_capability(self):
        output = _run(["--describe-capability", "web_search", "--pretty"])
        assert output["ok"] is True
        assert output["capability"]["name"] == "web_search"
        assert output["capability"]["category"] == "mcp_capability"

    def test_describes_local_capability(self):
        output = _run(["--describe-capability", "evidence_compile", "--pretty"])
        assert output["ok"] is True
        assert output["capability"]["name"] == "evidence_compile"
        assert output["capability"]["owner"] == "fund-agent"

    def test_json_stdout_only(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        result = subprocess.run(
            [sys.executable, RUN_SKILL, "--describe-capability", "fund_nav_history"],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
        )
        json.loads(result.stdout)


class TestCapabilityListSkillsIndependence:
    def test_list_skills_still_works(self):
        output = _run(["--list-skills", "--pretty"])
        assert output["ok"] is True
        assert "skills" in output
        assert len(output["skills"]) >= 5

    def test_list_capabilities_is_separate(self):
        caps_output = _run(["--list-capabilities", "--pretty"])
        skills_output = _run(["--list-skills", "--pretty"])
        assert "skills" in skills_output
        assert "capabilities" in caps_output
        assert "skills" not in caps_output
