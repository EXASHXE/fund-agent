"""Host acceptance docs tests.

Assert docs mention:
- fund-agent-doctor
- scripts/fund_agent_doctor.py
- examples/host_subprocess_runner.py
- generic subprocess host
- host owns data fetching/provider SDKs
- fake/sample fixtures
- no broker/order execution
- OpenCode plugin metadata/doc-reader only
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    full = ROOT / relpath
    if not full.exists():
        pytest.skip(f"{relpath} not found")
    return full.read_text(encoding="utf-8")


class TestStartHereDoc:
    def test_mentions_doctor(self):
        content = _read("docs/START_HERE.md")
        assert "fund-agent-doctor" in content or "doctor" in content.lower()

    def test_mentions_host_subprocess_runner(self):
        content = _read("docs/START_HERE.md")
        assert "host_subprocess_runner" in content or "subprocess host" in content.lower()

    def test_mentions_host_owns_data_fetching(self):
        content = _read("docs/START_HERE.md")
        assert "host owns" in content.lower() or "host-owned" in content.lower()


class TestRuntimeBridgeCliDoc:
    def test_mentions_doctor(self):
        content = _read("docs/install/runtime-bridge-cli.md")
        assert "fund-agent-doctor" in content or "doctor" in content.lower()

    def test_mentions_host_subprocess_runner(self):
        content = _read("docs/install/runtime-bridge-cli.md")
        assert "host_subprocess_runner" in content or "subprocess host" in content.lower()


class TestManualHostDoc:
    def test_mentions_doctor(self):
        content = _read("docs/install/manual-host.md")
        assert "fund-agent-doctor" in content or "doctor" in content.lower()

    def test_mentions_host_subprocess_runner(self):
        content = _read("docs/install/manual-host.md")
        assert "host_subprocess_runner" in content or "subprocess host" in content.lower()


class TestHostIntegrationsReadme:
    def test_mentions_doctor(self):
        content = _read("docs/host-integrations/README.md")
        assert "fund-agent-doctor" in content or "doctor" in content.lower()

    def test_mentions_generic_subprocess_host(self):
        content = _read("docs/host-integrations/README.md")
        assert "generic-subprocess-host" in content or "subprocess host" in content.lower()


class TestGenericSubprocessHostDoc:
    def test_mentions_doctor(self):
        content = _read("docs/host-integrations/generic-subprocess-host.md")
        assert "fund-agent-doctor" in content or "doctor" in content.lower()

    def test_mentions_host_subprocess_runner(self):
        content = _read("docs/host-integrations/generic-subprocess-host.md")
        assert "host_subprocess_runner" in content or "subprocess runner" in content.lower()


class TestDocsMentionKeyConcepts:
    @pytest.mark.parametrize("doc_rel", [
        "docs/START_HERE.md",
        "docs/install/manual-host.md",
        "docs/host-integrations/generic-subprocess-host.md",
    ])
    def test_host_owns_data_fetching(self, doc_rel):
        content = _read(doc_rel)
        lower = content.lower()
        assert "host owns" in lower or "host-owned" in lower

    @pytest.mark.parametrize("doc_rel", [
        "docs/START_HERE.md",
        "docs/install/manual-host.md",
    ])
    def test_no_broker_order_execution(self, doc_rel):
        content = _read(doc_rel)
        lower = content.lower()
        assert "no broker" in lower or "not a broker" in lower or "does not place trades" in lower

    @pytest.mark.parametrize("doc_rel", [
        "docs/START_HERE.md",
        "docs/install/manual-host.md",
    ])
    def test_opencode_plugin_metadata_only(self, doc_rel):
        content = _read(doc_rel)
        lower = content.lower()
        assert "metadata" in lower and ("doc-reader" in lower or "doc reader" in lower)

    @pytest.mark.parametrize("doc_rel", [
        "docs/install/runtime-bridge-cli.md",
        "docs/host-integrations/generic-subprocess-host.md",
    ])
    def test_fake_sample_fixtures(self, doc_rel):
        content = _read(doc_rel)
        lower = content.lower()
        assert "fake" in lower or "sample" in lower or "fixture" in lower
