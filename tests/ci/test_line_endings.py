"""Repository line-ending and executable-bit invariants.

v0.4.5 native skill install hardening:

- scripts/, config files, Markdown docs, and the OpenCode plugin must
  use LF line endings on disk (and stay LF in the working tree).
- .github/workflows/*.yml must use LF line endings.
- opencode.plugin.js must use LF line endings.
- canonical ``skills/<slug>/SKILL.md`` files must use LF line endings.
- ``scripts/check_plugin_gate.sh`` must remain executable.

These tests are intentionally file-level and content-based; they do
NOT depend on git, so they catch a CRLF checkin even if someone bypasses
the renormalize step. A complementary git-level check lives in
``tests/install/test_skill_doc_directory_policy.py`` and
``tests/architecture/test_architecture_boundaries.py``.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _has_crlf(path: Path) -> bool:
    raw = _read_bytes(path)
    if not raw:
        return False
    return b"\r\n" in raw


def test_check_plugin_gate_sh_is_lf():
    """The canonical gate script must use LF line endings. CRLF here
    breaks the ``set -o pipefail`` line on Linux hosts (the user's
    verified-state note from the v0.4.4 extraction)."""
    path = ROOT / "scripts" / "check_plugin_gate.sh"
    assert path.exists(), "scripts/check_plugin_gate.sh must exist"
    assert not _has_crlf(path), (
        f"{path} contains CRLF line endings; scripts/ must be LF"
    )


def test_check_plugin_gate_sh_is_executable():
    """The canonical gate script must remain executable. The
    architecture-boundary test already enforces this; we duplicate the
    check here so a CI failure on line endings does not silently lose
    the executable-bit assertion."""
    path = ROOT / "scripts" / "check_plugin_gate.sh"
    assert path.exists(), "scripts/check_plugin_gate.sh must exist"
    assert os.access(path, os.X_OK), (
        f"{path} must remain executable (chmod +x)"
    )


def test_github_workflows_are_lf():
    """CI workflow files must use LF line endings. CRLF here breaks
    GitHub Actions YAML parsers on Linux runners and is the same
    failure mode as the v0.4.4 zip extraction issue."""
    workflow_dir = ROOT / ".github" / "workflows"
    assert workflow_dir.exists(), ".github/workflows/ must exist"
    for path in sorted(workflow_dir.glob("*.yml")):
        assert not _has_crlf(path), (
            f"{path} contains CRLF line endings; CI workflows must be LF"
        )
    for path in sorted(workflow_dir.glob("*.yaml")):
        assert not _has_crlf(path), (
            f"{path} contains CRLF line endings; CI workflows must be LF"
        )


def test_opencode_plugin_is_lf():
    """The OpenCode plugin must use LF line endings."""
    path = ROOT / "opencode.plugin.js"
    assert path.exists(), "opencode.plugin.js must exist"
    assert not _has_crlf(path), (
        f"{path} contains CRLF line endings; the plugin must be LF"
    )


def test_canonical_skill_docs_are_lf():
    """All canonical ``skills/<slug>/SKILL.md`` files must use LF line
    endings. These are the agent-facing instruction files and are
    shipped verbatim through the OpenCode plugin and the (future)
    native skill sync helper."""
    skills_dir = ROOT / "skills"
    assert skills_dir.exists(), "skills/ must exist"
    skill_docs = sorted(skills_dir.glob("*/SKILL.md"))
    assert skill_docs, "skills/ must contain canonical SKILL.md files"
    for path in skill_docs:
        assert not _has_crlf(path), (
            f"{path} contains CRLF line endings; SKILL.md files must be LF"
        )


def test_canonical_skill_references_are_lf():
    """All ``skills/<slug>/references/*.md`` files must use LF line
    endings. These are the longer policy / example / template docs
    that ship with each canonical skill."""
    skills_dir = ROOT / "skills"
    assert skills_dir.exists(), "skills/ must exist"
    for refs_dir in sorted(skills_dir.glob("*/references")):
        for path in sorted(refs_dir.glob("*.md")):
            assert not _has_crlf(path), (
                f"{path} contains CRLF line endings; reference docs must be LF"
            )


def test_yaml_config_files_are_lf():
    """YAML config files at the repo root (manifest, workflows, etc.)
    must use LF line endings."""
    yaml_candidates = list(ROOT.rglob("*.yml")) + list(ROOT.rglob("*.yaml"))
    for path in yaml_candidates:
        if any(part in {"node_modules", ".git", "__pycache__"} for part in path.parts):
            continue
        assert not _has_crlf(path), (
            f"{path} contains CRLF line endings; YAML must be LF"
        )


def test_gitattributes_exists_and_enforces_lf():
    """``.gitattributes`` must exist and enforce LF for the canonical
    file types. This is a regression guard: the absence of this file
    is what allowed the v0.4.4 zip to slip CRLF into the working tree
    even though the git index was LF."""
    path = ROOT / ".gitattributes"
    assert path.exists(), ".gitattributes must exist"
    text = path.read_text(encoding="utf-8")
    assert "text=auto" in text, ".gitattributes must declare text=auto"
    for ext in ("*.sh", "*.yml", "*.yaml", "*.toml", "*.json", "*.js", "*.py", "*.md"):
        assert re.search(rf"^{re.escape(ext)}\s+text\s+eol=lf", text, re.MULTILINE), (
            f".gitattributes must enforce eol=lf for {ext}"
        )
