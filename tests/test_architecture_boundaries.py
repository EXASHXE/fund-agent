"""Architecture boundary tests — enforce clean separation between Research OS and legacy.

The restructured architecture enforces strict boundaries:
- Research OS (src/core/, src/schemas/, src/tools/, src/graph/, src/workflows/, src/infra/)
  must NOT import from the legacy system (legacy/).
- src/tools/ must remain pure: no LLM, no network IO.
- src/ top-level must stay within the allowlist.
- Old src/ directories (news, analysis, output, etc.) must not be imported by new code.
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
            if os.path.getsize(filepath) < 100:
                try:
                    with open(filepath) as fh:
                        if '# DEPRECATED' in fh.read():
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


def _assert_no_imports_matching(dirpath: str, patterns: list[str], label: str):
    """Assert that no file in dirpath imports modules matching any pattern."""
    imports = _get_imports_from_dir(dirpath)
    violations = [i for i in imports if any(p in i for p in patterns)]
    assert not violations, f"{label}: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Research OS must not import legacy
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("dirpath,label", [
    ("src/core", "src/core"),
    ("src/schemas", "src/schemas"),
    ("src/tools", "src/tools"),
    ("src/graph", "src/graph"),
    ("src/workflows", "src/workflows"),
    ("src/infra", "src/infra"),
])
def test_no_legacy_imports(dirpath, label):
    _assert_no_imports_matching(dirpath, ["legacy."], f"{label} must not import from legacy/")


def test_research_os_no_legacy():
    """src/workflows/research_os.py must not import from legacy/."""
    fp = os.path.join(PROJECT_ROOT, "src", "workflows", "research_os.py")
    if not os.path.exists(fp):
        pytest.skip("research_os.py not found")
    with open(fp) as f:
        tree = ast.parse(f.read(), filename=fp)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    violations = [i for i in imports if i.startswith("legacy.")]
    assert not violations, f"research_os.py must not import legacy: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: New code must not import old src/ directories
# ═══════════════════════════════════════════════════════════════════════════════

OLD_SRC_DIRS = [
    "src.news", "src.analysis", "src.output", "src.recommend",
    "src.ui", "src.routes", "src.strategy", "src.engine",
    "src.events", "src.forecast", "src.deprecated", "src.agents",
    "src.services", "src.prompts", "src.decision",
]

NEW_CODE_DIRS = ["src/core", "src/graph", "src/schemas", "src/tools", "src/workflows", "src/infra"]

def test_new_code_no_old_imports():
    """New Research OS code must not import old src/ directories."""
    all_imports = set()
    for d in NEW_CODE_DIRS:
        all_imports.update(_get_imports_from_dir(d))
    violations = [i for i in all_imports if any(i.startswith(p) for p in OLD_SRC_DIRS)]
    assert not violations, f"New code imports old src/ dirs: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: New code must not import shimmed infra old paths directly
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("dirpath", ["src/core", "src/tools", "src/graph", "src/schemas", "src/workflows"])
def test_no_direct_config_import(dirpath):
    _assert_no_imports_matching(dirpath, ["src.config."], f"{dirpath} must not import src.config (use src.infra.config)")

@pytest.mark.parametrize("dirpath", ["src/core", "src/tools", "src/graph", "src/schemas", "src/workflows"])
def test_no_direct_data_import(dirpath):
    _assert_no_imports_matching(dirpath, ["src.data."], f"{dirpath} must not import src.data (use src.infra.data)")

@pytest.mark.parametrize("dirpath", ["src/core", "src/tools", "src/graph", "src/schemas", "src/workflows"])
def test_no_direct_db_import(dirpath):
    _assert_no_imports_matching(dirpath, ["src.db."], f"{dirpath} must not import src.db (use src.infra.persistence)")

@pytest.mark.parametrize("dirpath", ["src/core", "src/tools", "src/graph", "src/schemas", "src/workflows"])
def test_no_direct_vectorstore_import(dirpath):
    _assert_no_imports_matching(dirpath, ["src.vectorstore."], f"{dirpath} must not import src.vectorstore (use src.infra.vectorstore)")

@pytest.mark.parametrize("dirpath", ["src/core", "src/tools", "src/graph", "src/schemas", "src/workflows"])
def test_no_direct_kg_import(dirpath):
    _assert_no_imports_matching(dirpath, ["src.kg."], f"{dirpath} must not import src.kg (use src.graph)")


# ═══════════════════════════════════════════════════════════════════════════════
# Purity: tools/ must remain pure math
# ═══════════════════════════════════════════════════════════════════════════════

def test_tools_no_llm_imports():
    imports = _get_imports_from_dir("src/tools")
    llm_keywords = {"llm", "langchain", "openai", "anthropic", "google.generativeai"}
    violations = [i for i in imports if any(kw in i.lower() for kw in llm_keywords)]
    assert not violations, f"src/tools imports LLM modules: {violations}"


def test_tools_no_network_io():
    imports = _get_imports_from_dir("src/tools")
    network_keywords = {"requests", "aiohttp", "httpx", "urllib3", "websocket", "socket", "akshare"}
    violations = [i for i in imports if any(kw in i.lower() for kw in network_keywords)]
    assert not violations, f"src/tools imports network modules: {violations}"


def test_schemas_no_heavy_deps():
    imports = _get_imports_from_dir("src/schemas")
    heavy = {"pandas", "requests", "akshare"}
    violations = [i for i in imports if any(h in i for h in heavy)]
    assert not violations, f"src/schemas imports heavy deps: {violations}"


def test_graph_no_legacy_dirs():
    _assert_no_imports_matching("src/graph", ["legacy.", "src.news.", "src.output.", "src.recommend."],
                                 "src/graph must not import legacy or old src dirs")


# ═══════════════════════════════════════════════════════════════════════════════
# Top-level allowlist
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWLIST = frozenset({
    "core", "schemas", "graph", "tools", "infra", "workflows",
    "__init__.py", "cli.py",
    # DEPRECATED compatibility shims — marked for removal
    "config", "data", "db", "kg", "vectorstore",
})


def test_src_top_level_allowlist():
    """src/ top-level must only contain allowlisted entries."""
    src_dir = os.path.join(PROJECT_ROOT, "src")
    entries = set(os.listdir(src_dir))
    entries.discard("__pycache__")
    violations = entries - ALLOWLIST
    assert not violations, f"src/ has non-allowlisted entries: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: src/kg/ must be only a deprecated shim
# ═══════════════════════════════════════════════════════════════════════════════

KG_IMPLEMENTATION_FILES = {"graph.py", "schema.py", "diff.py", "enrichment.py", "industry_map.py"}


def test_src_kg_is_only_deprecated_shim():
    """src/kg/ must not contain implementation files — only __init__.py shim."""
    _assert_deprecated_shim_only("kg")


@pytest.mark.parametrize("shim_dir", ["config", "data", "db", "vectorstore"])
def test_deprecated_compat_shims_are_init_only(shim_dir):
    """Deprecated compat shim dirs must not retain implementation files."""
    _assert_deprecated_shim_only(shim_dir)


def _assert_deprecated_shim_only(shim_dir: str):
    shim_path = os.path.join(PROJECT_ROOT, "src", shim_dir)
    if not os.path.isdir(shim_path):
        pytest.skip(f"src/{shim_dir} directory not found")
    entries = set(os.listdir(shim_path))
    entries.discard("__pycache__")
    assert entries == {"__init__.py"}, (
        f"src/{shim_dir}/ must be only a deprecated __init__.py shim, "
        f"found: {sorted(entries)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: README must not describe old src/ layout as new architecture
# ═══════════════════════════════════════════════════════════════════════════════

def test_readme_does_not_describe_old_src_layout():
    """README must not describe old src/ directories as new system architecture."""
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    if not os.path.exists(readme_path):
        pytest.skip("README.md not found")
    with open(readme_path) as f:
        content = f.read()
    # Old paths that should NOT appear as new architecture descriptions
    old_path_patterns = [
        "src/agents/",
        "src/analysis/",
        "src/news/",
        "src/output/",
        "src/recommend/",
        "src/ui/",
        "src/routes/",
        "src/strategy/",
        "src/engine/",
        "src/events/",
        "src/forecast/",
        "src/services/",
        "src/prompts/",
        "src/decision/",
        "src/deprecated/",
    ]
    violations = [p for p in old_path_patterns if p in content]
    assert not violations, (
        f"README still describes old src/ paths as new architecture: {violations}. "
        f"Update to describe legacy/ paths instead."
    )
