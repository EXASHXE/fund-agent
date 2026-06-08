"""Architecture no-regression boundary tests.

Ensures skills_runtime stay provider-free, fund_analysis never produces
Decision objects, examples are clean, and pure tools avoid system time/UUID.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_imports_from_dir(dirpath: str) -> set[str]:
    imports: set[str] = set()
    full_path = os.path.join(PROJECT_ROOT, dirpath)
    if not os.path.isdir(full_path):
        return imports
    for root, dirs, files in os.walk(full_path):
        dirs[:] = [d for d in dirs if not d.startswith("_") and d != "__pycache__"]
        for f in files:
            if not f.endswith(".py"):
                continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding="utf-8") as fh:
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


def _get_source_files(base_dir: str) -> list[str]:
    result: list[str] = []
    full = os.path.join(PROJECT_ROOT, base_dir)
    if not os.path.isdir(full):
        return result
    for root, dirs, files in os.walk(full):
        dirs[:] = [d for d in dirs if not d.startswith("_") and d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                result.append(os.path.join(root, f))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Provider SDK boundaries
# ═══════════════════════════════════════════════════════════════════════════════

PROVIDER_SDKS = {"tavily", "finnhub", "exa", "firecrawl", "reddit", "openai", "anthropic", "langchain", "akshare"}
NETWORK_IMPORTS = {"requests", "urllib3", "urllib.request", "urllib.error", "http.client", "socket", "httpx", "aiohttp"}


def test_skills_runtime_no_provider_sdk_imports():
    imports = _get_imports_from_dir("src/skills_runtime")
    violations = imports & PROVIDER_SDKS
    assert not violations, f"src/skills_runtime imports provider SDKs: {violations}"


def test_skills_runtime_no_network_imports():
    imports = _get_imports_from_dir("src/skills_runtime")
    violations = imports & NETWORK_IMPORTS
    assert not violations, f"src/skills_runtime imports network modules: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# FundAnalysisSkill never produces Decision
# ═══════════════════════════════════════════════════════════════════════════════

def test_fund_analysis_never_produces_decision():
    from src.schemas.skill import SkillInput
    from src.skills_runtime.fund_analysis import FundAnalysisSkill

    payload = {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 100000.0,
            "cash_available": 10000.0,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Test Fund",
                    "current_value": 50000.0,
                    "total_cost": 48000.0,
                    "target_weight": 0.5,
                    "tags": ["equity"],
                },
            ],
        },
    }
    output = FundAnalysisSkill().run(
        SkillInput(
            task_id="test-1",
            step_id="step-1",
            skill_name="fund_analysis",
            payload=payload,
        )
    )
    artifacts = output.artifacts
    assert "decision" not in artifacts, "FundAnalysisSkill must not produce Decision"
    assert "execution_ledger" not in artifacts, "FundAnalysisSkill must not produce ExecutionLedger"


# ═══════════════════════════════════════════════════════════════════════════════
# Examples must not reference ResearchOS or legacy
# ═══════════════════════════════════════════════════════════════════════════════

def test_examples_no_research_os_or_legacy():
    examples_dir = os.path.join(PROJECT_ROOT, "examples")
    violations: list[str] = []
    for f in os.listdir(examples_dir):
        if not f.endswith(".py"):
            continue
        filepath = os.path.join(examples_dir, f)
        content = Path(filepath).read_text(encoding="utf-8")
        if "src.core.research_os" in content:
            violations.append(f"examples/{f}: references src.core.research_os")
        if "import legacy" in content or "from legacy" in content:
            violations.append(f"examples/{f}: imports legacy")
    assert not violations, f"examples reference ResearchOS or legacy: {violations}"


# ═══════════════════════════════════════════════════════════════════════════════
# Pure tools must not use system time or UUID
# ═══════════════════════════════════════════════════════════════════════════════

_SYSTEM_TIME_PATTERNS = (
    "date.today",
    "datetime.now",
    "time.time",
    "uuid4",
    "uuid.uuid4",
    "datetime.utcnow",
)


def test_no_pure_tool_uses_system_time():
    source_files = _get_source_files("src/tools")
    violations: list[str] = []
    for filepath in source_files:
        rel = os.path.relpath(filepath, PROJECT_ROOT)
        if Path(rel).as_posix().startswith(("src/tools/evidence/", "src/tools/adapters/", "src/tools/math/")):
            continue
        content = Path(filepath).read_text(encoding="utf-8")
        for pattern in _SYSTEM_TIME_PATTERNS:
            if pattern in content:
                violations.append(f"{rel}: uses {pattern}")
    assert not violations, f"src/tools uses system time or UUID: {violations}"
