"""Tools inventory documentation tests.

Verifies that docs/tools-inventory.md covers the required policy areas
and references the correct registry files.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "docs" / "tools-inventory.md"
TOOLS_YAML_PATH = ROOT / "skillpack" / "tools.yaml"
MANIFEST_PATH = ROOT / "skillpack" / "fund-agent.skillpack.yaml"


class TestToolsInventoryDoc:
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
        assert "public registered tool" in text

    def test_mentions_internal_deterministic_helpers(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "internal deterministic helper" in text

    def test_mentions_mcp_adapter_boundary(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "MCP adapter boundary" in text or "mcp.py" in text

    def test_states_provider_sdks_belong_to_host(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "external host" in text or "MCP provider" in text

    def test_mentions_all_src_tools_subdirectories(self):
        tools_dir = ROOT / "src" / "tools"
        subdirs = sorted(
            d.name
            for d in tools_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        for subdir in subdirs:
            assert subdir in text, f"src/tools/{subdir}/ not mentioned in docs/tools-inventory.md"

    def test_does_not_claim_fund_agent_fetches_provider_data(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "does not fetch provider data" in text or "does not fetch" in text

    def test_has_classification_legend(self):
        text = INVENTORY_PATH.read_text(encoding="utf-8")
        assert "Classification Legend" in text or "classification" in text.lower()
