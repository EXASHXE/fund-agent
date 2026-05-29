"""Architecture boundary tests — enforce clean separation."""

import ast
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_imports_from_dir(dirpath: str) -> set[str]:
    """Extract all imports from Python files in a directory."""
    imports = set()
    for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, dirpath)):
        dirs[:] = [d for d in dirs if not d.startswith('_') and d != '__pycache__']
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f)
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


def test_core_does_not_import_deprecated():
    """src/core/ modules must not import from src.deprecated."""
    imports = _get_imports_from_dir('src/core')
    violations = [i for i in imports if 'deprecated' in i]
    assert not violations, f"src/core imports deprecated: {violations}"


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


def test_graph_does_not_import_deprecated():
    """src/graph/ modules must not import from src.deprecated."""
    imports = _get_imports_from_dir('src/graph')
    violations = [i for i in imports if 'deprecated' in i]
    assert not violations, f"src/graph imports deprecated: {violations}"
