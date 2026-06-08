"""Architecture checks for the package-based decision_support runtime."""

from __future__ import annotations

import ast
from pathlib import Path

from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
from src.skills_runtime.decision_support import DecisionSupportSkill

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "skills_runtime" / "decision_support"

REQUIRED_FILES = {
    "__init__.py",
    "skill.py",
    "context.py",
    "graph_stage.py",
    "trade_plan_stage.py",
    "action_policy.py",
    "amount_policy.py",
    "decision_stage.py",
    "ledger_stage.py",
    "audit_stage.py",
    "status_stage.py",
}

STAGE_FILES = {
    "skill.py",
    "context.py",
    "graph_stage.py",
    "trade_plan_stage.py",
    "action_policy.py",
    "amount_policy.py",
    "decision_stage.py",
    "ledger_stage.py",
    "audit_stage.py",
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
    "broker",
    "brokerage",
    "celery",
    "daemon",
    "http.server",
    "place_order",
    "execute_trade",
    "order_api",
    "schedule.",
    "socketserver",
    "uvicorn",
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


def test_decision_support_runtime_is_package_with_expected_modules() -> None:
    assert PACKAGE.is_dir()
    assert not (ROOT / "src" / "skills_runtime" / "decision_support.py").exists()
    existing = {path.name for path in PACKAGE.iterdir() if path.is_file() and path.suffix == ".py"}
    assert existing >= REQUIRED_FILES


def test_package_import_exposes_decision_support_skill() -> None:
    from src.skills_runtime.decision_support import DecisionSupportSkill as Imported

    assert Imported is DecisionSupportSkill
    assert DecisionSupportSkill.__name__ == "DecisionSupportSkill"


def test_manifest_decision_support_runtime_resolves_to_package_class() -> None:
    manifest = load_skillpack_manifest()
    spec = next(skill for skill in manifest.skills if skill.name == "decision_support")

    assert spec.runtime == "src.skills_runtime.decision_support:DecisionSupportSkill"
    assert resolve_runtime(spec.runtime) is DecisionSupportSkill


def test_decision_support_stage_modules_do_not_import_provider_sdks_or_network() -> None:
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


def test_decision_support_stage_modules_do_not_call_network_libraries() -> None:
    violations: dict[str, list[str]] = {}
    for path in _stage_paths():
        text = path.read_text(encoding="utf-8")
        matches = sorted(token for token in NETWORK_CALL_TOKENS if token in text)
        if matches:
            violations[path.name] = matches

    assert not violations


def test_decision_support_stage_modules_do_not_import_opencode_plugin() -> None:
    violations: dict[str, list[str]] = {}
    for path in _stage_paths():
        imports = _imports_for(path)
        matches = sorted(name for name in imports if "opencode" in name.lower())
        if matches:
            violations[path.name] = matches

    assert not violations


def test_decision_support_stage_modules_do_not_introduce_daemon_or_server_constructs() -> None:
    violations: dict[str, list[str]] = {}
    for path in _stage_paths():
        text = path.read_text(encoding="utf-8")
        matches = sorted(token for token in DAEMON_SERVER_TOKENS if token in text)
        if matches:
            violations[path.name] = matches

    assert not violations


def test_skill_py_does_not_import_provider_sdks_or_network() -> None:
    imports = _imports_for(PACKAGE / "skill.py")
    forbidden = PROVIDER_SDKS | NETWORK_LIBRARIES
    violations = sorted(
        name for name in imports
        if any(name == item or name.startswith(f"{item}.") for item in forbidden)
    )
    assert not violations


def test_skill_py_does_not_import_fund_analysis() -> None:
    imports = _imports_for(PACKAGE / "skill.py")
    assert "src.skills_runtime.fund_analysis" not in imports
    assert "fund_analysis" not in imports
