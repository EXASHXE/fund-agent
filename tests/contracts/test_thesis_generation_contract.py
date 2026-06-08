"""Contract tests for thesis_generation skill."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.skillpack.thesis_contracts import (
    get_thesis_contract,
    load_thesis_contracts,
    thesis_artifact_keys,
)

ROOT = Path(__file__).resolve().parents[2]
THESIS_YAML = ROOT / "skillpack" / "thesis-contracts.yaml"


class TestThesisContractsYAML:
    def test_yaml_exists_and_parses(self):
        assert THESIS_YAML.is_file()
        doc = yaml.safe_load(THESIS_YAML.read_text(encoding="utf-8"))
        assert isinstance(doc, dict)

    def test_schema_version(self):
        doc = load_thesis_contracts()
        assert doc["schema_version"] == "thesis-contracts.v1"

    def test_contracts_section_has_thesis_generation(self):
        doc = load_thesis_contracts()
        assert "thesis_generation" in doc["contracts"]

    def test_runtime_id(self):
        contract = get_thesis_contract("thesis_generation")
        assert contract["runtime_id"] == "thesis_generation"

    def test_doc_slug(self):
        contract = get_thesis_contract("thesis_generation")
        assert contract["doc_slug"] == "thesis-generation"

    def test_artifact_only_is_true(self):
        contract = get_thesis_contract("thesis_generation")
        assert contract["artifact_only"] is True

    def test_formal_outputs_forbidden(self):
        contract = get_thesis_contract("thesis_generation")
        forbidden = contract.get("formal_outputs_forbidden", [])
        assert "Decision" in forbidden
        assert "ExecutionLedger" in forbidden

    def test_artifact_keys_include_thesis_draft(self):
        contract = get_thesis_contract("thesis_generation")
        keys = [a["key"] for a in contract.get("artifact_keys", [])]
        assert "thesis_draft" in keys

    def test_thesis_draft_fields_all_present(self):
        contract = get_thesis_contract("thesis_generation")
        expected = {
            "task_id", "topic", "related_entities", "thesis_statement",
            "supporting_evidence", "counter_evidence", "neutral_evidence",
            "missing_evidence", "confidence_assessment", "watch_conditions",
            "invalidating_conditions", "next_research_questions",
            "source_summary", "limitations", "decision_boundary_note",
        }
        actual = set(contract.get("thesis_draft_fields", []))
        assert actual == expected

    def test_status_values(self):
        contract = get_thesis_contract("thesis_generation")
        assert set(contract.get("status_values", [])) == {"OK", "PARTIAL", "FAILED"}

    def test_loader_supports_both_id_forms(self):
        contract_underscore = get_thesis_contract("thesis_generation")
        contract_hyphen = get_thesis_contract("thesis-generation")
        assert contract_underscore == contract_hyphen

    def test_thesis_artifact_keys_returns_thesis_draft(self):
        keys = thesis_artifact_keys("thesis_generation")
        assert keys == ["thesis_draft"]

    def test_unknown_skill_id_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_thesis_contract("nonexistent")


class TestThesisContractDoc:
    def test_contract_doc_exists(self):
        doc_path = ROOT / "docs" / "contracts" / "thesis-generation-contract.v1.md"
        assert doc_path.is_file()

    def test_contract_doc_mentions_formal_decision_requires_decision_support(self):
        doc_path = ROOT / "docs" / "contracts" / "thesis-generation-contract.v1.md"
        text = doc_path.read_text(encoding="utf-8")
        assert "decision_support" in text.lower()

    def test_contract_doc_says_no_llm_provider_network(self):
        doc_path = ROOT / "docs" / "contracts" / "thesis-generation-contract.v1.md"
        text = doc_path.read_text(encoding="utf-8").lower().replace("**", "")
        no_patterns = ("must not call llm", "must not call provider", "must not call network")
        assert any(p in text for p in no_patterns), "Missing prohibition language"


class TestThesisFixtureDocs:
    def test_readme_mentions_all_fixtures(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        assert readme.is_file()
        text = readme.read_text(encoding="utf-8")
        fixture_names = [
            "thesis_with_mixed_evidence.json",
            "thesis_missing_evidence_partial.json",
            "thesis_from_fund_analysis_artifacts.json",
            "evidence_graph_balanced_thesis.json",
            "sparse_context_low_confidence.json",
            "fund_analysis_report_thesis.json",
        ]
        for name in fixture_names:
            assert name in text, f"README missing fixture: {name}"

    def test_readme_has_disclaimers(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "fake/sample" in text.lower() or "NOT investment advice" in text
        assert "decision_support" in text
        assert "Host owns" in text or "host owns" in text.lower()
