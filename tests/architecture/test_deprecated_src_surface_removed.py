"""Architecture tests verifying deprecated src-level surfaces are removed."""

from __future__ import annotations

import ast
import os
from pathlib import Path

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

ALLOWED_RETAINED_PATHS: dict[str, str] = {}


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


def _assert_path_removed(relpath: str, reason: str):
    full = ROOT / relpath
    if relpath in ALLOWED_RETAINED_PATHS:
        return
    assert not full.exists(), f"{relpath} still exists ({reason})"


def test_src_core_removed():
    _assert_path_removed("src/core", DEPRECATED_SRC_PATHS["src/core"])


def test_src_infra_removed():
    _assert_path_removed("src/infra", DEPRECATED_SRC_PATHS["src/infra"])


def test_src_workflows_removed():
    _assert_path_removed("src/workflows", DEPRECATED_SRC_PATHS["src/workflows"])


def test_src_config_removed():
    _assert_path_removed("src/config", DEPRECATED_SRC_PATHS["src/config"])


def test_src_data_removed():
    _assert_path_removed("src/data", DEPRECATED_SRC_PATHS["src/data"])


def test_src_db_removed():
    _assert_path_removed("src/db", DEPRECATED_SRC_PATHS["src/db"])


def test_src_kg_removed():
    _assert_path_removed("src/kg", DEPRECATED_SRC_PATHS["src/kg"])


def test_src_vectorstore_removed():
    _assert_path_removed("src/vectorstore", DEPRECATED_SRC_PATHS["src/vectorstore"])


def test_src_cli_removed():
    cli_path = SRC / "cli.py"
    if "src/cli.py" in ALLOWED_RETAINED_PATHS:
        return
    assert not cli_path.is_file(), "src/cli.py still exists"


def test_plugin_core_does_not_import_deprecated_paths():
    """No plugin runtime code may import any deprecated src surface."""
    deprecated_module_prefixes = (
        "src.core", "src.infra", "src.workflows",
        "src.config", "src.data", "src.db",
        "src.kg", "src.vectorstore",
    )
    for subdir in ("skills_runtime", "skillpack", "tools", "schemas", "graph"):
        imports = _imports_from_dir(SRC / subdir)
        violations = [
            i for i in imports
            if any(i.startswith(prefix) for prefix in deprecated_module_prefixes)
        ]
        assert not violations, f"src/{subdir} imports deprecated path: {violations}"


def test_docs_do_not_describe_deprecated_paths_as_runtime():
    """Docs must not describe deprecated src paths as current runtime paths."""
    docs_dir = ROOT / "docs"
    problematic: list[tuple[str, str]] = []
    for doc_path in sorted(docs_dir.rglob("*.md")):
        if "archive" in str(doc_path):
            continue
        text = doc_path.read_text(encoding="utf-8").lower()
        for phrase in (
            "src/core is", "src/infra is", "src.workflows is",
            "src/core provides", "src/infra provides",
            "src/config", "src/data", "src/db",
            "src/kg", "src/vectorstore",
        ):
            if phrase in text:
                problematic.append((str(doc_path.relative_to(ROOT)), phrase))
    assert not problematic, f"Docs describe deprecated surfaces as current: {problematic}"


def test_docs_maintenance_does_not_call_deprecated_as_current():
    """docs/maintenance.md must not call deprecated paths current optional runtime."""
    maint = ROOT / "docs" / "maintenance.md"
    if not maint.is_file():
        return
    text = maint.read_text(encoding="utf-8").lower()
    deprecated_terms = (
        "src/core", "src/infra", "src/workflows",
        "src/config", "src/data", "src/db",
    )
    for term in deprecated_terms:
        assert term not in text, f"docs/maintenance.md references deprecated {term}"
