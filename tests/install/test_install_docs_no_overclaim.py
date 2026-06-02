"""Install docs must be honest about current capability.

The OpenCode install is a metadata + doc reader plugin only. It is
NOT a runtime bridge, NOT a data fetcher, and NOT a trading system. These
tests guard the install docs against overclaiming, which would mislead
users and break the host-agnostic architecture constraints.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL_DOCS = [
    ROOT / ".opencode" / "INSTALL.md",
    ROOT / "docs" / "install" / "opencode.md",
    ROOT / "docs" / "install" / "manual-host.md",
    ROOT / "docs" / "install" / "codex.md",
]
RUNTIME_BRIDGE_DOC = ROOT / "docs" / "design" / "runtime-bridge.md"
PLUGIN_FILE = ROOT / "opencode.plugin.js"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_install_docs_do_not_claim_full_runtime_bridge_in_v0_4_4():
    """Install docs must not claim the OpenCode plugin runs the Python
    runtime in the current release."""
    forbidden = [
        "opencode plugin runs fund-agent",
        "opencode plugin invokes fund-analysis",
        "opencode plugin calls fund_analysis",
        "opencode plugin executes decision_support",
        "opencode invokes the python runtime",
        "opencode runs the python runtime",
        "opencode plugin runs the python runtime",
        "opencode plugin calls the python runtime",
    ]
    for path in INSTALL_DOCS:
        if not path.exists():
            continue
        text = _text(path)
        for phrase in forbidden:
            assert phrase not in text, (
                f"{path} overclaims runtime bridge: {phrase!r}"
            )


def test_install_docs_do_not_claim_provider_fetch_in_v0_4_3():
    """Install docs must not claim fund-agent fetches NAV, news, or
    sentiment on its own."""
    forbidden_phrases = [
        "fund-agent fetches nav",
        "fund-agent fetches news",
        "fund-agent fetches sentiment",
        "fund-agent fetches data",
        "fund-agent will fetch",
        "fund-agent automatically fetches",
        "fund-agent handles fetching",
        "fund-agent owns fetching",
        "opencode plugin fetches",
    ]
    for path in INSTALL_DOCS:
        if not path.exists():
            continue
        text = _text(path)
        for phrase in forbidden_phrases:
            assert phrase not in text, (
                f"{path} overclaims data fetching: {phrase!r}"
            )


def test_install_docs_do_not_claim_direct_trading():
    forbidden = [
        "fund-agent places trades",
        "fund-agent will place trades",
        "fund-agent executes trades",
        "fund-agent will execute trades",
        "opencode plugin places trades",
        "opencode plugin executes trades",
    ]
    for path in INSTALL_DOCS:
        if not path.exists():
            continue
        text = _text(path)
        for phrase in forbidden:
            assert phrase not in text, (
                f"{path} overclaims trading capability: {phrase!r}"
            )


def test_install_docs_state_host_owns_data_fetching():
    """Install docs must explicitly say the host owns data fetching."""
    needles = [
        "host owns",
        "host must",
        "host-driven",
        "host injects",
    ]
    for path in INSTALL_DOCS:
        if not path.exists():
            continue
        text = _text(path)
        if path.name in ("manual-host.md",):
            continue  # Manual host install is the one place that
            # delegates fetching to the host by construction.
        assert any(needle in text for needle in needles), (
            f"{path} must state that the host owns data fetching"
        )


def test_install_docs_state_host_owns_orchestration():
    needles = [
        "host owns",
        "host-driven",
        "external host",
        "host agent",
    ]
    for path in INSTALL_DOCS:
        if not path.exists():
            continue
        text = _text(path)
        assert any(needle in text for needle in needles), (
            f"{path} must state that the host owns orchestration"
        )


def test_install_docs_do_not_promote_fund_analyst_as_runtime():
    """The legacy `fund-analyst` material must not be promoted as a
    runtime entrypoint in any install doc."""
    patterns = [
        re.compile(r"fund-analyst.*runtime"),
        re.compile(r"runtime.*fund-analyst"),
        re.compile(r"fund.analyst.*skill"),
        re.compile(r"fund.analyst.*install"),
    ]
    for path in INSTALL_DOCS:
        if not path.exists():
            continue
        text = _text(path)
        for pat in patterns:
            assert not pat.search(text), (
                f"{path} promotes fund-analyst as runtime: matched {pat.pattern}"
            )


def test_opencode_plugin_does_not_claim_full_runtime_bridge():
    """The plugin code itself must not claim to run the Python runtime
    from inside OpenCode. It is a metadata + doc reader only. We allow
    comments that explicitly disclaim the runtime bridge (e.g. "no
    subprocess spawn"), but not any executable code path that would
    actually spawn a sidecar."""
    text = _text(PLUGIN_FILE)
    forbidden = [
        "child_process",
        "fund-agent run_skill",
        "run_skill",
        "fund_agent_run_skill",
        "pythonsubprocess",
        "node-python-bridge",
        "pythonia",
    ]
    for needle in forbidden:
        assert needle not in text, (
            f"opencode.plugin.js must not implement a runtime bridge "
            f"(matched {needle!r})"
        )
    # Also assert that the plugin does not import `child_process`
    # directly: the only Node built-ins it should pull are fs/promises,
    # url, path, module.
    import_block = "\n".join(
        line for line in text.splitlines()
        if line.lstrip().startswith("import ") or "createRequire" in line
    )
    assert "child_process" not in import_block, (
        "opencode.plugin.js must not import child_process"
    )


def test_runtime_bridge_design_doc_exists_and_is_marked_future():
    """The runtime bridge design doc must exist and clearly mark itself
    as partially implemented (thin CLI in v0.4.7-dev) with the deeper
    runtime bridge still future."""
    assert RUNTIME_BRIDGE_DOC.exists(), (
        "docs/design/runtime-bridge.md must document the runtime bridge"
    )
    text = _text(RUNTIME_BRIDGE_DOC)
    assert "design" in text or "future" in text, (
        "runtime-bridge.md must mark itself as design / future"
    )
    # The doc must mention at least one of the recent milestone
    # versions so it is not orphaned from the release narrative.
    has_version_marker = (
        "v0.4.4" in text
        or "v0.4.5" in text
        or "v0.4.6" in text
        or "v0.4.7" in text
    )
    # The doc must say that the deeper runtime bridge is still
    # future. The thin CLI shipped in v0.4.7-dev, but the
    # subprocess-handler and OpenCode-plugin wrapper are future.
    has_future_marker = (
        "future" in text
        or "not implemented" in text
        or "not in v0.4.4" in text
        or "not in v0.4.5" in text
        or "not in v0.4.6" in text
        or "not in v0.4.7" in text
    )
    assert has_version_marker and has_future_marker, (
        "runtime-bridge.md must reference a recent version AND "
        "mark the deeper runtime bridge as future"
    )
