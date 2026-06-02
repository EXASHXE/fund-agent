"""Doc consistency tests for the runtime bridge CLI.

The runtime bridge CLI (``scripts/run_skill.py`` and
``src/skillpack/run_skill.py``) is a Python shim. It is
git-clone-only; the v0.4.7-dev npm package remains Mode A
(plugin + skill docs) only and does NOT include the runtime
bridge.

These tests guard the install docs against drift on this
boundary. They verify that:

- The runtime bridge CLI doc explicitly says the bridge is
  git-clone-only / Python environment required.
- The runtime bridge CLI doc does NOT imply it ships via
  ``npm install fund-agent``.
- The install matrix in ``.opencode/INSTALL.md`` /
  ``docs/install/opencode.md`` acknowledges the runtime
  bridge is a separate surface.
- The CLI doc lists the public bridge error codes so hosts
  can branch on them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_BRIDGE_DOC = ROOT / "docs" / "install" / "runtime-bridge-cli.md"
OPENCODE_INSTALL_MD = ROOT / ".opencode" / "INSTALL.md"
DOCS_OPENCODE_MD = ROOT / "docs" / "install" / "opencode.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lower(path: Path) -> str:
    return _text(path).lower()


@pytest.fixture
def runtime_bridge_doc() -> Path:
    assert RUNTIME_BRIDGE_DOC.exists(), (
        f"runtime bridge doc missing: {RUNTIME_BRIDGE_DOC}"
    )
    return RUNTIME_BRIDGE_DOC


def test_runtime_bridge_doc_exists_and_is_versioned() -> None:
    """The runtime bridge CLI doc must exist and be tagged as
    shipped-in-v0.4.7-dev (so hosts know when it landed)."""
    assert RUNTIME_BRIDGE_DOC.exists()
    text = _lower(RUNTIME_BRIDGE_DOC)
    assert "v0.4.7-dev" in text, (
        "runtime bridge doc must be tagged with v0.4.7-dev"
    )


def test_runtime_bridge_doc_says_source_checkout_required(runtime_bridge_doc: Path) -> None:
    """The doc must say the runtime bridge requires a Python source
    checkout (i.e. git clone, pip install -e ., or equivalent) and
    is not shipped via the npm plugin install."""
    text = _lower(runtime_bridge_doc)
    needles = [
        "source checkout",
        "git clone",
        "python environment",
        "pip install",
    ]
    assert any(needle in text for needle in needles), (
        f"{runtime_bridge_doc} must say the runtime bridge is "
        f"git-clone / source-checkout; looked for: {needles}"
    )


def test_runtime_bridge_doc_does_not_imply_npm_plugin_install_includes_bridge(
    runtime_bridge_doc: Path,
) -> None:
    """The doc must NOT claim that installing the npm OpenCode
    plugin gives you the runtime bridge CLI. The plugin and the
    bridge are independent surfaces; the plugin still does not
    call Python."""
    text = _lower(runtime_bridge_doc)
    forbidden_phrases = [
        "the opencode plugin ships the runtime bridge",
        "npm install includes the runtime bridge",
        "the plugin provides scripts/run_skill.py",
        "opencode plugin runs scripts/run_skill.py",
        "plugin spawns scripts/run_skill.py",
        "plugin calls scripts/run_skill.py",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in text, (
            f"{runtime_bridge_doc} overclaims: {phrase!r}"
        )


def test_runtime_bridge_doc_lists_bridge_error_codes(runtime_bridge_doc: Path) -> None:
    """Hosts need to branch on the bridge's error codes. The doc
    must enumerate them in a table or list."""
    text = _lower(runtime_bridge_doc)
    required_codes = [
        "invalid_input",
        "unknown_skill",
        "runtime_load_failed",
        "skill_run_failed",
        "json_serialization_failed",
    ]
    for code in required_codes:
        assert code in text, (
            f"{runtime_bridge_doc} must document bridge error code {code!r}"
        )


def test_runtime_bridge_doc_explains_mcp_boundary(runtime_bridge_doc: Path) -> None:
    """The MCP boundary is a critical contract: the bridge never
    imports provider SDKs, never calls the network, never spawns
    subprocesses for MCP handlers. The doc must say so."""
    text = _lower(runtime_bridge_doc)
    needles = [
        "never",
        "provider sdk",
        "network",
        "subprocess",
    ]
    for needle in needles:
        assert needle in text, (
            f"{runtime_bridge_doc} must explain MCP boundary: {needle!r}"
        )


def test_opencode_install_docs_acknowledge_runtime_bridge_separate_surface() -> None:
    """Both ``.opencode/INSTALL.md`` and ``docs/install/opencode.md``
    must be honest that the runtime bridge is a separate surface
    not provided by the OpenCode plugin (it requires a Python
    source checkout)."""
    for doc in (OPENCODE_INSTALL_MD, DOCS_OPENCODE_MD):
        assert doc.exists(), f"install doc missing: {doc}"
        text = _lower(doc)
        # The doc must mention the runtime bridge as a separate
        # surface (or the docs/install/runtime-bridge-cli.md link).
        needles = [
            "runtime bridge",
            "runtime-bridge-cli",
            "docs/install/runtime-bridge-cli",
        ]
        assert any(needle in text for needle in needles), (
            f"{doc} must reference the runtime bridge as a separate "
            f"surface; looked for: {needles}"
        )
        # It must NOT say the OpenCode plugin invokes the bridge.
        forbidden_phrases = [
            "plugin invokes scripts/run_skill.py",
            "opencode plugin runs the bridge",
            "plugin shells out to the bridge",
            "plugin spawns the bridge",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in text, (
                f"{doc} overclaims plugin↔bridge coupling: {phrase!r}"
            )
