"""Readability and version-consistency regression tests.

These tests guard against accidental compression of key source files
and version drift across version-bearing files in the repository.

Coverage:
  - Key Python source files have reasonable line counts.
  - Core configuration files are syntactically valid.
  - opencode.plugin.js has no broken skills// references.
  - All version-bearing files agree on the current version.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]

VERSION_BEARING_FILES = [
    ROOT / "VERSION",
    ROOT / "package.json",
    ROOT / "pyproject.toml",
    ROOT / "skillpack" / "fund-agent.skillpack.yaml",
]
"""Files that must agree on the project version."""

KEY_PYTHON_FILES = {
    ROOT / "src" / "skillpack" / "run_skill.py": 100,
    ROOT / "src" / "tools" / "portfolio" / "ledger_snapshot.py": 100,
    ROOT / "src" / "tools" / "research" / "query_plan.py": 40,
}
"""Python source files and their minimum acceptable line counts."""


# ---------------------------------------------------------------------------
# Version consistency
# ---------------------------------------------------------------------------


def test_version_bearing_files_exist():
    """All version-bearing files must exist."""
    missing = [f for f in VERSION_BEARING_FILES if not f.exists()]
    assert not missing, f"Missing version-bearing files: {missing}"


def test_all_version_bearing_files_agree():
    """VERSION, package.json, pyproject.toml, and skillpack YAML
    must all report the same version string."""

    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    # package.json
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == expected, (
        f"package.json version {pkg['version']!r} != VERSION {expected!r}"
    )

    # pyproject.toml
    with (ROOT / "pyproject.toml").open("rb") as f:
        project = tomllib.load(f)
    site_version = project["project"]["version"]
    assert site_version == expected, (
        f"pyproject.toml version {site_version!r} != VERSION {expected!r}"
    )

    # skillpack YAML
    manifest = yaml.safe_load(
        (ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8")
    )
    assert manifest["version"] == expected, (
        f"skillpack YAML version {manifest['version']!r} != VERSION {expected!r}"
    )


def test_opencode_plugin_js_version_matches():
    """opencode.plugin.js PLUGIN_VERSION must equal VERSION."""
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    js_text = (ROOT / "opencode.plugin.js").read_text(encoding="utf-8")
    m = re.search(r'const PLUGIN_VERSION\s*=\s*"([^"]+)"', js_text)
    assert m, "PLUGIN_VERSION not found in opencode.plugin.js"
    assert m.group(1) == expected, (
        f"opencode.plugin.js PLUGIN_VERSION {m.group(1)!r} != VERSION {expected!r}"
    )


# ---------------------------------------------------------------------------
# Key file readability (line-count regressions)
# ---------------------------------------------------------------------------


def test_key_python_files_have_reasonable_line_counts():
    """Key Python source files must have at least the minimum
    acceptable number of lines, to guard against accidental
    compression or truncation."""
    for path, min_lines in KEY_PYTHON_FILES.items():
        assert path.exists(), f"Missing key source file: {path}"
        count = len(path.read_text(encoding="utf-8").splitlines())
        assert count >= min_lines, (
            f"{path} has {count} lines (<{min_lines}) — "
            f"file may be accidentally compressed"
        )


# ---------------------------------------------------------------------------
# Config file parseability
# ---------------------------------------------------------------------------


def test_pyproject_toml_is_parseable():
    """pyproject.toml must be valid TOML."""
    with (ROOT / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    assert "project" in data
    assert "version" in data["project"]


def test_skillpack_yaml_is_parseable():
    """skillpack/fund-agent.skillpack.yaml must be valid YAML
    with expected top-level keys."""
    manifest = yaml.safe_load(
        (ROOT / "skillpack" / "fund-agent.skillpack.yaml").read_text(encoding="utf-8")
    )
    for key in ("name", "version", "schema_version", "skills"):
        assert key in manifest, f"skillpack YAML missing key: {key!r}"


def test_package_json_is_parseable():
    """package.json must be valid JSON."""
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    for key in ("name", "version", "main", "files"):
        assert key in pkg, f"package.json missing key: {key!r}"


def test_opencode_plugin_js_has_no_broken_skill_placeholders():
    """opencode.plugin.js must not contain broken 'skills//SKILL.md'
    or similar double-slash placeholder strings."""
    text = (ROOT / "opencode.plugin.js").read_text(encoding="utf-8")
    assert "skills//SKILL.md" not in text
    assert "skills/<>/SKILL.md" not in text
    assert ".opencode/skills//SKILL.md" not in text
    assert ".agents/skills//SKILL.md" not in text


# ---------------------------------------------------------------------------
# Package Mode A boundary
# ---------------------------------------------------------------------------


def test_package_json_files_is_mode_a_only():
    """package.json 'files' must be Mode A only: plugin, skillpack,
    skills, and install docs. Must not include src/, examples/,
    scripts/, or tests/."""
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    files = pkg.get("files", [])

    required_mode_a = [
        "opencode.plugin.js",
        "skillpack/",
        "skills/",
        "docs/install/",
    ]
    for entry in required_mode_a:
        assert entry in files, f"package.json files missing Mode A entry: {entry!r}"

    forbidden = ["src/", "examples/", "scripts/", "tests/", "legacy/"]
    for entry in files:
        if entry.startswith("!"):
            continue
        assert entry not in forbidden, (
            f"package.json files must not include {entry!r} — Mode A only"
        )
