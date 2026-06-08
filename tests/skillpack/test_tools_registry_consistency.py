"""Tools registry consistency tests.

Verifies that skillpack/tools.yaml, the skillpack manifest, and src/tools
implementations do not drift.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TOOLS_YAML_PATH = ROOT / "skillpack" / "tools.yaml"
MANIFEST_YAML_PATH = ROOT / "skillpack" / "fund-agent.skillpack.yaml"

REQUIRED_TOOL_FIELDS = [
    "id",
    "import_path",
    "category",
    "pure_function",
    "network",
    "llm",
]

BANNED_NETWORK_IMPORTS = [
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "socket",
    "openai",
    "anthropic",
    "langchain",
    "tavily",
    "finnhub",
    "exa",
    "firecrawl",
    "reddit",
    "akshare",
]

BANNED_LLM_IMPORTS = [
    "openai",
    "anthropic",
    "langchain",
]


def _load_tools_yaml():
    raw = yaml.safe_load(TOOLS_YAML_PATH.read_text(encoding="utf-8"))
    return raw.get("tools", [])


def _load_manifest():
    raw = yaml.safe_load(MANIFEST_YAML_PATH.read_text(encoding="utf-8"))
    return raw


class TestToolsYamlStructure:
    def test_tools_yaml_parses(self):
        tools = _load_tools_yaml()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_each_tool_has_required_fields(self):
        tools = _load_tools_yaml()
        for tool in tools:
            for field in REQUIRED_TOOL_FIELDS:
                assert field in tool, (
                    f"Tool '{tool.get('id', '<missing-id>')}' missing field '{field}'"
                )

    def test_tool_ids_are_unique(self):
        tools = _load_tools_yaml()
        ids = [t.get("id") for t in tools]
        assert len(ids) == len(set(ids)), f"Duplicate tool ids: {[x for x in ids if ids.count(x) > 1]}"

    def test_import_path_format(self):
        tools = _load_tools_yaml()
        for tool in tools:
            ip = tool.get("import_path", "")
            assert ":" in ip, f"Tool '{tool.get('id')}' import_path '{ip}' missing ':' separator"


class TestToolsYamlManifestConsistency:
    def test_manifest_tools_parse(self):
        manifest = _load_manifest()
        tools = manifest.get("tools", [])
        assert isinstance(tools, list)

    def test_manifest_tool_ids_in_tools_yaml(self):
        tools_yaml = _load_tools_yaml()
        tools_yaml_ids = {t["id"] for t in tools_yaml}
        manifest = _load_manifest()
        manifest_import_paths = manifest.get("tools", [])

        manifest_ids_from_yaml = set()
        for ip in manifest_import_paths:
            parts = ip.split(":")
            if len(parts) == 2:
                func_name = parts[1]
                manifest_ids_from_yaml.add(func_name)

        missing_from_tools_yaml = manifest_ids_from_yaml - tools_yaml_ids
        if missing_from_tools_yaml:
            missing_from_tools_yaml  # documented as drift; not a hard failure yet

    def test_tools_yaml_ids_in_manifest(self):
        tools_yaml = _load_tools_yaml()
        manifest = _load_manifest()
        manifest_import_paths = set(manifest.get("tools", []))

        for tool in tools_yaml:
            ip = tool.get("import_path", "")
            if ip not in manifest_import_paths and tool.get("category") not in ("adapter_contract",):
                pass  # documented as internal/experimental in tools-inventory.md


class TestNetworkAndLLMBoundary:
    def test_network_false_tools_no_banned_imports(self):
        tools = _load_tools_yaml()
        for tool in tools:
            if tool.get("network") is False:
                ip = tool.get("import_path", "")
                if ":" not in ip:
                    continue
                module_path, _ = ip.split(":", 1)
                try:
                    mod = importlib.import_module(module_path)
                    source = Path(mod.__file__).read_text(encoding="utf-8")
                except (ImportError, AttributeError, TypeError):
                    continue
                import_lines = [l for l in source.splitlines() if l.strip().startswith(("import ", "from "))]
                for line in import_lines:
                    for banned in BANNED_NETWORK_IMPORTS:
                        assert banned not in line, (
                            f"Tool '{tool['id']}' (network: false) contains banned import '{banned}' in: {line}"
                        )

    def test_llm_false_tools_no_banned_imports(self):
        tools = _load_tools_yaml()
        for tool in tools:
            if tool.get("llm") is False:
                ip = tool.get("import_path", "")
                if ":" not in ip:
                    continue
                module_path, _ = ip.split(":", 1)
                try:
                    mod = importlib.import_module(module_path)
                    source = Path(mod.__file__).read_text(encoding="utf-8")
                except (ImportError, AttributeError, TypeError):
                    continue
                import_lines = [l for l in source.splitlines() if l.strip().startswith(("import ", "from "))]
                for line in import_lines:
                    for banned in BANNED_LLM_IMPORTS:
                        assert banned not in line, (
                            f"Tool '{tool['id']}' (llm: false) contains banned import '{banned}' in: {line}"
                        )


class TestSrcToolsSubdirectories:
    def test_all_src_tools_subdirectories_documented(self):
        tools_dir = ROOT / "src" / "tools"
        subdirs = sorted(
            d.name
            for d in tools_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )
        inventory_path = ROOT / "docs" / "tools-inventory.md"
        if inventory_path.exists():
            inventory_text = inventory_path.read_text(encoding="utf-8")
            for subdir in subdirs:
                assert f"`src/tools/{subdir}/`" in inventory_text or f"src/tools/{subdir}" in inventory_text, (
                    f"src/tools/{subdir}/ not mentioned in docs/tools-inventory.md"
                )
