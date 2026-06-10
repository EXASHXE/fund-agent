"""Tests for host smoke documentation consistency.

Asserts that key docs mention the smoke script, canonical bridge
commands, and boundary rules.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").lower()


class TestStartHereDocs:
    def test_mentions_smoke_script(self):
        text = _text("docs/START_HERE.md")
        assert "smoke_host_install" in text or "smoke host install" in text

    def test_mentions_list_skills(self):
        text = _text("docs/START_HERE.md")
        assert "--list-skills" in text

    def test_says_host_owns_provider_integration(self):
        text = _text("docs/START_HERE.md")
        assert "host owns" in text

    def test_says_no_broker_order_execution(self):
        text = _text("docs/START_HERE.md")
        assert "broker" in text or "order execution" in text

    def test_says_fund_analysis_no_formal_decision(self):
        text = _text("docs/START_HERE.md")
        assert "fund_analysis" in text
        assert "decision" in text

    def test_says_decision_support_only_formal_decision_runtime(self):
        text = _text("docs/START_HERE.md")
        assert "decision_support" in text
        assert "only" in text


class TestGenericSubprocessHostDocs:
    def test_mentions_smoke_script(self):
        text = _text("docs/host-integrations/generic-subprocess-host.md")
        assert "smoke_host_install" in text or "smoke host install" in text

    def test_mentions_list_skills(self):
        text = _text("docs/host-integrations/generic-subprocess-host.md")
        assert "--list-skills" in text

    def test_mentions_explain_input(self):
        text = _text("docs/host-integrations/generic-subprocess-host.md")
        assert "--explain-input" in text

    def test_mentions_output_schema(self):
        text = _text("docs/host-integrations/generic-subprocess-host.md")
        assert "--output-schema" in text


class TestOpenCodeDocs:
    def test_says_metadata_doc_reader_only(self):
        text = _text("docs/host-integrations/opencode.md")
        assert "metadata + doc" in text or "metadata and doc" in text

    def test_says_host_owns_provider_integration(self):
        text = _text("docs/host-integrations/opencode.md")
        assert "host owns" in text or "host-owned" in text

    def test_says_no_broker_order_execution(self):
        text = _text("docs/host-integrations/opencode.md")
        assert "broker" in text or "order execution" in text

    def test_says_fund_analysis_no_formal_decision(self):
        text = _text("docs/host-integrations/opencode.md")
        assert "fund_analysis" in text or "fund-analysis" in text

    def test_says_decision_support_only_formal_decision_runtime(self):
        text = _text("docs/host-integrations/opencode.md")
        assert "decision_support" in text or "decision-support" in text

    def test_says_runtime_bridge_requires_source_checkout(self):
        text = _text("docs/host-integrations/opencode.md")
        assert "source checkout" in text or "source-checkout" in text


class TestHostIntegrationsReadme:
    def test_mentions_smoke_script(self):
        text = _text("docs/host-integrations/README.md")
        assert "smoke_host_install" in text or "smoke host install" in text
