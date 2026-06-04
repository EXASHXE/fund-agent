"""Verify docs/host-compatibility.md reflects current v0.4.8-dev reality."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/host-compatibility.md")


def test_doc_exists():
    assert DOC_PATH.exists()


def test_no_stale_v046_no_native_installer():
    """The 'no native installer in v0.4.6' text should be updated."""
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "no native installer in v0.4.6" not in content, (
        "stale v0.4.6 reference in install surface text"
    )


def test_no_stale_in_v046_plugin():
    """The 'from inside the OpenCode plugin in v0.4.6' text should be updated."""
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "in v0.4.6. The plugin is metadata" not in content, (
        "stale v0.4.6 reference in OpenCode plugin description"
    )


def test_no_stale_future_runtime_bridge_design_only():
    """The runtime bridge should not be described as entirely future/design-only."""
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "future runtime bridge is design-only" not in content, (
        "runtime bridge CLI is shipped; should not be described as future design-only"
    )


def test_no_stale_explicitly_not_in_v046():
    """The 'explicitly not in v0.4.6' text should be removed."""
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "explicitly **not** in v0.4.6" not in content, (
        "stale v0.4.6 'not in' reference"
    )


def test_runtime_bridge_described_as_available_cli():
    """The runtime bridge CLI should be described as available."""
    content = DOC_PATH.read_text(encoding="utf-8")
    # Should mention the runtime bridge CLI is available for source-checkout
    assert "runtime bridge CLI" in content or "scripts/run_skill.py" in content, (
        "host-compatibility should mention the runtime bridge CLI"
    )


def test_opencode_plugin_not_calling_python():
    """OpenCode plugin is still metadata/docs only, does not call Python."""
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "not run the Python runtime" in content.replace("*", "") or \
           "does not run the Python runtime" in content.replace("*", ""), (
        "should state OpenCode plugin does not call Python"
    )
