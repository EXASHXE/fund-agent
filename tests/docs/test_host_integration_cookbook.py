"""String checks for host integration cookbook docs."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COOKBOOK_DIR = ROOT / "docs" / "host-integrations"

EXPECTED_DOCS = [
    "README.md",
    "generic-subprocess-host.md",
    "opencode.md",
    "codex.md",
    "claude-code.md",
    "hermes.md",
    "openclaw.md",
]

HOST_DOCS = [COOKBOOK_DIR / name for name in EXPECTED_DOCS]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lower(path: Path) -> str:
    return _text(path).lower()


def test_host_integration_cookbook_files_exist() -> None:
    assert COOKBOOK_DIR.exists()
    for name in EXPECTED_DOCS:
        assert (COOKBOOK_DIR / name).exists(), f"missing cookbook doc: {name}"


def test_cookbook_readme_links_to_all_host_docs() -> None:
    text = _text(COOKBOOK_DIR / "README.md")
    for name in EXPECTED_DOCS:
        if name == "README.md":
            continue
        assert f"./{name}" in text


def test_cookbook_readme_references_core_contracts_and_installs() -> None:
    text = _text(COOKBOOK_DIR / "README.md")
    required = [
        "skillpack/fund-agent.skillpack.yaml",
        "docs/contracts/fund-analysis-input-contract.v1.md",
        "docs/contracts/fund-analysis-artifacts.v1.md",
        "docs/contracts/report-output-contract.v1.md",
        "docs/install/runtime-bridge-cli.md",
    ]
    for item in required:
        assert item in text


def test_generic_subprocess_doc_contains_runtime_bridge_commands() -> None:
    text = _text(COOKBOOK_DIR / "generic-subprocess-host.md")
    for needle in (
        "--list-skills",
        "--explain-input",
        "--validate-input",
        "--output-schema",
        "--emit-report markdown",
    ):
        assert needle in text


def test_opencode_doc_preserves_plugin_boundary() -> None:
    text = _lower(COOKBOOK_DIR / "opencode.md")
    assert "opencode plugin must not call python" in text
    assert "npm/plugin install alone does not provide python runtime execution" in text
    assert "plugin itself must not invoke python" in text


def test_all_host_docs_state_host_owns_data_fetching_and_provider_sdks() -> None:
    for path in HOST_DOCS:
        text = _lower(path)
        assert "host owns data fetching" in text, path
        assert "provider sdk" in text, path


def test_all_host_docs_state_formal_decisions_require_decision_support() -> None:
    for path in HOST_DOCS:
        text = _lower(path)
        assert "decision_support" in text, path
        assert "formal" in text and "decision" in text, path


def test_no_host_doc_claims_fund_agent_fetches_provider_data() -> None:
    forbidden = [
        "fund-agent fetches nav",
        "fund-agent fetches holdings",
        "fund-agent fetches benchmark",
        "fund-agent fetches peer",
        "fund-agent fetches news",
        "fund-agent fetches sentiment",
        "fund-agent fetches market data",
    ]
    for path in HOST_DOCS:
        text = _lower(path)
        for phrase in forbidden:
            assert phrase not in text, f"{path} overclaims: {phrase}"


def test_no_host_doc_exposes_archived_persona_as_installable() -> None:
    forbidden = [
        "install docs/archive/fund-analyst",
        "installable docs/archive/fund-analyst",
        "restore skills/fund-analyst",
        "create skills/fund-analyst",
    ]
    for path in HOST_DOCS:
        text = _lower(path)
        for phrase in forbidden:
            assert phrase not in text, f"{path} exposes archived persona: {phrase}"


def test_no_host_doc_claims_daemon_or_server_runtime() -> None:
    forbidden = [
        "fund-agent is a daemon",
        "fund-agent is a server",
        "fund-agent runs as a daemon",
        "fund-agent runs as a server",
        "start the fund-agent daemon",
        "start the fund-agent server",
    ]
    for path in HOST_DOCS:
        text = _lower(path)
        for phrase in forbidden:
            assert phrase not in text, f"{path} claims daemon/server runtime: {phrase}"
