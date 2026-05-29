"""Architecture boundary tests — enforce clean separation between Research OS and legacy.

The restructured architecture enforces strict boundaries:
- Research OS (src/core/, src/schemas/, src/tools/, src/graph/, src/workflows/, src/infra/)
  must NOT import from the legacy system (legacy/).
- src/tools/ must remain pure: no LLM, no network IO.
"""

import ast
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_imports_from_dir(dirpath: str) -> set[str]:
    """Extract all imports from Python files in a directory."""
    imports = set()
    full_path = os.path.join(PROJECT_ROOT, dirpath)
    if not os.path.isdir(full_path):
        return imports
    for root, dirs, files in os.walk(full_path):
        dirs[:] = [d for d in dirs if not d.startswith('_') and d != '__pycache__']
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f)
            # Skip empty/deprecation-only marker files
            if os.path.getsize(filepath) < 100:
                try:
                    with open(filepath) as fh:
                        content = fh.read()
                    if '# DEPRECATED' in content:
                        continue
                except Exception:
                    pass
            try:
                with open(filepath) as fh:
                    tree = ast.parse(fh.read(), filename=f)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module)
            except SyntaxError:
                pass
    return imports


def _assert_no_legacy_imports(dirpath: str, label: str):
    """Assert that no file in dirpath imports from legacy.*."""
    imports = _get_imports_from_dir(dirpath)
    violations = [i for i in imports if i.startswith('legacy.')]
    assert not violations, f"{label} must not import from legacy/: {violations}"


# ── Boundary: Research OS must not import legacy ──────────────────────────

def test_core_does_not_import_legacy():
    """src/core/ must not import from legacy/."""
    _assert_no_legacy_imports('src/core', 'src/core')


def test_schemas_does_not_import_legacy():
    """src/schemas/ must not import from legacy/."""
    _assert_no_legacy_imports('src/schemas', 'src/schemas')


def test_tools_does_not_import_legacy():
    """src/tools/ must not import from legacy/."""
    _assert_no_legacy_imports('src/tools', 'src/tools')


def test_graph_does_not_import_legacy():
    """src/graph/ must not import from legacy/."""
    _assert_no_legacy_imports('src/graph', 'src/graph')


def test_workflows_does_not_import_legacy():
    """src/workflows/ must not import from legacy/."""
    _assert_no_legacy_imports('src/workflows', 'src/workflows')


def test_infra_does_not_import_legacy():
    """src/infra/ must not import from legacy/."""
    _assert_no_legacy_imports('src/infra', 'src/infra')


# ── Purity: tools/ must remain pure math ─────────────────────────────────

def test_tools_no_llm_imports():
    """src/tools/ modules must not import LLM modules."""
    imports = _get_imports_from_dir('src/tools')
    llm_imports = {'llm', 'langchain', 'openai', 'anthropic', 'google.generativeai'}
    violations = [i for i in imports if any(li in i.lower() for li in llm_imports)]
    assert not violations, f"src/tools imports LLM modules: {violations}"


def test_tools_no_network_io():
    """src/tools/ modules must not import network/HTTP clients."""
    imports = _get_imports_from_dir('src/tools')
    network_imports = {'requests', 'aiohttp', 'httpx', 'urllib3', 'websocket', 'socket'}
    violations = [i for i in imports if any(ni in i.lower() for ni in network_imports)]
    assert not violations, f"src/tools imports network modules: {violations}"
