"""Tools registry consistency tests.

Verifies that skillpack/tools.yaml, the skillpack manifest, and src/tools
implementations stay consistent. Every public registered tool must appear in
both tools.yaml and the manifest. Internal deterministic helpers are
explicitly allowlisted.
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
    "input_schema",
    "output_schema",
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

INTERNAL_TOOL_IDS = frozenset({
})


def _load_tools_yaml():
    raw = yaml.safe_load(TOOLS_YAML_PATH.read_text(encoding="utf-8"))
    return raw.get("tools", [])


def _load_manifest():
    raw = yaml.safe_load(MANIFEST_YAML_PATH.read_text(encoding="utf-8"))
    return raw


def _manifest_import_paths():
    manifest = _load_manifest()
    return list(manifest.get("tools", []))


def _tools_yaml_ids():
    tools = _load_tools_yaml()
    return {t["id"] for t in tools}


def _import_path_to_id(ip: str) -> str:
    if ":" in ip:
        return ip.split(":", 1)[1]
    return ip


def _resolve_import_path(ip: str):
    if ":" not in ip:
        return None
    module_name, attr_name = ip.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        value = module
        for part in attr_name.split("."):
            value = getattr(value, part)
        return value
    except (ImportError, AttributeError):
        return None


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
        duplicates = [x for x in ids if ids.count(x) > 1]
        assert len(ids) == len(set(ids)), f"Duplicate tool ids: {sorted(set(duplicates))}"

    def test_import_paths_are_unique(self):
        tools = _load_tools_yaml()
        paths = [t.get("import_path", "") for t in tools]
        assert len(paths) == len(set(paths)), f"Duplicate import_paths: {[x for x in paths if paths.count(x) > 1]}"

    def test_import_path_format(self):
        tools = _load_tools_yaml()
        for tool in tools:
            ip = tool.get("import_path", "")
            assert ":" in ip, f"Tool '{tool.get('id')}' import_path '{ip}' missing ':' separator"

    def test_all_tools_yaml_import_paths_resolve(self):
        tools = _load_tools_yaml()
        for tool in tools:
            ip = tool.get("import_path", "")
            if tool.get("category") == "adapter_contract":
                continue
            resolved = _resolve_import_path(ip)
            assert resolved is not None, (
                f"Tool '{tool['id']}' import_path '{ip}' does not resolve to an importable callable"
            )
            assert callable(resolved), (
                f"Tool '{tool['id']}' import_path '{ip}' resolves but is not callable"
            )


class TestManifestToolsStructure:
    def test_manifest_tools_parse(self):
        manifest = _load_manifest()
        tools = manifest.get("tools", [])
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_manifest_tool_import_paths_are_unique(self):
        paths = _manifest_import_paths()
        assert len(paths) == len(set(paths)), f"Duplicate manifest tool import paths"

    def test_all_manifest_import_paths_resolve(self):
        for ip in _manifest_import_paths():
            if ip == "src.tools.adapters.mcp:MCPHostAdapter":
                continue
            resolved = _resolve_import_path(ip)
            assert resolved is not None, (
                f"Manifest tool import_path '{ip}' does not resolve to an importable callable"
            )
            assert callable(resolved), (
                f"Manifest tool import_path '{ip}' resolves but is not callable"
            )


class TestToolsYamlManifestConsistency:
    def test_manifest_tools_in_tools_yaml(self):
        tools_yaml_ids = _tools_yaml_ids()
        for ip in _manifest_import_paths():
            tool_id = _import_path_to_id(ip)
            if tool_id in INTERNAL_TOOL_IDS:
                continue
            assert tool_id in tools_yaml_ids, (
                f"Manifest tool '{ip}' (id='{tool_id}') not found in tools.yaml. "
                f"If it is internal, add it to INTERNAL_TOOL_IDS in this test file."
            )

    def test_tools_yaml_public_tools_in_manifest(self):
        manifest_paths = set(_manifest_import_paths())
        tools = _load_tools_yaml()
        for tool in tools:
            if tool.get("category") == "adapter_contract":
                continue
            if tool["id"] in INTERNAL_TOOL_IDS:
                continue
            ip = tool.get("import_path", "")
            assert ip in manifest_paths, (
                f"tools.yaml tool '{tool['id']}' (import_path='{ip}') not in manifest tools list. "
                f"If it is internal/experimental, add its id to INTERNAL_TOOL_IDS in this test file."
            )


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
                    mod_file = mod.__file__
                    if mod_file is None:
                        continue
                    source = Path(mod_file).read_text(encoding="utf-8")
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
                    mod_file = mod.__file__
                    if mod_file is None:
                        continue
                    source = Path(mod_file).read_text(encoding="utf-8")
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
        assert inventory_path.exists(), "docs/tools-inventory.md must exist"
        inventory_text = inventory_path.read_text(encoding="utf-8")
        for subdir in subdirs:
            assert f"`src/tools/{subdir}/`" in inventory_text or f"src/tools/{subdir}" in inventory_text, (
                f"src/tools/{subdir}/ not mentioned in docs/tools-inventory.md"
            )
