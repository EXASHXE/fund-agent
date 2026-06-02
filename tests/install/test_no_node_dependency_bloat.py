"""The package.json must not introduce heavy or surprising runtime dependencies.

fund-agent's OpenCode plugin is supposed to be lightweight. It must not pull
in provider SDKs, framework runtimes, LLM clients, or large utility libraries.
The plugin file itself must not require anything other than Node built-ins and
the optional @opencode-ai/plugin peer dep.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_JSON = ROOT / "package.json"
PLUGIN_FILE = ROOT / "opencode.plugin.js"

HEAVY_PATTERNS = [
    "react",
    "vue",
    "angular",
    "express",
    "koa",
    "fastify",
    "lodash",
    "rxjs",
    "moment",
    "axios",
    "node-fetch",
    "cross-fetch",
    "got",
    "request",
    "openai",
    "@anthropic-ai/sdk",
    "langchain",
    "tavily",
    "finnhub",
    "exa",
    "firecrawl",
    "praw",
    "akshare",
    "pyodide",
    "pythonia",
    "node-python-bridge",
]


def test_package_json_dependencies_are_minimal():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    deps = data.get("dependencies", {})
    assert deps == {}, (
        f"package.json must not declare runtime dependencies, got {deps!r}. "
        f"Add peer dependencies for optional host-provided packages instead."
    )


def test_package_json_dev_dependencies_are_minimal():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    dev_deps = data.get("devDependencies", {})
    # Dev deps are tolerated (e.g. for plugin linting) but must be small
    # and obvious. We allow none by default in v0.4.6 to keep the install
    # surface zero-dep.
    assert dev_deps == {}, (
        f"package.json must not declare devDependencies in v0.4.6, got {dev_deps!r}"
    )


def test_package_json_peer_dependencies_are_optional():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    peers = data.get("peerDependencies", {})
    pmeta = data.get("peerDependenciesMeta", {})
    for name in peers:
        # Any peer dep must be marked optional. We don't want a hard
        # requirement on @opencode-ai/plugin to block npm install for
        # users who just want the metadata.
        assert pmeta.get(name, {}).get("optional") is True, (
            f"peer dependency {name!r} must be marked optional=true in peerDependenciesMeta"
        )


def test_package_json_does_not_list_provider_sdks():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        block = data.get(section, {})
        if isinstance(block, dict):
            for pkg in block:
                lower = pkg.lower()
                for heavy in HEAVY_PATTERNS:
                    assert heavy not in lower, (
                        f"package.json {section} must not list {heavy!r} (got {pkg!r})"
                    )


def test_plugin_does_not_require_non_builtin_node_modules():
    """The plugin file should only import Node built-ins and the optional
    @opencode-ai/plugin peer dep. We tolerate dynamic `require(...)` for
    the optional peer but not static top-level imports of arbitrary npm packages.
    """
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # Top-level import statements
    import_pattern = re.compile(r"^\s*import\s+[^;]+from\s+[\"']([^\"']+)[\"']", re.MULTILINE)
    static_imports = import_pattern.findall(text)

    allowed_static = {
        "node:fs/promises",
        "node:url",
        "node:path",
        "node:module",
        "fs/promises",
        "url",
        "path",
        "module",
        "@opencode-ai/plugin",
    }

    for imp in static_imports:
        assert imp in allowed_static, (
            f"opencode.plugin.js static import {imp!r} is not a Node built-in "
            f"or the allowed optional peer @opencode-ai/plugin"
        )

    # Dynamic require / createRequire is allowed only for the optional peer.
    dynamic_requires = re.findall(r"require\(\s*[\"']([^\"']+)[\"']\s*\)", text)
    for req in dynamic_requires:
        assert req == "@opencode-ai/plugin", (
            f"opencode.plugin.js dynamic require {req!r} is not allowed; "
            f"only the optional @opencode-ai/plugin peer may be required"
        )


def test_package_json_files_field_excludes_heavy_paths():
    """The package.json 'files' field should publish only the install-relevant
    paths, not the whole repo. This keeps the published package tiny."""
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    files = data.get("files", [])
    assert isinstance(files, list) and files, "package.json should declare 'files'"
    forbidden_substrings = [
        "tests/",
        ".github/",
        "scripts/",
        "examples/",
        "data/",
        ".venv/",
        "__pycache__/",
    ]
    for f in files:
        for bad in forbidden_substrings:
            assert not f.startswith(bad), (
                f"package.json 'files' entry {f!r} must not include {bad!r}"
            )
