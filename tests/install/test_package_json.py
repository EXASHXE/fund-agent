"""package.json must exist, name must be fund-agent, version must match VERSION,
repository must point at EXASHXE/fund-agent, and main must point at the plugin entrypoint.

This test guards the OpenCode / npm-shaped install surface. It does NOT
attempt to run `npm install` or `bun install`; it only checks that the
package metadata is coherent and matches the canonical VERSION.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_JSON = ROOT / "package.json"
VERSION_FILE = ROOT / "VERSION"
PYPROJECT = ROOT / "pyproject.toml"


def test_package_json_exists():
    assert PACKAGE_JSON.exists(), "package.json is required for OpenCode/npm install"


def test_package_json_is_valid_json():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_package_name_is_fund_agent():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert data.get("name") == "fund-agent", (
        f"package.json name must be 'fund-agent', got {data.get('name')!r}"
    )


def test_package_version_matches_version_file():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    assert data.get("version") == version, (
        f"package.json version {data.get('version')!r} must match "
        f"VERSION {version!r}"
    )


def test_package_version_matches_pyproject():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data.get("version") == pyproject["project"]["version"], (
        f"package.json version must match pyproject project.version: "
        f"{data.get('version')!r} vs {pyproject['project']['version']!r}"
    )


def test_package_repository_points_at_exashxe():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    repo = data.get("repository", {})
    if isinstance(repo, str):
        url = repo
    else:
        url = repo.get("url", "")
    assert "EXASHXE/fund-agent" in url, (
        f"package.json repository must reference EXASHXE/fund-agent, got {url!r}"
    )


def test_package_main_points_at_plugin_entrypoint():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    main = data.get("main")
    assert main, "package.json must declare a 'main' for the plugin entrypoint"
    assert main.endswith(".js"), (
        f"package.json main must point at a .js file, got {main!r}"
    )
    assert (ROOT / main).exists(), (
        f"package.json main {main!r} does not exist on disk"
    )


def test_package_has_exports_pointing_at_plugin():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    exports = data.get("exports")
    assert exports, "package.json should declare an exports map"
    if isinstance(exports, dict):
        if "." in exports:
            entry = exports["."]
            if isinstance(entry, str):
                assert entry.endswith(".js")
                assert (ROOT / entry).exists()
            elif isinstance(entry, dict):
                # ESM/CJS dual export map
                assert "import" in entry or "default" in entry or "require" in entry


def test_package_has_license_field():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert data.get("license"), "package.json should declare a license"


def test_package_version_is_semver_like():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    version = data.get("version", "")
    assert re.match(r"^\d+\.\d+\.\d+", version), (
        f"package.json version {version!r} is not semver-like"
    )
