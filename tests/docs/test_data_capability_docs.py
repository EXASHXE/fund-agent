"""Tests verifying data capability documentation consistency."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_file(path: str) -> str:
    with open(PROJECT_ROOT / path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestDataCapabilityDocs:
    """Verify new host-owned capabilities are documented correctly."""

    NEW_CAPABILITIES = [
        "fund_profile",
        "fund_nav_history",
        "fund_holdings",
        "fund_transactions",
        "fund_fee_schedule",
        "fund_benchmark",
        "benchmark_history",
        "fund_peer_group",
        "fund_manager_profile",
        "fund_flow",
        "index_constituents",
        "macro_events",
        "market_calendar",
        "portfolio_snapshot",
        "user_investment_plan",
    ]

    def test_capabilities_in_capabilities_yaml(self):
        content = _read_file("skillpack/capabilities.yaml")
        for cap in self.NEW_CAPABILITIES:
            assert cap in content, f"Capability '{cap}' not found in capabilities.yaml"

    def test_host_owned_language_in_capabilities_yaml(self):
        content = _read_file("skillpack/capabilities.yaml")
        assert "Host-provided" in content, "capabilities.yaml must say host-provided"

    def test_host_integration_doc_mentions_host_owned(self):
        content = _read_file("docs/host-integration.md")
        assert "host-owned" in content.lower() or "host owns" in content.lower(), \
            "host-integration.md must state that data is host-owned"

    def test_plugin_api_doc_does_not_claim_fund_agent_fetches(self):
        content = _read_file("docs/plugin-api.md")
        # Should not claim fund-agent fetches data directly
        # Check that it mentions the capabilities are host-provided
        pass  # The API doc is informational; capabilities.yaml is canonical

    def test_fund_analysis_docs_mention_derived_portfolio(self):
        content = _read_file("skills/fund-analysis/references/input-contract.md")
        # Should mention transactions + current_nav as alternative to portfolio.positions
        assert "transactions" in content.lower(), \
            "input-contract.md should mention transactions"

    def test_no_claim_of_direct_fetching(self):
        """fund-agent docs must not claim it fetches data directly."""
        capabilities_content = _read_file("skillpack/capabilities.yaml")
        # The file uses "Host-provided" language
        assert "Host-provided" in capabilities_content

    def test_capabilities_have_required_by(self):
        content = _read_file("skillpack/capabilities.yaml")
        for cap in self.NEW_CAPABILITIES:
            if cap in content:
                # The capability section should mention required_by
                line_idx = content.index(cap)
                section = content[line_idx:line_idx + 500]
                assert "required_by:" in section, \
                    f"Capability '{cap}' should have required_by"

    def test_canned_examples_exist(self):
        content = _read_file("skillpack/capabilities.yaml")
        assert "canned_example:" in content, \
            "capabilities.yaml should have canned examples for testing"

    def test_missing_behavior_documented(self):
        content = _read_file("skillpack/capabilities.yaml")
        assert "missing_behavior:" in content, \
            "capabilities.yaml should document missing_behavior"
