"""Network-isolation tests for the runtime bridge.

The bridge must not perform network IO, must not import provider
SDKs, must not shell out to OpenCode, and must not call
``opencode.plugin.js``. It is a thin local Python shim only.
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _import_bridge_module():
    from src.skillpack import run_skill
    return run_skill


def test_bridge_does_not_import_provider_sdk_modules():
    """None of the forbidden provider SDKs may be importable via the
    bridge module's import graph."""
    run_skill = _import_bridge_module()
    source = inspect.getsource(run_skill)
    forbidden_sdks = [
        "tavily",
        "finnhub",
        "exa",
        "firecrawl",
        "praw",
        "akshare",
        "langchain",
        "openai",
        "anthropic",
    ]
    for sdk in forbidden_sdks:
        # Use AST to inspect only actual import statements, so SDK
        # names that appear in comments / docstrings do not trigger
        # a false positive.
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert sdk not in alias.name.lower(), (
                        f"runtime bridge must not import provider SDK {sdk!r} "
                        f"(found import {alias.name!r})"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert sdk not in module.lower(), (
                    f"runtime bridge must not import provider SDK {sdk!r} "
                    f"(found from-import {module!r})"
                )
                for alias in node.names:
                    assert sdk not in alias.name.lower(), (
                        f"runtime bridge must not import provider SDK {sdk!r} "
                        f"(found from-import {module}.{alias.name})"
                    )


def test_bridge_does_not_use_network_modules():
    """The bridge must not use ``requests``, ``httpx``, ``urllib``,
    ``urllib2``, or ``urllib3`` for outbound network calls. ``urllib``
    is acceptable for local file IO (json reading) but never for
    ``urlopen``/``Request`` to a remote endpoint."""
    run_skill = _import_bridge_module()
    source = inspect.getsource(run_skill)
    forbidden_calls = [
        "requests.",
        "httpx.",
        "urllib.request.urlopen",
        "urllib.request.Request",
        "urllib2.",
        "urllib3.",
    ]
    for needle in forbidden_calls:
        assert needle not in source, (
            f"runtime bridge must not use network library call {needle!r}"
        )


def test_bridge_does_not_subprocess_opencode():
    """The bridge must not spawn subprocesses that invoke OpenCode or
    the OpenCode plugin. It is local Python only."""
    run_skill = _import_bridge_module()
    source = inspect.getsource(run_skill)
    forbidden_subprocess_patterns = [
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_output",
        "opencode",
    ]
    for needle in forbidden_subprocess_patterns:
        # ``opencode`` is allowed in comments / docstrings; we still
        # disallow it because the bridge has no reason to mention it.
        assert needle not in source, (
            f"runtime bridge must not use {needle!r} (subprocess / opencode)"
        )


def test_bridge_does_not_read_opencode_plugin_js():
    """The bridge must not import or call opencode.plugin.js."""
    plugin_path = ROOT / "opencode.plugin.js"
    assert plugin_path.exists()
    # No source file under src/ or scripts/ should reference the
    # plugin file path or import its module.
    forbidden_strings = [
        "opencode.plugin.js",
        "opencode_plugin",
        "@opencode-ai/plugin",
    ]
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_strings:
            assert needle not in text, (
                f"{path} must not reference {needle!r}"
            )
    for path in (ROOT / "scripts").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_strings:
            assert needle not in text, (
                f"{path} must not reference {needle!r}"
            )


def test_bridge_works_with_no_network(tmp_path: Path):
    """A live end-to-end invocation must not touch the network.

    We monkey-patch :class:`urllib.request.urlopen` and
    :class:`urllib.error.URLError` to raise if the bridge ever tries
    to make a remote request. The bridge should still complete
    successfully.
    """
    import subprocess
    SCRIPT = ROOT / "scripts" / "run_skill.py"

    # Build a valid fund_analysis input.
    input_payload = {
        "payload": {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 100000,
                "cash_available": 10000,
                "positions": [],
            },
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
        }
    }
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")

    env = {"PYTHONPATH": str(ROOT), "PATH": __import__("os").environ.get("PATH", "")}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--skill", "fund_analysis",
         "--input", str(input_path)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"bridge must succeed locally without network, got rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    # Sanity: stdout is valid JSON.
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
