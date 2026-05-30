"""Architecture boundary tests for the host-agnostic skill pack.

The architecture enforces strict boundaries:
- Skill pack code must NOT import from the legacy system (legacy/).
- Runtime skills must not depend on internal ResearchOS orchestration.
- src/tools/ must remain pure: no LLM, no network IO.
- src/ top-level must stay within the allowlist.
- Old src/ directories (news, analysis, output, etc.) must not be imported by new code.
"""

import ast
import os
import pytest
import yaml

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


def _read(relpath: str) -> str:
    with open(os.path.join(PROJECT_ROOT, relpath)) as f:
        return f.read()


def _load_skillpack_manifest() -> dict:
    return yaml.safe_load(_read("skillpack/fund-agent.skillpack.yaml"))


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
    ("src/skills_runtime", "src/skills_runtime"),
    ("src/skillpack", "src/skillpack"),
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

NEW_CODE_DIRS = [
    "src/core",
    "src/graph",
    "src/schemas",
    "src/tools",
    "src/workflows",
    "src/infra",
    "src/skills_runtime",
    "src/skillpack",
]

def test_new_code_no_old_imports():
    """New Research OS code must not import old src/ directories."""
    all_imports = set()
    for d in NEW_CODE_DIRS:
        all_imports.update(_get_imports_from_dir(d))
    violations = [i for i in all_imports if any(i.startswith(p) for p in OLD_SRC_DIRS)]
    assert not violations, f"New code imports old src/ dirs: {violations}"


def test_new_system_does_not_import_deprecated_shims():
    """New Research OS code must not import deprecated infra shim paths."""
    deprecated_shims = (
        "src.config.",
        "src.data.",
        "src.db.",
        "src.vectorstore.",
    )
    all_imports = set()
    for d in NEW_CODE_DIRS:
        all_imports.update(_get_imports_from_dir(d))
    violations = [
        item
        for item in all_imports
        if any(item.startswith(prefix) for prefix in deprecated_shims)
    ]
    assert not violations, f"New code imports deprecated shims: {violations}"


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
    heavy = {
        "pandas",
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "socket",
        "akshare",
        "openai",
        "anthropic",
        "langchain",
        "src.infra",
    }
    violations = [i for i in imports if any(h in i for h in heavy)]
    assert not violations, f"src/schemas imports heavy deps: {violations}"


def test_graph_no_legacy_dirs():
    _assert_no_imports_matching("src/graph", ["legacy.", "src.news.", "src.output.", "src.recommend."],
                                 "src/graph must not import legacy or old src dirs")


def test_skills_runtime_does_not_import_provider_sdks():
    """Skill runtime handlers must use MCPHostAdapter, not provider SDKs."""
    provider_or_network = [
        "legacy.",
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "socket",
        "tavily",
        "exa",
        "firecrawl",
        "finnhub",
        "reddit",
        "openai",
        "anthropic",
        "langchain",
    ]
    _assert_no_imports_matching(
        "src/skills_runtime",
        provider_or_network,
        "src/skills_runtime must stay adapter-only",
    )


def test_skills_runtime_does_not_import_research_os_runtime():
    """Host-callable skills must not depend on internal orchestration."""
    forbidden = [
        "src.core.research_os",
        "src.core.planner",
        "src.core.skill_registry",
        "src.workflows.research_os",
        "legacy.",
    ]
    _assert_no_imports_matching(
        "src/skills_runtime",
        forbidden,
        "src/skills_runtime must be host-callable without internal runtime",
    )


def test_skills_runtime_does_not_import_research_os_or_planner():
    """Runtime skills must not import ResearchOS, Planner, or SkillRegistry."""
    _assert_no_imports_matching(
        "src/skills_runtime",
        [
            "src.core.research_os",
            "src.core.planner",
            "src.core.skill_registry",
        ],
        "src/skills_runtime must not depend on internal orchestration",
    )


def test_mcp_adapter_has_no_network_dependency():
    """MCP adapter declaration must not import providers or network clients."""
    provider_or_network = [
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "socket",
        "tavily",
        "exa",
        "firecrawl",
        "finnhub",
        "reddit",
    ]
    _assert_no_imports_matching(
        "src/tools/adapters",
        provider_or_network,
        "src/tools/adapters must not import providers or network clients",
    )


def test_core_has_no_provider_sdk_dependency():
    """Core orchestration must not import concrete MCP provider SDKs."""
    provider_sdks = ["tavily", "exa", "firecrawl", "finnhub", "reddit"]
    _assert_no_imports_matching(
        "src/core",
        provider_sdks,
        "src/core must not import provider SDKs",
    )


def test_evidence_tools_have_no_network_or_llm_dependency():
    """Evidence/quant/ledger tools stay pure and do not import infra/network/LLM."""
    forbidden = [
        "src.infra",
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "socket",
        "openai",
        "anthropic",
        "langchain",
    ]
    for dirpath in ("src/tools/evidence", "src/tools/quant", "src/tools/ledger"):
        _assert_no_imports_matching(
            dirpath,
            forbidden,
            f"{dirpath} must not import infra, network, or LLM modules",
        )


def test_src_tools_do_not_import_legacy():
    _assert_no_imports_matching(
        "src/tools",
        ["legacy."],
        "src/tools must not import legacy",
    )


def test_workflows_research_os_has_no_provider_or_legacy_dependency():
    _assert_no_imports_matching(
        "src/workflows",
        ["legacy.", "tavily", "exa", "firecrawl", "finnhub", "reddit"],
        "src/workflows must not import legacy or provider SDKs",
    )


def test_skillpack_manifest_does_not_require_research_os_entrypoint():
    """The manifest must not require internal ResearchOS as host entrypoint."""
    manifest_path = os.path.join(PROJECT_ROOT, "skillpack", "fund-agent.skillpack.yaml")
    assert os.path.exists(manifest_path)
    with open(manifest_path) as f:
        data = yaml.safe_load(f)

    required = data.get("host_integration", {}).get("required_entrypoint", "")
    assert required == "skillpack/fund-agent.skillpack.yaml"
    assert "src.core.research_os" not in required
    assert "src/workflows/research_os.py" not in required


def test_skillpack_manifest_does_not_require_research_os():
    """Manifest must not require ResearchOS anywhere in host integration."""
    data = _load_skillpack_manifest()
    serialized = yaml.safe_dump(data)

    assert data["host_integration"]["required_entrypoint"] == (
        "skillpack/fund-agent.skillpack.yaml"
    )
    assert "src.core.research_os" not in serialized
    assert "src/workflows/research_os.py" not in serialized


def test_readme_positions_skillpack_as_primary_product():
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path) as f:
        content = f.read()

    assert "Host-Agnostic AI Financial Research Skill Pack" in content
    assert "skillpack/fund-agent.skillpack.yaml" in content
    assert "Host integrations do not need to import or call" in content
    assert "Research OS Path (New)" not in content
    assert "primary structured path" not in content


def test_readme_identifies_skill_pack_as_primary_product():
    """README must position fund-agent as a host-mounted skill pack."""
    content = _read("README.md")

    assert "Host-Agnostic" in content
    assert "Skill Pack" in content
    assert "external agent" in content
    assert "skillpack/fund-agent.skillpack.yaml" in content


def test_readme_does_not_require_research_os_for_new_integrations():
    """README must not tell new integrations to use ResearchOS."""
    content = _read("README.md")
    forbidden = [
        "New integrations should use src.core.research_os",
        "src/ = Research OS 主路径",
        "Research OS Path (New)",
    ]

    violations = [phrase for phrase in forbidden if phrase in content]
    assert not violations


def test_host_integration_doc_exists_and_contains_flow():
    doc_path = os.path.join(PROJECT_ROOT, "docs", "host-integration.md")
    assert os.path.exists(doc_path)
    with open(doc_path) as f:
        content = f.read()

    for phrase in (
        "external agent host",
        "load_skillpack_manifest",
        "resolve_runtime",
        "SkillInput",
        "compile_evidence_graph",
        "DecisionSupportSkill",
    ):
        assert phrase in content


def test_host_integration_doc_says_research_os_not_required():
    content = _read("docs/host-integration.md")

    assert "Host integrations do not need to call `src.core.research_os`" in content
    assert "does not own the agent loop" in content


def test_decision_support_is_only_formal_decision_skill():
    data = _load_skillpack_manifest()
    decision_skills = [
        skill["name"]
        for skill in data["skills"]
        if "Decision" in skill.get("produces", [])
        or "ExecutionLedger" in skill.get("produces", [])
    ]

    assert decision_skills == ["decision_support"]


def test_thesis_generation_forbids_decision_generation():
    data = _load_skillpack_manifest()
    thesis = next(skill for skill in data["skills"] if skill["name"] == "thesis_generation")

    assert "formal_decision_generation" in thesis.get("forbidden", [])
    assert "formal_decision_generation" in _read("skills/thesis-generation/SKILL.md")


def test_manifest_skill_docs_have_runtime_contract_fields():
    docs = {
        "fund_analysis": "skills/fund-analysis/SKILL.md",
        "news_research": "skills/news-research/SKILL.md",
        "sentiment_analysis": "skills/sentiment-analysis/SKILL.md",
        "thesis_generation": "skills/thesis-generation/SKILL.md",
        "decision_support": "skills/decision-support/SKILL.md",
    }
    required = (
        "id:",
        "runtime:",
        "input_schema:",
        "output_schema:",
        "required_mcp_capabilities",
        "Example SkillInput",
        "Example SkillOutput",
    )

    for skill_id, path in docs.items():
        content = _read(path)
        assert skill_id in content
        for phrase in required:
            assert phrase in content, f"{path} missing {phrase}"


# ═══════════════════════════════════════════════════════════════════════════════
# Top-level allowlist
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWLIST = frozenset({
    "core", "schemas", "graph", "tools", "infra", "workflows",
    "skills_runtime", "skillpack",
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


def test_src_config_is_only_deprecated_shim():
    _assert_deprecated_shim_only("config")


def test_src_data_is_only_deprecated_shim():
    _assert_deprecated_shim_only("data")


def test_src_db_is_only_deprecated_shim():
    _assert_deprecated_shim_only("db")


def test_src_vectorstore_is_only_deprecated_shim():
    _assert_deprecated_shim_only("vectorstore")


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
