"""Install docs (.opencode/INSTALL.md and docs/install/opencode.md) must exist
and cover the required install topics: prerequisites, install snippet, restart,
verify, version pinning, troubleshooting, and a clear note that other harnesses
have separate install docs.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENCODE_INSTALL_MD = ROOT / ".opencode" / "INSTALL.md"
DOCS_OPENCODE_MD = ROOT / "docs" / "install" / "opencode.md"
DOCS_MANUAL_MD = ROOT / "docs" / "install" / "manual-host.md"
DOCS_CODEX_MD = ROOT / "docs" / "install" / "codex.md"


def test_opencode_install_md_exists():
    assert OPENCODE_INSTALL_MD.exists(), (
        ".opencode/INSTALL.md is required for the project-local OpenCode install"
    )


def test_docs_install_opencode_md_exists():
    assert DOCS_OPENCODE_MD.exists(), (
        "docs/install/opencode.md is required for the documented OpenCode install"
    )


def test_docs_install_manual_host_md_exists():
    assert DOCS_MANUAL_MD.exists(), (
        "docs/install/manual-host.md is required for the manual Python host install"
    )


def test_docs_install_codex_md_exists():
    assert DOCS_CODEX_MD.exists(), (
        "docs/install/codex.md is required for the Codex install path"
    )


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_opencode_install_md_mentions_opencode_json_plugin_array():
    text = _text(OPENCODE_INSTALL_MD)
    assert "opencode.json" in text, (
        ".opencode/INSTALL.md must mention opencode.json"
    )
    assert "plugin" in text, (
        ".opencode/INSTALL.md must mention the plugin install path"
    )


def test_opencode_install_md_mentions_git_backed_install():
    text = _text(OPENCODE_INSTALL_MD)
    assert "git" in text and "clone" in text, (
        ".opencode/INSTALL.md must mention git-backed clone install"
    )


def test_opencode_install_md_mentions_version_pinning():
    text = _text(OPENCODE_INSTALL_MD)
    # v0.4.4 should appear, or at least a version-pinning example with a tag.
    assert "v0.4.4" in text or "tag" in text or "pin" in text, (
        ".opencode/INSTALL.md must mention version pinning"
    )


def test_opencode_install_md_mentions_separate_installs():
    text = _text(OPENCODE_INSTALL_MD)
    # Must clearly state that Claude Code / Codex / manual install are separate.
    for needle in ("claude code", "codex", "manual"):
        assert needle in text, (
            f".opencode/INSTALL.md must mention separate installs for {needle!r}"
        )


def test_opencode_install_md_has_troubleshooting_section():
    text = _text(OPENCODE_INSTALL_MD)
    assert "troubleshoot" in text, (
        ".opencode/INSTALL.md must include a troubleshooting section"
    )


def test_docs_opencode_md_covers_required_topics():
    text = _text(DOCS_OPENCODE_MD)
    required = [
        "opencode",
        "install",
        "plugin",
        "fund-analysis",
        "version",
        "manual",
        "codex",
    ]
    for needle in required:
        assert needle in text, (
            f"docs/install/opencode.md must cover topic {needle!r}"
        )


def test_docs_opencode_md_mentions_opencode_json_plugin_array():
    text = _text(DOCS_OPENCODE_MD)
    assert "opencode.json" in text, (
        "docs/install/opencode.md must reference opencode.json"
    )
    assert "plugin" in text, (
        "docs/install/opencode.md must describe the plugin install path"
    )


def test_docs_opencode_md_mentions_git_backed_install():
    text = _text(DOCS_OPENCODE_MD)
    assert "git" in text and "clone" in text, (
        "docs/install/opencode.md must mention git-backed install"
    )


def test_docs_opencode_md_mentions_version_pinning():
    text = _text(DOCS_OPENCODE_MD)
    assert "v0.4.4" in text or "tag" in text or "pin" in text, (
        "docs/install/opencode.md must mention version pinning"
    )


def test_docs_opencode_md_mentions_separate_installs():
    text = _text(DOCS_OPENCODE_MD)
    for needle in ("claude code", "codex", "manual"):
        assert needle in text, (
            f"docs/install/opencode.md must mention separate installs for {needle!r}"
        )


def test_install_docs_link_to_each_other():
    """All install docs must cross-link so the user can navigate between them."""
    opencode_md = _text(OPENCODE_INSTALL_MD)
    docs_opencode = _text(DOCS_OPENCODE_MD)
    docs_manual = _text(DOCS_MANUAL_MD)
    docs_codex = _text(DOCS_CODEX_MD)

    # The .opencode/INSTALL.md is the canonical install doc; it must
    # point at the manual host and codex docs.
    assert "manual-host" in opencode_md, (
        ".opencode/INSTALL.md should link to manual-host.md"
    )

    # The docs/install/*.md files must cross-reference each other.
    for src, target in [
        (docs_opencode, "manual-host"),
        (docs_opencode, "codex"),
        (docs_manual, "opencode"),
        (docs_manual, "codex"),
        (docs_codex, "opencode"),
        (docs_codex, "manual-host"),
    ]:
        assert target in src, (
            f"docs/install/*.md cross-link missing: expected '{target}' reference"
        )
