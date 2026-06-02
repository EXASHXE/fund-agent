"""Cross-doc install-mode consistency tests (v0.4.6
install-packaging-smoke).

These tests guard the install documentation against drift between
``.opencode/INSTALL.md`` and ``docs/install/opencode.md``. The two
docs must consistently describe the three install modes (Mode A,
Mode B, Mode C) and the package contents (Mode A only in the npm
package; Mode B helper is git-clone-only).

The contract:

- Both docs must mention Mode A, Mode B, and Mode C explicitly.
- Both docs must say Mode C is a future runtime bridge (design
  only, not implemented in the current release).
- Both docs must say the OpenCode plugin does not shell out to
  Python.
- Both docs must say the Mode B sync helper is a plain file copy
  (does not edit `opencode.json`, does not start a subprocess).
- Both docs must mention `fund-analysis` as the primary skill
  and the four supporting slugs (`decision-support`,
  `news-research`, `sentiment-analysis`, `thesis-generation`).
- Neither doc may contain a `skills//SKILL.md` placeholder.
- Neither doc may claim the npm package is published.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OPENCODE_INSTALL_MD = ROOT / ".opencode" / "INSTALL.md"
DOCS_OPENCODE_MD = ROOT / "docs" / "install" / "opencode.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lower(path: Path) -> str:
    return _text(path).lower()


PRIMARY = "fund-analysis"
SUPPORTING = (
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
)


@pytest.fixture(params=[OPENCODE_INSTALL_MD, DOCS_OPENCODE_MD])
def install_doc(request) -> Path:
    """Parametrize the two install docs so each consistency test
    runs against both ``.opencode/INSTALL.md`` and
    ``docs/install/opencode.md``."""
    p = request.param
    assert p.exists(), f"install doc missing: {p}"
    return p


# ---------------------------------------------------------------------------
# Mode A / Mode B / Mode C coverage
# ---------------------------------------------------------------------------


def test_install_doc_mentions_mode_a(install_doc: Path):
    text = _lower(install_doc)
    assert "mode a" in text, (
        f"{install_doc} must mention 'Mode A' (plugin metadata + doc-reader)"
    )


def test_install_doc_mentions_mode_b(install_doc: Path):
    text = _lower(install_doc)
    assert "mode b" in text, (
        f"{install_doc} must mention 'Mode B' (native Agent Skills install)"
    )


def test_install_doc_mentions_mode_c(install_doc: Path):
    text = _lower(install_doc)
    assert "mode c" in text, (
        f"{install_doc} must mention 'Mode C' (future runtime bridge)"
    )


def test_install_doc_says_mode_c_is_future_runtime_bridge(install_doc: Path):
    text = _lower(install_doc)
    # Must say Mode C is a future runtime bridge (or equivalent wording).
    assert "runtime bridge" in text, (
        f"{install_doc} must mention 'runtime bridge' in the Mode C context"
    )
    # Must mark Mode C as future / design only.
    assert "future" in text or "design" in text, (
        f"{install_doc} must mark Mode C as future / design only"
    )


# ---------------------------------------------------------------------------
# Plugin does not shell out to Python
# ---------------------------------------------------------------------------


def test_install_doc_says_plugin_does_not_shell_out_to_python(install_doc: Path):
    """Both docs must say the OpenCode plugin does not shell out to
    Python or otherwise start a Python subprocess / embed a Python
    interpreter."""
    text = _lower(install_doc)
    needles = [
        "does not shell out to python",
        "plugin does not shell out",
        "no python",
        "no subprocess",
        "does not start a subprocess",
        "no python interpreter",
        "no sidecar",
        "metadata + doc reader",
        "metadata + doc-reader",
    ]
    assert any(needle in text for needle in needles), (
        f"{install_doc} must say the plugin does not shell out to Python; "
        f"looked for: {needles}"
    )


# ---------------------------------------------------------------------------
# Mode B sync helper is a plain file copy
# ---------------------------------------------------------------------------


def test_install_doc_says_sync_helper_is_plain_file_copy(install_doc: Path):
    """Both docs must say the Mode B sync helper
    (``scripts/install_opencode_skills.py``) is a plain file copy:
    it does not edit ``opencode.json``, does not start a
    subprocess, does not call the network, and does not install
    the Python runtime."""
    text = _lower(install_doc)
    needles = [
        "plain file copy",
        "is a plain file copy",
        "file copy helper",
    ]
    assert any(needle in text for needle in needles), (
        f"{install_doc} must say the Mode B sync helper is a plain file copy"
    )
    # The negative claim: the helper does NOT do certain things.
    anti_patterns = [
        "edit opencode.json",
        "install the python runtime",
        "start a subprocess",
    ]
    negative_needles = [
        "does not edit opencode.json",
        "does not install the python runtime",
        "does not start a subprocess",
        "does not spawn a subprocess",
        "does not start the python runtime",
        "is metadata + markdown only",
    ]
    assert any(needle in text for needle in negative_needles), (
        f"{install_doc} must explicitly disclaim that the sync helper does "
        f"NOT edit opencode.json / install python / start subprocess / call "
        f"network; anti-patterns: {anti_patterns}"
    )


# ---------------------------------------------------------------------------
# Primary + four supporting slugs
# ---------------------------------------------------------------------------


def test_install_doc_mentions_primary_skill(install_doc: Path):
    text = _lower(install_doc)
    assert PRIMARY in text, (
        f"{install_doc} must mention the primary skill '{PRIMARY}'"
    )


@pytest.mark.parametrize("slug", SUPPORTING)
def test_install_doc_mentions_supporting_skill(install_doc: Path, slug: str):
    text = _lower(install_doc)
    assert slug in text, (
        f"{install_doc} must mention supporting skill '{slug}'"
    )


# ---------------------------------------------------------------------------
# No broken placeholders
# ---------------------------------------------------------------------------


def test_install_doc_has_no_skills_double_slash_placeholder(install_doc: Path):
    """Neither doc may contain a broken ``skills//SKILL.md``
    placeholder."""
    text = _text(install_doc)
    assert "skills//SKILL.md" not in text, (
        f"{install_doc} contains broken placeholder 'skills//SKILL.md'"
    )
    assert "skills/<>/SKILL.md" not in text, (
        f"{install_doc} contains broken placeholder 'skills/<>/SKILL.md'"
    )


# ---------------------------------------------------------------------------
# npm package status: declared but not published
# ---------------------------------------------------------------------------


def test_install_doc_does_not_claim_npm_package_is_published(install_doc: Path):
    """Neither doc may claim the npm package is already published.

    The v0.4.6 npm package is **declared but not yet published**.
    The doc must be honest about this."""
    text = _lower(install_doc)
    forbidden_phrases = [
        "the npm package is published",
        "is now published",
        "publish to npm",
        "available on npm",
        "installable from npm",
    ]
    # Allow ``not yet published`` / ``not published`` / ``declarative
    # only`` / ``declared but not yet published`` etc. — these are
    # the honest forms.
    for phrase in forbidden_phrases:
        assert phrase not in text, (
            f"{install_doc} overclaims npm publishing: {phrase!r}"
        )


# ---------------------------------------------------------------------------
# .opencode/INSTALL.md specific: explicit "package contents — npm vs git"
# ---------------------------------------------------------------------------


def test_opencode_install_md_has_package_contents_npm_vs_git_section():
    """.opencode/INSTALL.md must include an explicit
    "Package contents — npm vs git" (or equivalent) section that
    names what the npm package includes and what is git-clone-only."""
    text = _lower(OPENCODE_INSTALL_MD)
    needles = [
        "package contents",
        "npm vs git",
        "npm package contents",
        "what ships in the npm package",
        "what the npm package actually contains",
    ]
    assert any(needle in text for needle in needles), (
        f".opencode/INSTALL.md must include a 'Package contents — npm vs "
        f"git' (or equivalent) section. Looked for: {needles}"
    )


def test_opencode_install_md_says_mode_b_helper_is_git_only():
    """.opencode/INSTALL.md must say the Mode B sync helper
    (``scripts/install_opencode_skills.py``) is **git-clone-only**
    and is NOT shipped via the npm package."""
    text = _lower(OPENCODE_INSTALL_MD)
    assert "git-clone-only" in text or "git clone only" in text, (
        ".opencode/INSTALL.md must say the Mode B helper is git-clone-only"
    )
    assert "scripts/install_opencode_skills.py" in text, (
        ".opencode/INSTALL.md must mention scripts/install_opencode_skills.py"
    )
