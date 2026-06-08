"""Architecture tests verifying deprecated src-level surfaces are removed or guarded."""

from __future__ import annotations

import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

DEPRECATED_SHIM_ONLY = {"config", "data", "db", "kg", "vectorstore"}


def _imports_from_dir(dirpath: Path) -> set[str]:
    imports: set[str] = set()
    if not dirpath.is_dir():
        return imports
    for path in sorted(dirpath.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    return imports


def _deprecated_shims_are_init_only():
    """Deprecated compatibility shims must be __init__.py only."""
    for shim_name in sorted(DEPRECATED_SHIM_ONLY):
        shim_path = SRC / shim_name
        if not shim_path.is_dir():
            continue
        entries = set(p.name for p in shim_path.iterdir())
        entries.discard("__pycache__")
        extra = entries - {"__init__.py"}
        assert not extra, f"src/{shim_name} must be __init__.py only, found: {extra}"


def test_plugin_core_does_not_import_src_core():
    """No plugin runtime code may import deprecated src.core."""
    for subdir in ("skills_runtime", "skillpack", "tools", "schemas", "graph"):
        imports = _imports_from_dir(SRC / subdir)
        violations = [i for i in imports if i.startswith("src.core")]
        assert not violations, f"src/{subdir} imports src.core: {violations}"


def test_plugin_core_does_not_import_src_workflows():
    """No plugin runtime code may import deprecated src.workflows."""
    for subdir in ("skills_runtime", "skillpack", "tools", "schemas", "graph"):
        imports = _imports_from_dir(SRC / subdir)
        violations = [i for i in imports if i.startswith("src.workflows")]
        assert not violations, f"src/{subdir} imports src.workflows: {violations}"


def test_src_cli_is_deprecated_stub():
    """src/cli.py must be a harmless deprecated stub, not a ResearchOS CLI."""
    cli_path = SRC / "cli.py"
    if not cli_path.is_file():
        return
    text = cli_path.read_text(encoding="utf-8")
    assert "deprecated" in text.lower()
    assert "not part of the plugin contract" in text


def test_deprecated_shims_present_if_still_configured():
    """Verify shim-only directories remain __init__.py only."""
    _deprecated_shims_are_init_only()


def test_docs_do_not_describe_src_core_as_runtime():
    """Docs must not describe src/core or src/infra as current runtime path."""
    docs_dir = ROOT / "docs"
    problematic: list[tuple[str, str]] = []
    for doc_path in sorted(docs_dir.rglob("*.md")):
        if "archive" in str(doc_path):
            continue
        text = doc_path.read_text(encoding="utf-8").lower()
        for phrase in ("src/core is", "src/infra is", "src.workflows is", "src/core provides"):
            if phrase in text:
                problematic.append((str(doc_path.relative_to(ROOT)), phrase))
    assert not problematic, f"Docs describe deprecated surfaces as current: {problematic}"
