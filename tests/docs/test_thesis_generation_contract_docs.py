"""Documentation tests for thesis_generation contract docs."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
THESIS_YAML = ROOT / "skillpack" / "thesis-contracts.yaml"


class TestThesisGenerationContractDocs:
    def test_contract_doc_exists(self):
        doc = ROOT / "docs" / "contracts" / "thesis-generation-contract.v1.md"
        assert doc.is_file()

    def test_every_thesis_draft_field_appears_in_docs(self):
        contract = yaml.safe_load(THESIS_YAML.read_text(encoding="utf-8"))
        fields = contract["contracts"]["thesis_generation"]["thesis_draft_fields"]
        doc = ROOT / "docs" / "contracts" / "thesis-generation-contract.v1.md"
        text = doc.read_text(encoding="utf-8")
        for field in fields:
            assert field in text, f"Field '{field}' not found in thesis contract doc"

    def test_docs_say_formal_decisions_require_decision_support(self):
        doc = ROOT / "docs" / "contracts" / "thesis-generation-contract.v1.md"
        text = doc.read_text(encoding="utf-8").lower()
        assert "decision_support" in text
        assert "formal" in text

    def test_docs_say_no_llm_provider_network(self):
        doc = ROOT / "docs" / "contracts" / "thesis-generation-contract.v1.md"
        text = doc.read_text(encoding="utf-8").lower().replace("**", "")
        no_patterns = ("must not call llm", "must not call provider", "must not call network")
        assert any(p in text for p in no_patterns), "Missing prohibition language"


class TestThesisFixtureDocs:
    def test_fixture_readme_exists(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        assert readme.is_file()

    def test_readme_mentions_all_fixtures(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        for name in (
            "thesis_with_mixed_evidence.json",
            "thesis_missing_evidence_partial.json",
            "thesis_from_fund_analysis_artifacts.json",
            "evidence_graph_balanced_thesis.json",
            "sparse_context_low_confidence.json",
            "fund_analysis_report_thesis.json",
        ):
            assert name in text, f"README missing fixture: {name}"

    def test_readme_says_not_investment_advice(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "NOT investment advice" in text

    def test_readme_says_no_real_personal_holdings(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "No real personal holdings" in text

    def test_readme_says_host_owns_provider_integration(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "host owns" in text.lower()

    def test_readme_links_decision_support(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "decision_support" in text

    def test_readme_has_boundary_disclaimers(self):
        readme = ROOT / "examples" / "thesis_generation" / "README.md"
        text = readme.read_text(encoding="utf-8")
        assert "Boundary Disclaimers" in text
