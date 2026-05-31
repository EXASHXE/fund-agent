"""Version consistency tests for v0.3.0-skillpack-rc."""

from __future__ import annotations

from pathlib import Path

import yaml


VERSION_PATH = Path("VERSION")
MANIFEST_PATH = Path("skillpack/fund-agent.skillpack.yaml")
README_PATH = Path("README.md")


def _version() -> str:
    return VERSION_PATH.read_text(encoding="utf-8").strip()


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_version_file_exists():
    assert VERSION_PATH.exists()


def test_manifest_version_matches_version_file():
    assert _manifest()["version"] == _version()


def test_manifest_schema_version_is_skillpack_v1():
    assert _manifest()["schema_version"] == "skillpack.v1"


def test_manifest_package_role_is_agent_plugin():
    assert _manifest()["package_role"] == "agent_plugin"


def test_readme_mentions_rc_version():
    content = README_PATH.read_text(encoding="utf-8")
    # README should mention v0.1.0-skillpack-alpha (legacy pointer) or VERSION link
    assert "v0.1.0-skillpack-alpha" in content or "VERSION" in content
