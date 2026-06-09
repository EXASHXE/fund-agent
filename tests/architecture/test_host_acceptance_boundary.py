"""Host acceptance boundary tests.

Assert:
- src/skillpack/doctor.py does not import provider SDKs/network clients.
- src/skillpack/doctor.py does not import opencode.plugin.js or execute OpenCode.
- src/skillpack/doctor.py does not contain broker/order execution tokens.
- examples/host_subprocess_runner.py does not import src.skills_runtime.
- examples/host_subprocess_runner.py does not import provider SDKs/network clients.
- examples/host_subprocess_runner.py does not contain broker/order execution tokens.
- package.json still does not invoke Python.
- opencode.plugin.js still does not invoke Python.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _get_imports(filepath: str) -> set[str]:
    full = ROOT / filepath
    if not full.exists():
        pytest.skip(f"{filepath} not found")
    source = full.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _read(relpath: str) -> str:
    full = ROOT / relpath
    if not full.exists():
        pytest.skip(f"{relpath} not found")
    return full.read_text(encoding="utf-8")


class TestDoctorBoundary:
    def test_no_provider_sdk_imports(self):
        imports = _get_imports("src/skillpack/doctor.py")
        provider_keywords = [
            "tavily", "finnhub", "exa", "firecrawl", "reddit",
            "akshare", "openai", "anthropic", "langchain",
        ]
        violations = [i for i in imports if any(kw in i.lower() for kw in provider_keywords)]
        assert not violations, f"doctor.py imports provider SDKs: {violations}"

    def test_no_network_client_imports(self):
        imports = _get_imports("src/skillpack/doctor.py")
        network_keywords = ["requests", "httpx", "aiohttp", "urllib3", "socket"]
        violations = [i for i in imports if any(kw in i.lower() for kw in network_keywords)]
        assert not violations, f"doctor.py imports network clients: {violations}"

    def test_no_opencode_plugin_import(self):
        source = _read("src/skillpack/doctor.py")
        assert "opencode.plugin" not in source
        assert "opencode_plugin" not in source

    def test_no_broker_order_tokens(self):
        source = _read("src/skillpack/doctor.py")
        forbidden = ["broker_order", "place_order", "execute_trade", "order_execution"]
        for token in forbidden:
            assert token not in source, f"doctor.py contains {token}"


class TestHostRunnerBoundary:
    def test_no_skills_runtime_import(self):
        imports = _get_imports("examples/host_subprocess_runner.py")
        violations = [i for i in imports if "skills_runtime" in i]
        assert not violations, f"host_subprocess_runner imports skills_runtime: {violations}"

    def test_no_provider_sdk_imports(self):
        imports = _get_imports("examples/host_subprocess_runner.py")
        provider_keywords = [
            "tavily", "finnhub", "exa", "firecrawl", "reddit",
            "akshare", "openai", "anthropic", "langchain",
        ]
        violations = [i for i in imports if any(kw in i.lower() for kw in provider_keywords)]
        assert not violations, f"host_subprocess_runner imports provider SDKs: {violations}"

    def test_no_network_client_imports(self):
        imports = _get_imports("examples/host_subprocess_runner.py")
        network_keywords = ["requests", "httpx", "aiohttp", "urllib3", "socket"]
        violations = [i for i in imports if any(kw in i.lower() for kw in network_keywords)]
        assert not violations, f"host_subprocess_runner imports network clients: {violations}"

    def test_no_broker_order_tokens(self):
        source = _read("examples/host_subprocess_runner.py")
        forbidden = ["broker_order", "place_order", "execute_trade", "order_execution"]
        for token in forbidden:
            assert token not in source, f"host_subprocess_runner contains {token}"


class TestPackageJsonNoPython:
    def test_package_json_does_not_invoke_python(self):
        content = _read("package.json")
        data = json.loads(content)
        scripts = data.get("scripts", {})
        for name, script in scripts.items():
            assert "python" not in script.lower(), f"package.json script {name} invokes python: {script}"


class TestOpenCodePluginNoPython:
    def test_opencode_plugin_does_not_invoke_python(self):
        source = _read("opencode.plugin.js")
        lower = source.lower()
        assert "does not shell out to python" in lower or "does not invoke python" in lower or "does not call python" in lower
        assert "child_process" not in lower
        assert "spawn(" not in source
        assert "exec(" not in source or "async execute(" in source
        assert "execsync(" not in lower
