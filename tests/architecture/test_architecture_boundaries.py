"""Architecture boundary tests for the host-agnostic skill pack.

The architecture enforces strict boundaries:
- Skill pack code must NOT import from the legacy system (legacy/).
- Runtime skills must not depend on internal ResearchOS (optional reference only).
- src/tools/ must remain pure: no LLM, no network IO.
- src/ top-level must stay within the allowlist.
- Old src/ directories (news, analysis, output, etc.) must not be imported by plugin code.
"""

import ast
import os
import pytest
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
# Boundary: Skill Pack code must not import legacy
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


def test_src_does_not_import_legacy():
    """No src module may import the historical legacy archive."""
    _assert_no_imports_matching("src", ["legacy", "legacy."], "src must not import legacy")


def test_optional_reference_workflows_do_not_import_legacy():
    """Optional reference workflow (src/workflows/research_os.py) must not import from legacy/."""
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
    assert not violations, f"optional reference workflow research_os.py must not import legacy: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Plugin runtime code must not import old src/ directories
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
    """Plugin runtime code must not import old src/ directories."""
    all_imports = set()
    for d in NEW_CODE_DIRS:
        all_imports.update(_get_imports_from_dir(d))
    violations = [i for i in all_imports if any(i.startswith(p) for p in OLD_SRC_DIRS)]
    assert not violations, f"New code imports old src/ dirs: {violations}"


def test_new_system_does_not_import_deprecated_shims():
    """Plugin runtime code must not import deprecated infra shim paths."""
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
# Boundary: Plugin runtime code must not import shimmed infra old paths directly
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
        "tavily",
        "exa",
        "firecrawl",
        "finnhub",
        "reddit",
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


def test_skillpack_loader_has_no_network_or_provider_dependency():
    _assert_no_imports_matching(
        "src/skillpack",
        [
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
        ],
        "src/skillpack must not import network, LLM, or provider SDKs",
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


def test_skillpack_examples_do_not_reference_research_os_required_path():
    examples_dir = os.path.join(PROJECT_ROOT, "skillpack", "examples")
    assert os.path.isdir(examples_dir)
    serialized = []
    for filename in os.listdir(examples_dir):
        if filename.endswith(".json"):
            serialized.append(_read(os.path.join("skillpack", "examples", filename)))
    content = "\n".join(serialized)

    assert "src.core.research_os" not in content
    assert "src/workflows/research_os.py" not in content


def test_readme_positions_skillpack_as_primary_product():
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    with open(readme_path) as f:
        content = f.read()

    assert "Host-Agnostic AI Financial Research Skill Pack" in content
    assert "Host-Agnostic AI Financial Research Skill Pack / Agent Plugin" in content
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
    assert "ResearchOS is optional reference only, not required" in content
    assert "does not own the agent loop" in content
    forbidden = [
        "must call ResearchOS",
        "requires ResearchOS",
        "required ResearchOS",
    ]
    assert not [phrase for phrase in forbidden if phrase in content]


def test_agent_host_quickstart_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "docs", "agent-host-quickstart.md"))


def test_agent_host_quickstart_mentions_external_agent_owns_orchestration():
    content = _read("docs/agent-host-quickstart.md")

    assert "external agent owns orchestration" in content.lower()
    assert "load_skillpack_manifest" in content
    assert "DecisionSupportSkill" in content


def test_agent_host_quickstart_does_not_require_research_os():
    content = _read("docs/agent-host-quickstart.md")

    assert "Do not call ResearchOS for host integration" in content
    assert "ResearchOS is optional reference only, not required" in content
    forbidden = [
        "must call ResearchOS",
        "requires ResearchOS",
        "required ResearchOS",
        "src.core.research_os",
    ]
    assert not [phrase for phrase in forbidden if phrase in content]


def test_research_os_reference_modules_are_labeled_deprecated_optional():
    required_phrases = [
        "Deprecated / optional reference only.",
        "Not required for host integration.",
        "External agents should use skillpack manifest and skills_runtime directly.",
    ]
    for relpath in (
        "src/core/research_os.py",
        "src/workflows/research_os.py",
        "src/core/planner.py",
        "src/core/skill_registry.py",
        "src/core/critic.py",
    ):
        content = _read(relpath)
        for phrase in required_phrases:
            assert phrase in content, f"{relpath} missing {phrase}"


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


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Legacy README must be historical archive only
# ═══════════════════════════════════════════════════════════════════════════════

def test_legacy_readme_is_historical_archive_only():
    """legacy/README.md must be a pointer to the alpha tag, not ResearchOS replacement."""
    content = _read("legacy/README.md")

    assert "v0.1.0-skillpack-alpha" in content
    assert "git checkout" in content

    forbidden = [
        "Research OS Skill pipeline",
        "New Research OS",
        "src.core.research_os as replacement",
        "run_research_task",
    ]
    violations = [phrase for phrase in forbidden if phrase in content]
    assert not violations, f"legacy/README.md references ResearchOS as replacement: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Low-value legacy dirs must be removed
# ═══════════════════════════════════════════════════════════════════════════════

def test_low_value_legacy_dirs_removed():
    """ui, routes, services, agents, forecast must not exist under legacy/."""
    deleted = ["ui", "routes", "services", "agents", "forecast"]
    remaining = []
    for d in deleted:
        p = os.path.join(PROJECT_ROOT, "legacy", d)
        if os.path.exists(p):
            remaining.append(d)
    assert not remaining, f"Low-value legacy dirs still exist: {remaining}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Plugin main paths must not import legacy
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("dirpath,label", [
    ("src/skills_runtime", "src/skills_runtime"),
    ("src/tools", "src/tools"),
    ("src/schemas", "src/schemas"),
    ("src/graph", "src/graph"),
    ("src/skillpack", "src/skillpack"),
])
def test_main_plugin_paths_do_not_import_legacy(dirpath, label):
    _assert_no_imports_matching(dirpath, ["legacy."], f"{label} must not import legacy")


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: tests/deprecated must not be in default pytest testpaths
# ═══════════════════════════════════════════════════════════════════════════════

def test_deprecated_not_in_default_pytest_testpaths():
    """pyproject.toml testpaths must not include tests/deprecated."""
    pyproject_path = os.path.join(PROJECT_ROOT, "pyproject.toml")
    content = _read(pyproject_path)

    assert "tests/deprecated" not in content.split("[tool.pytest.ini_options]")[1].split("[")[0], (
        "tests/deprecated must not be in pyproject.toml testpaths"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Plugin API documentation must exist and be correct
# ═══════════════════════════════════════════════════════════════════════════════

def test_plugin_api_doc_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "docs", "plugin-api.md"))


def test_plugin_api_doc_mentions_external_host():
    content = _read("docs/plugin-api.md")

    assert "external host" in content.lower()
    assert "external_agent" in content
    assert "external_host" in content


def test_plugin_api_doc_does_not_require_research_os():
    content = _read("docs/plugin-api.md")

    # "src.core.research_os" may appear only in "what not to do" context
    forbidden_present = [
        "call src.core.research_os",
        "import src.core.research_os",
    ]
    for phrase in forbidden_present:
        if phrase in content:
            assert "NOT" in content[content.index(phrase)-50:content.index(phrase)+50].upper(), (
                f"plugin-api.md mentions {phrase} without forbidding it"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Legacy README must not mention deleted dirs as remaining
# ═══════════════════════════════════════════════════════════════════════════════

def test_legacy_readme_matches_existing_dirs():
    """legacy/README.md must not list deleted dirs in remaining components."""
    content = _read("legacy/README.md")
    deleted_refs = [
        "`legacy/routes/`",
        "`legacy/agents/`",
        "`legacy/services/`",
        "`legacy/forecast/`",
        "`legacy/ui/`",
    ]
    # Find the Remaining Components section (before Deleted Directories)
    remaining_section = content.split("Deleted Directories")[0]
    violations = [ref for ref in deleted_refs if ref in remaining_section]
    assert not violations, f"legacy/README.md lists deleted dirs in remaining section: {violations}"


def test_readme_legacy_description_does_not_mention_deleted_ui():
    content = _read("README.md")

    assert "ui compatibility path" not in content


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Cleanup verification for Beta-8.1 release
# ═══════════════════════════════════════════════════════════════════════════════

def test_legacy_readme_does_not_reference_deleted_legacy_dirs():
    """legacy/README.md must not reference deleted legacy dirs."""
    content = _read("legacy/README.md")
    deleted_names = ["legacy/ui", "legacy/routes", "legacy/services", "legacy/agents", "legacy/forecast"]
    violations = [name for name in deleted_names if name in content]
    assert not violations, f"legacy/README.md references deleted dirs: {violations}"


def test_readme_legacy_layout_does_not_reference_deleted_ui():
    """README must not describe legacy as a ui compatibility path."""
    content = _read("README.md")

    assert "legacy/" in content
    assert "ui compatibility" not in content


def test_check_plugin_gate_script_exists_and_is_executable():
    path = os.path.join(PROJECT_ROOT, "scripts", "check_plugin_gate.sh")

    assert os.path.exists(path)
    assert os.access(path, os.X_OK)


def test_check_plugin_gate_script_does_not_run_deprecated():
    content = _read("scripts/check_plugin_gate.sh")

    assert "pytest tests/deprecated" not in content


def test_legacy_deprecated_news_pipeline_removed():
    assert not os.path.exists(
        os.path.join(PROJECT_ROOT, "legacy", "deprecated", "news_pipeline.py")
    )


def test_archived_broken_deprecated_tests_removed():
    assert not os.path.exists(
        os.path.join(PROJECT_ROOT, "tests", "deprecated", "archived_broken")
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Post-Alpha legacy removal (Beta-9)
# ═══════════════════════════════════════════════════════════════════════════════

def test_legacy_code_removed_or_pointer_only():
    """legacy/ must not exist, or contain only README.md."""
    legacy_path = os.path.join(PROJECT_ROOT, "legacy")
    if os.path.exists(legacy_path):
        entries = set(os.listdir(legacy_path))
        entries.discard("__pycache__")
        assert entries == {"README.md"}, f"legacy/ contains unexpected entries: {entries}"


def test_tests_deprecated_removed():
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "tests", "deprecated"))


def test_readme_points_to_alpha_tag_for_legacy():
    content = _read("README.md")
    assert "v0.1.0-skillpack-alpha" in content


def test_archive_doc_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "docs", "archive", "legacy-system.md"))


def test_archive_doc_mentions_alpha_tag():
    content = _read("docs/archive/legacy-system.md")
    assert "v0.1.0-skillpack-alpha" in content


def test_no_plugin_path_imports_legacy():
    """No plugin code path may import legacy."""
    for dirpath, label in [
        ("src", "src"),
        ("skillpack", "skillpack"),
        ("skills", "skills"),
        ("docs", "docs"),
        ("tests/architecture", "tests/architecture"),
        ("tests/contracts", "tests/contracts"),
        ("tests/skillpack", "tests/skillpack"),
        ("tests/skills", "tests/skills"),
        ("tests/tools", "tests/tools"),
        ("tests/integration", "tests/integration"),
    ]:
        imports = _get_imports_from_dir(dirpath)
        violations = [i for i in imports if i == "legacy" or i.startswith("legacy.")]
        assert not violations, f"{label} imports legacy: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Host integration UX (Beta-10)
# ═══════════════════════════════════════════════════════════════════════════════

def test_agents_md_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "AGENTS.md"))


def test_agents_md_identifies_external_host_as_orchestrator():
    content = _read("AGENTS.md")

    assert "external agent" in content.lower() or "external agents" in content.lower()
    assert "planning" in content.lower()
    assert "Host-Agnostic" in content or "host-agnostic" in content


def test_agents_md_does_not_require_research_os():
    content = _read("AGENTS.md")

    # "src.core.research_os" may appear only in "Do NOT use" context
    if "src.core.research_os" in content:
        idx = content.index("src.core.research_os")
        context = content[max(0, idx-100):idx+100].upper()
        assert "NOT" in context, "AGENTS.md mentions src.core.research_os without forbidding it"
    assert "New integrations should use" not in content


def test_examples_readme_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "skillpack", "examples", "README.md"))


def test_minimal_host_demo_exists():
    assert os.path.exists(
        os.path.join(PROJECT_ROOT, "examples", "minimal_host_news_to_decision.py")
    )


def test_minimal_host_demo_does_not_import_research_os_or_legacy():
    demo_path = os.path.join(PROJECT_ROOT, "examples", "minimal_host_news_to_decision.py")
    content = _read("examples/minimal_host_news_to_decision.py")

    assert "src.core.research_os" not in content
    assert "import legacy" not in content
    assert "from legacy" not in content


def test_readme_mentions_agent_quick_start():
    content = _read("README.md")

    assert "Agent Quick Start" in content
    assert "AGENTS.md" in content


def test_plugin_api_mentions_skill_error_codes():
    content = _read("docs/plugin-api.md")

    assert "SkillError Codes" in content or "Standard Error Codes" in content


def test_changelog_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "CHANGELOG.md"))


def test_changelog_mentions_current_version():
    content = _read("CHANGELOG.md")
    version = _read("VERSION").strip()
    assert version in content, f"CHANGELOG.md must mention {version}"


def test_changelog_mentions_legacy_alpha_tag():
    content = _read("CHANGELOG.md")
    assert "v0.1.0-skillpack-alpha" in content


def test_markdown_docs_are_not_single_line_blobs():
    docs = [
        "AGENTS.md",
        "README.md",
        "docs/plugin-api.md",
        "docs/skill-io-examples.md",
        "docs/agent-host-quickstart.md",
        "docs/host-integration.md",
        "skillpack/examples/README.md",
        "docs/release-checklist.md",
        "docs/maintenance.md",
    ]
    for path in docs:
        content = _read(path)
        lines = content.split("\n")
        assert len(lines) > 10, f"{path} has only {len(lines)} lines"
        assert any(line.strip().startswith("#") for line in lines), f"{path} has no heading"


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary: Host compatibility (RC-1)
# ═══════════════════════════════════════════════════════════════════════════════

def test_host_compatibility_doc_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "docs", "host-compatibility.md"))


def test_host_compatibility_doc_mentions_major_hosts():
    content = _read("docs/host-compatibility.md")
    for host in ("OpenCode", "Claude Code", "Codex", "OpenClaw", "Hermes"):
        assert host in content, f"host-compatibility missing {host}"


def test_host_compatibility_doc_does_not_require_research_os():
    content = _read("docs/host-compatibility.md")
    # "ResearchOS" may appear only as "not required"
    if "ResearchOS" in content:
        idx = content.index("ResearchOS")
        context = content[max(0, idx-100):idx+100].lower()
        assert "not" in context, "host-compatibility.md mentions ResearchOS without saying not required"
    assert "src.core.research_os" not in content
