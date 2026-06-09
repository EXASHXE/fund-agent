"""Final boundary audit for pre-release readiness.

Static assertions ensuring no provider SDKs, network clients, broker/order
execution machinery, or deprecated surfaces exist in runtime plugin core.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


_PROVIDER_SDKS = {
    "tavily", "exa", "firecrawl", "finnhub", "reddit",
    "akshare", "openai", "anthropic", "langchain",
}

_NETWORK_CLIENTS = {
    "requests", "httpx", "aiohttp", "urllib3", "socket",
}

_BROKER_KEYWORDS = {
    "place_order", "submit_order", "broker_client", "brokerage",
    "trade_execution_api",
}

_DEPRECATED_SRC_MODULES = {
    "src.core", "src.infra", "src.workflows",
    "src.config", "src.data", "src.db",
    "src.kg", "src.vectorstore",
}


def _imports_from_file(path: Path) -> set[str]:
    imports: set[str] = set()
    if not path.is_file():
        return imports
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _imports_from_dir(dirpath: Path) -> set[str]:
    imports: set[str] = set()
    if not dirpath.is_dir():
        return imports
    for py_file in sorted(dirpath.rglob("*.py")):
        if "__pycache__" in str(py_file):
            continue
        imports.update(_imports_from_file(py_file))
    return imports


def test_no_provider_sdks_in_skills_runtime():
    imports = _imports_from_dir(SRC / "skills_runtime")
    violations = imports & _PROVIDER_SDKS
    assert not violations, f"skills_runtime imports provider SDKs: {violations}"


def test_no_provider_sdks_in_skillpack():
    imports = _imports_from_dir(SRC / "skillpack")
    violations = imports & _PROVIDER_SDKS
    assert not violations, f"skillpack imports provider SDKs: {violations}"


def test_no_provider_sdks_in_tools():
    imports = _imports_from_dir(SRC / "tools")
    violations = imports & _PROVIDER_SDKS
    assert not violations, f"tools imports provider SDKs: {violations}"


def test_no_network_clients_in_skills_runtime():
    imports = _imports_from_dir(SRC / "skills_runtime")
    violations = imports & _NETWORK_CLIENTS
    assert not violations, f"skills_runtime imports network clients: {violations}"


def test_no_network_clients_in_skillpack():
    imports = _imports_from_dir(SRC / "skillpack")
    violations = imports & _NETWORK_CLIENTS
    assert not violations, f"skillpack imports network clients: {violations}"


def test_no_broker_keywords_in_runtime_source():
    runtime_dirs = ("skills_runtime", "skillpack", "tools")
    for dirname in runtime_dirs:
        dirpath = SRC / dirname
        if not dirpath.is_dir():
            continue
        for py_file in dirpath.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            text = py_file.read_text(encoding="utf-8").lower()
            for kw in _BROKER_KEYWORDS:
                assert kw not in text, (
                    f"{py_file.relative_to(ROOT)} contains broker keyword: {kw}"
                )


def test_opencode_plugin_does_not_invoke_python_or_child_process():
    js = (ROOT / "opencode.plugin.js").read_text(encoding="utf-8")
    for kw in ("child_process", "execFile", "execSync", "spawn(", "exec(",
               'spawnSync', 'python3', 'sys.executable'):
        assert kw not in js, f"opencode.plugin.js contains execution keyword: {kw}"


def test_fund_analysis_does_not_import_decision():
    imports = _imports_from_dir(SRC / "skills_runtime" / "fund_analysis")
    assert "src.schemas.decision" not in imports, (
        "fund_analysis must not import Decision schema"
    )


def test_thesis_generation_does_not_import_decision():
    imports = _imports_from_file(
        SRC / "skills_runtime" / "thesis_generation.py"
    )
    assert "src.schemas.decision" not in imports, (
        "thesis_generation must not import Decision schema"
    )


def test_decision_support_allowed_to_import_decision():
    imports = _imports_from_dir(SRC / "skills_runtime" / "decision_support")
    assert "src.schemas.decision" in imports, (
        "decision_support should import Decision schema"
    )


def test_deprecated_src_surfaces_remain_absent():
    for relpath in _DEPRECATED_SRC_MODULES:
        parts = relpath.split(".")
        parts[0] = "src"
        abs_path = ROOT.joinpath(*parts)
        assert not abs_path.exists(), f"Deprecated surface still present: {relpath}"


def test_no_deprecated_surface_imports_in_plugin_core():
    core_dirs = ("skills_runtime", "skillpack", "tools", "schemas", "graph")
    for dirname in core_dirs:
        imports = _imports_from_dir(SRC / dirname)
        for deprecated in _DEPRECATED_SRC_MODULES:
            violations = [i for i in imports if i.startswith(deprecated)]
            assert not violations, (
                f"src/{dirname} imports deprecated {deprecated}: {violations}"
            )
