"""Tests for docs/tools-inventory.md consistency."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "docs" / "tools-inventory.md"


@pytest.mark.skipif(not INVENTORY_PATH.exists(), reason="tools-inventory.md not yet created")
class TestToolsInventoryDocs:
    def test_inventory_exists(self):
        assert INVENTORY_PATH.exists()

    def test_mentions_tools_yaml(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "tools.yaml" in text

    def test_mentions_manifest(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "fund-agent.skillpack.yaml" in text

    def test_mentions_public_registered_tools(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "public registered tool" in text.lower()

    def test_mentions_internal_deterministic_helpers(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "internal" in text.lower()

    def test_mentions_mcp_adapter_boundary(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "MCP" in text or "mcp" in text

    def test_states_provider_boundary(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "host" in text.lower() or "provider" in text.lower()

    def test_mentions_all_src_tools_subdirectories(self):
        tools_dir = ROOT / "src" / "tools"
        subdirs = sorted(
            d.name
            for d in tools_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        for subdir in subdirs:
            assert subdir in text, f"src/tools/{subdir}/ not mentioned in tools-inventory.md"

    def test_does_not_claim_fund_agent_fetches_data(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "fetches provider data" not in text.lower()
        assert "does not fetch" in text.lower() or "does not" in text.lower()
