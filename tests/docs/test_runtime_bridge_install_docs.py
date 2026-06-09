"""Runtime bridge install docs tests.

Verifies that documentation accurately describes the runtime bridge
install surface, supported modes, and boundary rules.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

DOCS_TO_CHECK = [
    ROOT / "docs" / "START_HERE.md",
    ROOT / "docs" / "install" / "runtime-bridge-cli.md",
    ROOT / "docs" / "install" / "manual-host.md",
]

DOCS_FOR_CLI_FLAGS = [
    ROOT / "docs" / "START_HERE.md",
    ROOT / "docs" / "install" / "runtime-bridge-cli.md",
    ROOT / "docs" / "install" / "manual-host.md",
]

DOCS_FOR_BOUNDARY_RULES = [
    ROOT / "docs" / "START_HERE.md",
    ROOT / "docs" / "install" / "runtime-bridge-cli.md",
    ROOT / "docs" / "install" / "manual-host.md",
    ROOT / "README.md",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _text_lower(path: Path) -> str:
    return _text(path).lower()


class TestRuntimeBridgeDocsExist:
    def test_start_here_exists(self):
        assert (ROOT / "docs" / "START_HERE.md").exists()

    def test_runtime_bridge_cli_doc_exists(self):
        assert (ROOT / "docs" / "install" / "runtime-bridge-cli.md").exists()

    def test_manual_host_doc_exists(self):
        assert (ROOT / "docs" / "install" / "manual-host.md").exists()


class TestRuntimeBridgeDocsMentionSourceCheckout:
    @pytest.mark.parametrize("doc_path", DOCS_FOR_CLI_FLAGS)
    def test_mentions_scripts_run_skill(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text(doc_path)
        assert "scripts/run_skill.py" in text or "run_skill.py" in text, (
            f"{doc_path.name} must mention scripts/run_skill.py"
        )

    @pytest.mark.parametrize("doc_path", DOCS_FOR_CLI_FLAGS)
    def test_mentions_list_skills(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "--list-skills" in text, (
            f"{doc_path.name} must mention --list-skills"
        )

    @pytest.mark.parametrize("doc_path", DOCS_FOR_CLI_FLAGS)
    def test_mentions_explain_input(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "--explain-input" in text, (
            f"{doc_path.name} must mention --explain-input"
        )

    @pytest.mark.parametrize("doc_path", DOCS_FOR_CLI_FLAGS)
    def test_mentions_validate_input(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "--validate-input" in text, (
            f"{doc_path.name} must mention --validate-input"
        )

    @pytest.mark.parametrize("doc_path", DOCS_FOR_CLI_FLAGS)
    def test_mentions_emit_report_markdown(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "--emit-report" in text and "markdown" in text, (
            f"{doc_path.name} must mention --emit-report markdown"
        )


class TestRuntimeBridgeDocsMentionSkills:
    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_decision_support(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "decision_support" in text or "decision-support" in text, (
            f"{doc_path.name} must mention decision_support"
        )

    @pytest.mark.parametrize("doc_path", DOCS_TO_CHECK)
    def test_mentions_thesis_generation(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        assert "thesis_generation" in text or "thesis-generation" in text, (
            f"{doc_path.name} must mention thesis_generation"
        )


class TestRuntimeBridgeDocsMentionBoundaryRules:
    @pytest.mark.parametrize("doc_path", DOCS_FOR_BOUNDARY_RULES)
    def test_mentions_host_owns_data_fetching(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        needles = ["host owns", "host-driven", "host injects", "external host"]
        assert any(n in text for n in needles), (
            f"{doc_path.name} must state that the host owns data fetching/provider SDKs"
        )

    def test_start_here_opencode_plugin_metadata_only(self):
        text = _text_lower(ROOT / "docs" / "START_HERE.md")
        assert "metadata" in text and "doc" in text, (
            "docs/START_HERE.md must describe OpenCode plugin as metadata + doc-reader"
        )

    def test_runtime_bridge_cli_opencode_plugin_metadata_only(self):
        text = _text_lower(ROOT / "docs" / "install" / "runtime-bridge-cli.md")
        assert "metadata" in text and "doc" in text, (
            "docs/install/runtime-bridge-cli.md must describe OpenCode plugin as metadata + doc-reader"
        )

    @pytest.mark.parametrize("doc_path", DOCS_FOR_BOUNDARY_RULES)
    def test_no_broker_order_execution_claim(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        forbidden = [
            "fund-agent places trades",
            "fund-agent executes trades",
            "fund-agent will place trades",
        ]
        for phrase in forbidden:
            assert phrase not in text, (
                f"{doc_path.name} must not claim broker/order execution: {phrase!r}"
            )

    @pytest.mark.parametrize("doc_path", DOCS_FOR_BOUNDARY_RULES)
    def test_no_provider_sdks_bundled_claim(self, doc_path):
        if not doc_path.exists():
            pytest.skip(f"{doc_path} does not exist")
        text = _text_lower(doc_path)
        forbidden = [
            "fund-agent bundles provider sdks",
            "fund-agent includes tavily",
            "fund-agent includes finnhub",
        ]
        for phrase in forbidden:
            assert phrase not in text, (
                f"{doc_path.name} must not claim provider SDKs are bundled: {phrase!r}"
            )


class TestRuntimeBridgeDocsMentionSupportedModes:
    def test_start_here_mentions_source_checkout(self):
        text = _text_lower(ROOT / "docs" / "START_HERE.md")
        assert "scripts/run_skill.py" in text

    def test_start_here_mentions_editable_install(self):
        text = _text_lower(ROOT / "docs" / "START_HERE.md")
        assert "pip install -e ." in text or "editable" in text

    def test_manual_host_mentions_runtime_bridge(self):
        text = _text_lower(ROOT / "docs" / "install" / "manual-host.md")
        assert "runtime bridge" in text

    def test_runtime_bridge_cli_mentions_source_checkout(self):
        text = _text_lower(ROOT / "docs" / "install" / "runtime-bridge-cli.md")
        assert "source checkout" in text or "git clone" in text

    def test_runtime_bridge_cli_mentions_console_script(self):
        text = _text_lower(ROOT / "docs" / "install" / "runtime-bridge-cli.md")
        assert "fund-agent-run-skill" in text or "console script" in text or "project.scripts" in text
