"""Tool catalog tests for external host discovery."""

from __future__ import annotations

import importlib
from pathlib import Path

import yaml

CATALOG = Path("skillpack/tools.yaml")


def test_tool_catalog_exists():
    assert CATALOG.exists()


def test_tool_catalog_entries_have_import_paths():
    for entry in _tools():
        for key in (
            "id",
            "import_path",
            "category",
            "pure_function",
            "network",
            "llm",
            "input_schema",
            "output_schema",
            "produces",
            "notes",
        ):
            assert key in entry, f"{entry.get('id')} missing {key}"


def test_tool_catalog_import_paths_resolve():
    for entry in _tools():
        assert _resolve(entry["import_path"]) is not None


def test_pure_tools_declare_network_false():
    for entry in _tools():
        if entry["pure_function"]:
            assert entry["network"] is False


def test_pure_tools_declare_llm_false():
    for entry in _tools():
        if entry["pure_function"]:
            assert entry["llm"] is False


def test_tool_catalog_does_not_reference_legacy():
    serialized = CATALOG.read_text()

    assert "legacy" not in serialized


def _tools() -> list[dict]:
    data = yaml.safe_load(CATALOG.read_text())
    return data["tools"]


def _resolve(import_path: str):
    module_name, attr_name = import_path.split(":", 1)
    module = importlib.import_module(module_name)
    value = module
    for part in attr_name.split("."):
        value = getattr(value, part)
    return value
