"""Version consistency tests: ensure all version-bearing files agree
and that install docs do not contain stale current-version references."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VERSION_PATH = ROOT / "VERSION"
PYPROJECT_PATH = ROOT / "pyproject.toml"
PACKAGE_JSON_PATH = ROOT / "package.json"
MANIFEST_PATH = ROOT / "skillpack" / "fund-agent.skillpack.yaml"

INSTALL_DOC_PATHS = [
    ROOT / "docs" / "install" / "manual-host.md",
    ROOT / "docs" / "install" / "runtime-bridge-cli.md",
    ROOT / "docs" / "install" / "opencode.md",
    ROOT / "docs" / "install" / "codex.md",
    ROOT / ".opencode" / "INSTALL.md",
    ROOT / "docs" / "design" / "runtime-bridge.md",
]


def _version() -> str:
    return VERSION_PATH.read_text(encoding="utf-8").strip()


def _pyproject_version() -> str:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return data["project"]["version"]


def _package_json_version() -> str:
    data = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
    return data["version"]


def _manifest_version() -> str:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data["version"]


def test_version_file_exists():
    assert VERSION_PATH.exists(), "VERSION file is missing"


def test_manifest_version_matches_version_file():
    v = _version()
    mv = _manifest_version()
    assert mv == v, (
        f"skillpack/fund-agent.skillpack.yaml version={mv!r} != VERSION={v!r}"
    )


def test_manifest_schema_version_is_skillpack_v1():
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["schema_version"] == "skillpack.v1"


def test_manifest_package_role_is_agent_plugin():
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["package_role"] == "agent_plugin"


def test_pyproject_version_matches_version_file():
    v = _version()
    pv = _pyproject_version()
    assert pv == v, (
        f"pyproject.toml project.version={pv!r} != VERSION={v!r}"
    )


def test_package_json_version_matches_version_file():
    v = _version()
    pjv = _package_json_version()
    assert pjv == v, (
        f"package.json version={pjv!r} != VERSION={v!r}"
    )


def test_pyproject_version_matches_manifest_version():
    pv = _pyproject_version()
    mv = _manifest_version()
    assert pv == mv, (
        f"pyproject.toml project.version={pv!r} != skillpack manifest version={mv!r}"
    )


def test_package_json_version_matches_manifest_version():
    pjv = _package_json_version()
    mv = _manifest_version()
    assert pjv == mv, (
        f"package.json version={pjv!r} != skillpack manifest version={mv!r}"
    )


def test_install_docs_do_not_contain_stale_current_version_references():
    """Current install docs must not claim the current version is an older
    release. Historical references in CHANGELOG/archive are allowed."""
    v = _version()
    base_version = v.replace("-dev", "")
    stale_patterns = []
    for match_base in ("0.4.6", "0.4.7", "0.4.8"):
        if match_base == base_version:
            continue
        stale_patterns.append(match_base)

    for path in INSTALL_DOC_PATHS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for stale in stale_patterns:
            assert stale not in text, (
                f"{path} contains stale version reference '{stale}' "
                f"(current version is {v})"
            )


def test_runtime_bridge_cli_doc_does_not_advertise_python_310():
    """docs/install/runtime-bridge-cli.md must say Python 3.11+, not 3.10+,
    because pyproject.toml requires Python >=3.11."""
    path = ROOT / "docs" / "install" / "runtime-bridge-cli.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    assert "3.10+" not in text, (
        f"{path} advertises Python 3.10+ but pyproject.toml requires >=3.11"
    )
    assert "3.11+" in text, (
        f"{path} should mention Python 3.11+ as the runtime requirement"
    )
