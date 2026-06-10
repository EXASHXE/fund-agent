"""Shared architecture test helpers and session-scoped fixtures.

Provides cached import extraction and file content reading to avoid
redundant directory walks and AST parses across architecture tests.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

DEPRECATED_SRC_PATHS = {
    "src/core": "Deprecated ResearchOS modules removed in v0.4.9-dev hardening.",
    "src/infra": "Deprecated infrastructure shims removed in v0.4.9-dev hardening.",
    "src/workflows": "Deprecated workflow wrappers removed in v0.4.9-dev hardening.",
    "src/config": "Deprecated shim (re-exported src.infra.config) removed.",
    "src/data": "Deprecated shim (re-exported src.infra.data) removed.",
    "src/db": "Deprecated shim (re-exported src.infra.persistence) removed.",
    "src/kg": "Deprecated shim (re-exported src.graph) removed.",
    "src/vectorstore": "Deprecated shim (re-exported src.infra.vectorstore) removed.",
}

DEPRECATED_SRC_MODULES = {
    "src.core", "src.infra", "src.workflows",
    "src.config", "src.data", "src.db",
    "src.kg", "src.vectorstore",
}

PROVIDER_SDKS = {
    "tavily", "exa", "firecrawl", "finnhub", "reddit",
    "akshare", "openai", "anthropic", "langchain",
}

NETWORK_CLIENTS = {
    "requests", "httpx", "aiohttp", "urllib3", "socket",
}

BROKER_KEYWORDS = {
    "place_order", "submit_order", "broker_client", "brokerage",
    "trade_execution_api",
}

PLUGIN_CORE_DIRS = ("skills_runtime", "skillpack", "tools", "schemas", "graph")


def imports_from_dir(dirpath: Path) -> set[str]:
    """Extract all imports from Python files in a directory (skips __pycache__, DEPRECATED)."""
    imports: set[str] = set()
    if not dirpath.is_dir():
        return imports
    for path in sorted(dirpath.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if "# DEPRECATED" in text:
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    return imports


def imports_from_file(path: Path) -> set[str]:
    """Extract all imports from a single Python file."""
    imports: set[str] = set()
    if not path.is_file():
        return imports
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return imports
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


@lru_cache(maxsize=64)
def cached_file_read(relpath: str) -> str:
    """Read a project file by relative path, cached."""
    return (ROOT / relpath).read_text(encoding="utf-8")


@lru_cache(maxsize=32)
def cached_dir_imports(relpath: str) -> frozenset[str]:
    """Extract imports from a directory by relative path, cached."""
    return frozenset(imports_from_dir(ROOT / relpath))


@pytest.fixture(scope="session")
def plugin_imports() -> dict[str, frozenset[str]]:
    """Session-scoped: import sets for each plugin core directory."""
    return {d: cached_dir_imports(f"src/{d}") for d in PLUGIN_CORE_DIRS}


@pytest.fixture(scope="session")
def all_plugin_imports(plugin_imports: dict[str, frozenset[str]]) -> frozenset[str]:
    """Session-scoped: union of all plugin core imports."""
    result: set[str] = set()
    for imp_set in plugin_imports.values():
        result.update(imp_set)
    return frozenset(result)


@pytest.fixture(scope="session")
def src_top_level_entries() -> frozenset[str]:
    """Session-scoped: top-level entries in src/."""
    if not SRC.is_dir():
        return frozenset()
    return frozenset(p.name for p in SRC.iterdir())


@pytest.fixture(scope="session")
def runtime_source_texts() -> dict[str, str]:
    """Session-scoped: raw text of all .py files under skills_runtime/skillpack/tools."""
    texts: dict[str, str] = {}
    for dirname in ("skills_runtime", "skillpack", "tools"):
        dirpath = SRC / dirname
        if not dirpath.is_dir():
            continue
        for py_file in sorted(dirpath.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            try:
                texts[str(py_file.relative_to(ROOT))] = py_file.read_text(encoding="utf-8")
            except Exception:
                pass
    return texts
