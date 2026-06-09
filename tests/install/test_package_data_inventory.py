"""Package data and source distribution inventory checks.

Verifies that the repo contains and packaging metadata includes (or at
least does not exclude) all required runtime files, contracts, docs,
examples, and skillpack YAMLs needed for a working source checkout
or editable install.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"


def _pyproject_data() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


class TestSkillpackYamls:
    SKILLPACK_YAMLS = [
        "skillpack/fund-agent.skillpack.yaml",
        "skillpack/capabilities.yaml",
        "skillpack/tools.yaml",
        "skillpack/input-contracts.yaml",
        "skillpack/artifact-contracts.yaml",
        "skillpack/decision-contracts.yaml",
        "skillpack/thesis-contracts.yaml",
    ]

    @pytest.mark.parametrize("relpath", SKILLPACK_YAMLS)
    def test_skillpack_yaml_exists(self, relpath):
        assert (ROOT / relpath).exists(), f"required skillpack YAML missing: {relpath}"

    @pytest.mark.parametrize("relpath", SKILLPACK_YAMLS)
    def test_skillpack_yaml_is_valid_yaml(self, relpath):
        path = ROOT / relpath
        if not path.exists():
            pytest.skip(f"{relpath} does not exist")
        yaml.safe_load(path.read_text(encoding="utf-8"))


class TestSkillDocs:
    MANIFEST_SKILL_SLUGS = [
        "fund-analysis",
        "decision-support",
        "news-research",
        "sentiment-analysis",
        "thesis-generation",
    ]

    @pytest.mark.parametrize("slug", MANIFEST_SKILL_SLUGS)
    def test_skill_md_exists(self, slug):
        path = ROOT / "skills" / slug / "SKILL.md"
        assert path.exists(), f"required skill doc missing: skills/{slug}/SKILL.md"


class TestDocsContracts:
    REQUIRED_CONTRACT_DOCS = [
        "docs/START_HERE.md",
        "docs/contracts/skill-output-contract.v1.md",
        "docs/contracts/fund-analysis-input-contract.v1.md",
        "docs/contracts/fund-analysis-artifacts.v1.md",
        "docs/contracts/decision-support-contract.v1.md",
        "docs/contracts/thesis-generation-contract.v1.md",
        "docs/contracts/report-output-contract.v1.md",
    ]

    @pytest.mark.parametrize("relpath", REQUIRED_CONTRACT_DOCS)
    def test_contract_doc_exists(self, relpath):
        assert (ROOT / relpath).exists(), f"required contract doc missing: {relpath}"


class TestExampleFixtures:
    SCENARIO_FIXTURES = [
        "examples/scenarios/cn_fund_7d_redemption_fee.json",
        "examples/scenarios/cn_fund_ai_semiconductor_overweight.json",
        "examples/scenarios/cn_fund_qdii_sp500_overlap.json",
        "examples/scenarios/cn_fund_dca_drawdown_review.json",
        "examples/scenarios/cn_fund_ledger_derived_snapshot.json",
    ]

    DECISION_SUPPORT_FIXTURES = [
        "examples/decision_support/single_active_buy_with_evidence.json",
        "examples/decision_support/single_active_buy_without_evidence_invalid.json",
        "examples/decision_support/single_passive_hold_without_evidence.json",
        "examples/decision_support/trade_plan_selected_trade_with_caps.json",
        "examples/decision_support/trade_plan_no_evidence_downgraded.json",
        "examples/decision_support/trade_plan_forbidden_action_skipped.json",
    ]

    THESIS_GENERATION_FIXTURES = [
        "examples/thesis_generation/evidence_graph_balanced_thesis.json",
        "examples/thesis_generation/fund_analysis_report_thesis.json",
        "examples/thesis_generation/sparse_context_low_confidence.json",
        "examples/thesis_generation/thesis_missing_evidence_partial.json",
        "examples/thesis_generation/thesis_from_fund_analysis_artifacts.json",
        "examples/thesis_generation/thesis_with_mixed_evidence.json",
    ]

    @pytest.mark.parametrize("relpath", SCENARIO_FIXTURES)
    def test_scenario_fixture_exists(self, relpath):
        assert (ROOT / relpath).exists(), f"required scenario fixture missing: {relpath}"

    @pytest.mark.parametrize("relpath", DECISION_SUPPORT_FIXTURES)
    def test_decision_support_fixture_exists(self, relpath):
        assert (ROOT / relpath).exists(), f"required decision_support fixture missing: {relpath}"

    @pytest.mark.parametrize("relpath", THESIS_GENERATION_FIXTURES)
    def test_thesis_generation_fixture_exists(self, relpath):
        assert (ROOT / relpath).exists(), f"required thesis_generation fixture missing: {relpath}"


class TestPackageMetadata:
    def test_pyproject_includes_src_packages(self):
        data = _pyproject_data()
        include = data.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("include", [])
        assert "src*" in include, (
            "pyproject.toml must include 'src*' in setuptools.packages.find.include"
        )

    def test_pyproject_declares_console_script(self):
        data = _pyproject_data()
        scripts = data.get("project", {}).get("scripts", {})
        assert "fund-agent-run-skill" in scripts, (
            "pyproject.toml must declare fund-agent-run-skill console script"
        )
        assert scripts["fund-agent-run-skill"] == "src.skillpack.run_skill:main", (
            "fund-agent-run-skill must point at src.skillpack.run_skill:main"
        )

    def test_pyproject_does_not_exclude_required_packages(self):
        data = _pyproject_data()
        exclude = data.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("exclude", [])
        for pkg in ["src.skillpack", "src.schemas", "src.skills_runtime", "src.tools"]:
            assert pkg not in exclude, (
                f"pyproject.toml must not exclude required package {pkg}"
            )


class TestRuntimeBridgeSourceCheckout:
    def test_run_skill_script_exists(self):
        assert (ROOT / "scripts" / "run_skill.py").exists()

    def test_run_skill_module_exists(self):
        assert (ROOT / "src" / "skillpack" / "run_skill.py").exists()

    def test_resources_module_exists(self):
        assert (ROOT / "src" / "skillpack" / "resources.py").exists()

    def test_manifest_path_constant_matches_repo(self):
        from src.skillpack.run_skill import DEFAULT_MANIFEST_PATH
        expected = "skillpack/fund-agent.skillpack.yaml"
        assert DEFAULT_MANIFEST_PATH == expected, (
            f"DEFAULT_MANIFEST_PATH is {DEFAULT_MANIFEST_PATH!r}, expected {expected!r}"
        )
        assert (ROOT / expected).exists(), (
            f"DEFAULT_MANIFEST_PATH points to {expected} but file does not exist"
        )

    def test_resource_resolver_finds_manifest(self):
        from src.skillpack.resources import resolve_manifest_path
        path = resolve_manifest_path()
        assert path.exists(), f"resolve_manifest_path() returned non-existent path: {path}"

    def test_resource_resolver_finds_skillpack_yamls(self):
        from src.skillpack.resources import resolve_skillpack_file
        for filename in [
            "capabilities.yaml",
            "artifact-contracts.yaml",
            "input-contracts.yaml",
            "decision-contracts.yaml",
            "thesis-contracts.yaml",
        ]:
            path = resolve_skillpack_file(filename)
            assert path.exists(), f"resolve_skillpack_file({filename!r}) returned non-existent path: {path}"
