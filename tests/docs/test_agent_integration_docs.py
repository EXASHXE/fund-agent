"""Tests for agent integration documentation consistency."""

from __future__ import annotations

from pathlib import Path

import pytest

AGENT_INTEGRATION_DIR = Path(__file__).resolve().parents[2] / "docs" / "agent-integration"


class TestAgentIntegrationDocs:
    def test_readme_exists(self):
        assert (AGENT_INTEGRATION_DIR / "README.md").exists()

    def test_report_only_flow_exists(self):
        assert (AGENT_INTEGRATION_DIR / "report-only-flow.md").exists()

    def test_formal_decision_flow_exists(self):
        assert (AGENT_INTEGRATION_DIR / "formal-decision-flow.md").exists()

    def test_provider_snapshot_flow_exists(self):
        assert (AGENT_INTEGRATION_DIR / "provider-snapshot-flow.md").exists()

    def test_private_data_flow_exists(self):
        assert (AGENT_INTEGRATION_DIR / "private-data-flow.md").exists()

    def test_forbidden_behaviors_exists(self):
        assert (AGENT_INTEGRATION_DIR / "forbidden-behaviors.md").exists()

    def test_docs_mention_no_broker_execution(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "broker" in all_text.lower() or "经纪" in all_text or "执行" in all_text

    def test_docs_mention_host_owned_live_data(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "host" in all_text.lower() or "主机" in all_text

    def test_docs_mention_core_no_network(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "no-network" in all_text or "无网络" in all_text or "no network" in all_text.lower()

    def test_docs_distinguish_report_only_and_formal_decision(self):
        readme = (AGENT_INTEGRATION_DIR / "README.md").read_text(encoding="utf-8")
        assert "report" in readme.lower()
        assert "decision" in readme.lower() or "决策" in readme

    def test_docs_mention_private_data_not_committed(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "commit" in all_text.lower() or "提交" in all_text

    def test_docs_mention_provider_snapshot(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "snapshot" in all_text.lower() or "快照" in all_text

    def test_docs_do_not_claim_live_provider_support_in_core(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "core runtime" not in all_text.lower() or "no-network" in all_text.lower() or "host" in all_text.lower()

    def test_docs_do_not_claim_auto_trading(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "auto-trad" not in all_text.lower() and "autonomous trad" not in all_text.lower()

    def test_docs_do_not_instruct_real_credentials_in_repo(self):
        all_text = ""
        for f in AGENT_INTEGRATION_DIR.rglob("*.md"):
            all_text += f.read_text(encoding="utf-8")
        assert "never commit" in all_text.lower() or "不提交" in all_text or "do not commit" in all_text.lower()
