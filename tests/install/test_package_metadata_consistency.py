"""Package metadata consistency tests.

Verifies package.json, opencode.plugin.js, pyproject.toml, and README metadata
are internally consistent and align with the published boundary contracts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _package_json() -> dict:
    return json.loads((ROOT / "package.json").read_text(encoding="utf-8"))


def _plugin_js_text() -> str:
    return (ROOT / "opencode.plugin.js").read_text(encoding="utf-8")


def test_package_json_runtime_bridge_path():
    pkg = _package_json()
    bridge = pkg.get("fundAgent", {}).get("runtimeBridge", {})
    assert bridge.get("path") == "scripts/run_skill.py"
    assert bridge.get("distribution") == "source-checkout-only"


def test_package_json_runtime_bridge_distribution_readme():
    pkg = _package_json()
    dist = pkg.get("fundAgent", {}).get("runtimeBridge", {}).get("distribution", "")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert dist == "source-checkout-only"
    assert "source-checkout" in readme or "source checkout" in readme


def test_pyproject_requires_python_311():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert ">=3.11" in pyproject


def test_opencode_plugin_does_not_claim_python_execution():
    js_text = _plugin_js_text()
    prohibited = (
        "invoke_python",
        "run_python",
        "spawn_python",
        'child_process',
        "subprocess.spawn",
        "execFile",
        "execSync",
        "execa(",
        "implement deterministic Python",
        "runs the deterministic runtime",
    )
    for phrase in prohibited:
        assert phrase not in js_text, f"opencode.plugin.js claims Python execution: {phrase}"


def test_opencode_plugin_states_metadata_doc_reader_only():
    js_text = _plugin_js_text().lower()
    assert "metadata" in js_text
    assert "doc-reader" in js_text or "doc reader" in js_text


def test_package_json_version_matches_skillpack_manifest():
    import yaml
    pkg = _package_json()
    manifest = yaml.safe_load(
        (ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8")
    )
    assert pkg.get("version") == manifest.get("version")
