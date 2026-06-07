"""Architecture checks for the package-based fund_analysis runtime."""

from __future__ import annotations

import ast
from pathlib import Path

from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.skills_runtime.fund_analysis import FundAnalysisSkill

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "skills_runtime" / "fund_analysis"

REQUIRED_FILES = {
    "__init__.py",
    "skill.py",
    "context.py",
    "input_stage.py",
    "ledger_stage.py",
    "metrics_stage.py",
    "optional_data_stage.py",
    "report_stage.py",
    "evidence_stage.py",
    "status_stage.py",
}

STAGE_FILES = {
    "skill.py",
    "context.py",
    "input_stage.py",
    "ledger_stage.py",
    "metrics_stage.py",
    "optional_data_stage.py",
    "report_stage.py",
    "evidence_stage.py",
    "status_stage.py",
}

PROVIDER_SDKS = {
    "akshare",
    "anthropic",
    "exa",
    "finnhub",
    "firecrawl",
    "langchain",
    "openai",
    "reddit",
    "tavily",
}

NETWORK_LIBRARIES = {
    "aiohttp",
    "httpx",
    "requests",
    "socket",
    "urllib",
    "urllib3",
    "websocket",
}

NETWORK_CALL_TOKENS = {
    "requests.",
    "httpx.",
    "aiohttp.",
    "urllib.request",
    "urlopen(",
    "socket.",
    "create_connection(",
}

DAEMON_SERVER_TOKENS = {
    "APScheduler",
    "FastAPI",
    "Flask",
    "LangGraph",
    "celery",
    "daemon",
    "http.server",
    "schedule.",
    "socketserver",
    "uvicorn",
}

SKILL_LOW_LEVEL_TOOL_IMPORTS = {
    "src.tools.fund.metrics",
    "src.tools.portfolio.analysis",
    "src.tools.portfolio.transaction",
    "src.tools.research.query_plan",
}


def _imports_for(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _stage_paths() -> list[Path]:
    return [PACKAGE / filename for filename in sorted(STAGE_FILES)]


def test_fund_analysis_runtime_is_package_with_expected_modules() -> None:
    assert PACKAGE.is_dir()
    assert not (ROOT / "src" / "skills_runtime" / "fund_analysis.py").exists()
    assert {path.name for path in PACKAGE.iterdir() if path.is_file()} >= REQUIRED_FILES


def test_package_import_exposes_fund_analysis_skill() -> None:
    from src.skills_runtime.fund_analysis import FundAnalysisSkill as Imported

    assert Imported is FundAnalysisSkill
    assert FundAnalysisSkill.__name__ == "FundAnalysisSkill"


def test_manifest_fund_analysis_runtime_resolves_to_package_class() -> None:
    manifest = load_skillpack_manifest()
    spec = next(skill for skill in manifest.skills if skill.name == "fund_analysis")

    assert spec.runtime == "src.skills_runtime.fund_analysis:FundAnalysisSkill"
    assert resolve_runtime(spec.runtime) is FundAnalysisSkill


def test_fund_analysis_stage_modules_do_not_import_provider_sdks_or_network() -> None:
    forbidden = PROVIDER_SDKS | NETWORK_LIBRARIES
    violations: dict[str, list[str]] = {}
    for path in _stage_paths():
        imports = _imports_for(path)
        matches = sorted(
            name
            for name in imports
            if any(name == item or name.startswith(f"{item}.") for item in forbidden)
        )
        if matches:
            violations[path.name] = matches

    assert not violations


def test_fund_analysis_stage_modules_do_not_call_network_libraries() -> None:
    violations: dict[str, list[str]] = {}
    for path in _stage_paths():
        text = path.read_text(encoding="utf-8")
        matches = sorted(token for token in NETWORK_CALL_TOKENS if token in text)
        if matches:
            violations[path.name] = matches

    assert not violations


def test_fund_analysis_stage_modules_do_not_import_opencode_plugin() -> None:
    violations: dict[str, list[str]] = {}
    for path in _stage_paths():
        imports = _imports_for(path)
        matches = sorted(name for name in imports if "opencode" in name.lower())
        if matches:
            violations[path.name] = matches

    assert not violations


def test_fund_analysis_stage_modules_do_not_introduce_daemon_or_server_constructs() -> None:
    violations: dict[str, list[str]] = {}
    for path in _stage_paths():
        text = path.read_text(encoding="utf-8")
        matches = sorted(token for token in DAEMON_SERVER_TOKENS if token in text)
        if matches:
            violations[path.name] = matches

    assert not violations


def test_fund_analysis_skill_orchestrator_does_not_import_low_level_tools() -> None:
    imports = _imports_for(PACKAGE / "skill.py")
    violations = sorted(imports & SKILL_LOW_LEVEL_TOOL_IMPORTS)

    assert not violations
