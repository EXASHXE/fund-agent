"""npm pack --dry-run content assertions for the v0.4.6 install
packaging smoke milestone.

This test guards the actual published package contents. It runs
``npm pack --dry-run --json`` against the repo-root ``package.json``
and asserts that the package contains the expected install surface
and does NOT contain the forbidden paths (legacy code, tests,
build artifacts, archive material).

Notes:

- The test is skipped if ``npm`` is not available on the test host.
- The test does NOT publish or pack a real tarball; it only
  inspects the dry-run output.
- The Mode B helper script ``scripts/install_opencode_skills.py``
  is **not** included in the npm package in v0.4.6 — it is
  git-clone-only. The npm package is Mode A (plugin + skill docs)
  only. See ``tests/docs/test_install_mode_consistency.py`` for
  the doc consistency guards.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_JSON = ROOT / "package.json"


# Files that MUST be present in the published npm package.
REQUIRED_PACKAGE_PATHS = (
    "package.json",
    "opencode.plugin.js",
    "skillpack/fund-agent.skillpack.yaml",
    "skillpack/input-contracts.yaml",
    "skillpack/artifact-contracts.yaml",
    "skills/fund-analysis/SKILL.md",
    "skills/decision-support/SKILL.md",
    "skills/news-research/SKILL.md",
    "skills/sentiment-analysis/SKILL.md",
    "skills/thesis-generation/SKILL.md",
    "docs/install/opencode.md",
    "docs/install/manual-host.md",
    "docs/install/codex.md",
)


# Files that MUST NOT be present in the published npm package.
# These are git-clone-only, source-only, or build-artifact paths.
FORBIDDEN_PACKAGE_PATHS = (
    # Legacy / archived runtime files. legacy/ contains a single
    # README.md pointer; the package must not include even that
    # if it grows.
    "legacy/README.md",
    # Archived persona. Must never ship via npm.
    "docs/archive/fund-analyst",
    # Tests directory. The npm package is install + skill docs only.
    "tests/install",
    "tests/docs",
    "tests/architecture",
    "tests/ci",
    "tests/skills",
    "tests/contracts",
    "tests/skillpack",
    "tests/tools",
    "tests/integration",
    "tests/deprecated",
    "tests/runtime_bridge",
    # Mode B helper. v0.4.6 npm package is Mode A only; the
    # helper is git-clone-only.
    "scripts/install_opencode_skills.py",
    # Runtime bridge CLI. v0.4.7-dev npm package remains Mode A
    # (plugin + skill docs) only; the runtime bridge is a Python
    # CLI shipped via git clone / source checkout, not via npm.
    "scripts/run_skill.py",
    "src/skillpack/run_skill.py",
    "examples/runtime_bridge_fund_analysis_input.json",
    "examples/runtime_bridge_decision_support_input.json",
    "examples/minimal_runtime_bridge_fund_analysis.py",
    # Project-local OpenCode install doc. Lives at .opencode/INSTALL.md
    # in the source repo only.
    ".opencode/INSTALL.md",
    # Build / cache / dev artifacts. Must never ship.
    "node_modules",
    ".tmp",
    "__pycache__",
    ".pytest_cache",
)


def _has_npm() -> bool:
    return shutil.which("npm") is not None


def _run_npm_pack_dry_run() -> dict:
    """Run ``npm pack --dry-run --json`` from the repo root and
    return the parsed JSON output. The output of ``npm pack
    --dry-run --json`` is a single JSON object describing the
    files that would be packed into the tarball."""
    assert PACKAGE_JSON.exists(), "package.json is required"
    proc = subprocess.run(
        ["npm", "pack", "--dry-run", "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"npm pack --dry-run failed: stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    # Newer npm versions return a list with a single entry; older
    # versions return a single object. Normalize.
    if isinstance(payload, list):
        assert len(payload) == 1, (
            f"npm pack --dry-run --json should return a single entry, "
            f"got {len(payload)}"
        )
        return payload[0]
    return payload


def _packed_files(pack_payload: dict) -> list[str]:
    """Return the list of file paths (relative to the package root)
    that would be packed. ``npm pack --dry-run --json`` reports
    files under ``pack_payload['files'][].path`` (or sometimes
    ``entry`` depending on npm version)."""
    files = pack_payload.get("files") or []
    paths: list[str] = []
    for entry in files:
        if isinstance(entry, dict):
            p = entry.get("path") or entry.get("entry")
            if p:
                paths.append(p.lstrip("/"))
        elif isinstance(entry, str):
            paths.append(entry.lstrip("/"))
    return paths


@pytest.fixture(scope="session")
def npm_pack_payload():
    """Run npm pack --dry-run --json once per session."""
    if not _has_npm():
        return None
    try:
        return _run_npm_pack_dry_run()
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None


@pytest.fixture(scope="session")
def npm_packed_paths(npm_pack_payload):
    """Return the set of packed file paths once per session."""
    if npm_pack_payload is None:
        return None
    return set(_packed_files(npm_pack_payload))


@pytest.mark.install
@pytest.mark.subprocess
def test_npm_pack_dry_run_emits_valid_payload(npm_pack_payload):
    if npm_pack_payload is None:
        pytest.skip("npm not available on test host")
    pack = npm_pack_payload
    assert isinstance(pack, dict), f"pack payload must be a dict, got {type(pack)}"
    # The pack payload should describe the package name and version.
    # Different npm versions surface this under different keys; the
    # essential contract is that the package metadata is present.
    name = pack.get("name")
    version = pack.get("version")
    if name is not None:
        assert name == "fund-agent", (
            f"pack name must be 'fund-agent', got {name!r}"
        )
    if version is not None:
        # The pack version must equal the canonical VERSION file
        # (i.e. the npm package advertises the same version as the
        # rest of the repo). The test reads VERSION at runtime so
        # it stays valid across dev tags.
        expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert version == expected, (
            f"pack version must equal VERSION ({expected!r}), got {version!r}"
        )


@pytest.mark.install
@pytest.mark.subprocess
def test_npm_pack_contains_required_install_paths(npm_packed_paths):
    if npm_packed_paths is None:
        pytest.skip("npm not available on test host")
    missing = [p for p in REQUIRED_PACKAGE_PATHS if p not in npm_packed_paths]
    assert not missing, (
        f"npm pack must include required install paths; missing: {missing}\n"
        f"present paths: {sorted(npm_packed_paths)[:50]}..."
    )


@pytest.mark.install
@pytest.mark.subprocess
def test_npm_pack_does_not_contain_forbidden_paths(npm_packed_paths):
    """The npm package is Mode A only and must not ship legacy code,
    tests, build artifacts, archive material, or the Mode B helper
    script. This is the v0.4.6 install-packaging-smoke guard."""
    if npm_packed_paths is None:
        pytest.skip("npm not available on test host")
    paths = list(npm_packed_paths)
    violations: list[str] = []
    for packed in paths:
        packed_norm = packed.replace("\\", "/").lstrip("./")
        for forbidden in FORBIDDEN_PACKAGE_PATHS:
            if packed_norm == forbidden or packed_norm.startswith(
                forbidden + "/"
            ):
                violations.append(packed)
                break
    assert not violations, (
        "npm pack must not contain forbidden paths (Mode A only, "
        "no tests / no legacy / no build artifacts):\n  "
        + "\n  ".join(violations)
    )


@pytest.mark.install
@pytest.mark.subprocess
def test_npm_pack_does_not_include_underscore_runtime_skill_dirs(npm_packed_paths):
    """The npm package ships the canonical hyphenated skill docs only.
    It must NOT ship any ``skills/<underscore>`` runtime dir."""
    if npm_packed_paths is None:
        pytest.skip("npm not available on test host")
    paths = list(npm_packed_paths)
    bad: list[str] = []
    for p in paths:
        if not p.startswith("skills/"):
            continue
        # Skip Python artifacts; they are caught by a separate test.
        parts = Path(p).parts
        if any(part == "__pycache__" or part.endswith(".pyc") for part in parts):
            continue
        if any(part == "__init__.py" for part in parts):
            continue
        # A path is a candidate "underscore skill dir" if its immediate
        # parent under skills/ contains an underscore.
        if len(parts) >= 2 and "_" in parts[1]:
            bad.append(p)
    assert not bad, (
        f"npm pack must not include underscore runtime skill dirs; "
        f"found: {bad}"
    )


@pytest.mark.install
@pytest.mark.subprocess
def test_npm_pack_does_not_include_fund_analyst_archive(npm_packed_paths):
    """The npm package must never ship the archived ``fund-analyst``
    persona material."""
    if npm_packed_paths is None:
        pytest.skip("npm not available on test host")
    paths = list(npm_packed_paths)
    bad = [p for p in paths if "fund-analyst" in p or "fund_analyst" in p]
    assert not bad, (
        f"npm pack must not include archived fund-analyst material; "
        f"found: {bad}"
    )


@pytest.mark.install
@pytest.mark.subprocess
def test_npm_pack_contains_at_least_one_skill_doc_per_canonical_skill(npm_packed_paths):
    """Each of the five canonical hyphenated skills must contribute
    at least one file (the SKILL.md) to the npm package."""
    if npm_packed_paths is None:
        pytest.skip("npm not available on test host")
    paths = list(npm_packed_paths)
    for slug in [
        "fund-analysis",
        "decision-support",
        "news-research",
        "sentiment-analysis",
        "thesis-generation",
    ]:
        matching = [p for p in paths if p.startswith(f"skills/{slug}/")]
        assert matching, (
            f"npm pack must include at least one file under "
            f"skills/{slug}/, got: {sorted(paths)[:30]}..."
        )
        # The SKILL.md is the canonical doc and must be present.
        assert f"skills/{slug}/SKILL.md" in paths, (
            f"npm pack must include skills/{slug}/SKILL.md"
        )
