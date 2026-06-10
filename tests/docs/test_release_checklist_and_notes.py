"""Tests for v0.4.9 release checklist and release notes draft docs."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ROOT / "docs" / "release-checklist-v0.4.9.md"
NOTES = ROOT / "docs" / "release-notes-v0.4.9-draft.md"


class TestReleaseChecklist:
    def test_checklist_exists(self):
        assert CHECKLIST.is_file()

    def test_v049_metadata_prepared(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "v0.4.9 metadata has been prepared" in text.lower()

    def test_no_tag_created_yet(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tag has not been created" in text.lower()

    def test_no_pypi_published(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "no pypi" in text.lower()

    def test_no_npm_published(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "no npm" in text.lower()

    def test_gates_must_pass_before_tagging(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "gates must pass before tagging" in text.lower()

    def test_includes_compileall_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "compileall" in text

    def test_includes_pytest_schemas_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/schemas" in text

    def test_includes_pytest_architecture_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/architecture" in text

    def test_includes_pytest_skills_runtime_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/skills_runtime" in text

    def test_includes_pytest_tools_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/tools" in text

    def test_includes_pytest_integration_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/integration" in text

    def test_includes_pytest_runtime_bridge_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/runtime_bridge" in text

    def test_includes_pytest_contracts_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/contracts" in text

    def test_includes_pytest_docs_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/docs" in text

    def test_includes_pytest_golden_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/golden" in text

    def test_includes_pytest_skillpack_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/skillpack" in text

    def test_includes_pytest_install_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "tests/install" in text

    def test_includes_full_pytest_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "pytest -q" in text

    def test_includes_node_check_gate(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "node --check" in text

    def test_includes_plugin_gate_script(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "check_plugin_gate" in text

    def test_mentions_optional_build_skip(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "build" in text.lower() and "skip" in text.lower() and "unavailable" in text.lower()

    def test_mentions_optional_editable_install_skip(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "editable" in text.lower() and "skip" in text.lower()

    def test_source_checkout_smoke_canonical(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "source-checkout" in text.lower() and "canonical" in text.lower()

    def test_tag_commands_not_yet_executed(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        assert "not yet executed" in text.lower()


class TestReleaseNotes:
    def test_notes_exist(self):
        assert NOTES.is_file()

    def test_refers_to_v049(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "v0.4.9" in text

    def test_host_owns_data_fetching(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "data fetching" in text.lower()
        assert "provider sdk" in text.lower() or "provider sdks" in text.lower()

    def test_host_owns_network_credentials(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "network" in text.lower()
        assert "credentials" in text.lower()

    def test_opencode_metadata_doc_reader_only(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "opencode" in text.lower()
        assert "metadata" in text.lower() and "doc-reader" in text.lower()

    def test_no_broker_order_execution(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "no broker" in text.lower() or "no order execution" in text.lower()

    def test_no_live_data_fetching(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "no live data" in text.lower() or "no live market" in text.lower()

    def test_fund_analysis_no_formal_decision(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "fund_analysis" in text.lower() or "fund analysis" in text.lower()
        assert "decision" in text.lower()

    def test_thesis_generation_no_formal_decision(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "thesis_generation" in text.lower() or "thesis generation" in text.lower()

    def test_decision_support_only_formal_runtime(self):
        text = NOTES.read_text(encoding="utf-8")
        assert "decision_support" in text.lower() or "decision support" in text.lower()
        assert "only" in text.lower()

    def test_fake_sample_fixtures_only(self):
        text = NOTES.read_text(encoding="utf-8")
        assert ("fake" in text.lower() or "sample" in text.lower()) and "fixture" in text.lower()

    def test_no_pypi_publication_claim(self):
        text = NOTES.read_text(encoding="utf-8")
        lower = text.lower()
        assert "no pypi" in lower

    def test_no_npm_publication_claim(self):
        text = NOTES.read_text(encoding="utf-8")
        lower = text.lower()
        assert "no npm" in lower

    def test_draft_until_tag(self):
        text = NOTES.read_text(encoding="utf-8")
        lower = text.lower()
        assert "draft" in lower or "no tag" in lower

    def test_does_not_claim_tag_exists(self):
        text = NOTES.read_text(encoding="utf-8")
        lower = text.lower()
        for phrase in ("a tag exists", "the tag exists", "tag already exists"):
            assert phrase not in lower


class TestNeitherFileClaimsPublication:
    def test_checklist_does_not_claim_publication(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        lower = text.lower()
        assert "no pypi" in lower
        assert "no npm" in lower

    def test_notes_does_not_claim_publication(self):
        text = NOTES.read_text(encoding="utf-8")
        lower = text.lower()
        assert "no pypi" in lower or "no package publication" in lower
        assert "no npm" in lower

    def test_checklist_does_not_claim_tag_exists(self):
        text = CHECKLIST.read_text(encoding="utf-8")
        lower = text.lower()
        assert "tag has not been created" in lower

    def test_notes_does_not_claim_tag_exists(self):
        text = NOTES.read_text(encoding="utf-8")
        lower = text.lower()
        for phrase in ("a tag exists", "the tag exists", "tag already exists"):
            assert phrase not in lower
