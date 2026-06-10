"""Packaged skillpack file inclusion checks.

Asserts that the source tree contains all files required for an
external host to discover, inspect, and run the skill pack.

These tests verify source-checkout expectations. They do not
publish or run npm publish.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _assert_exists(rel: str) -> None:
    path = ROOT / rel
    assert path.exists(), f"Required file missing: {rel}"


def _glob_exists(pattern: str, directory: str) -> None:
    path = ROOT / directory
    matches = list(path.glob(pattern))
    assert matches, f"No files matching {pattern} in {directory}"


class TestSkillpackManifest:
    def test_skillpack_manifest_exists(self):
        _assert_exists("skillpack/fund-agent.skillpack.yaml")

    def test_skillpack_capabilities_exists(self):
        _assert_exists("skillpack/capabilities.yaml")

    def test_skillpack_input_contracts_exists(self):
        _assert_exists("skillpack/input-contracts.yaml")

    def test_skillpack_artifact_contracts_exists(self):
        _assert_exists("skillpack/artifact-contracts.yaml")

    def test_skillpack_decision_contracts_exists(self):
        _assert_exists("skillpack/decision-contracts.yaml")

    def test_skillpack_thesis_contracts_exists(self):
        _assert_exists("skillpack/thesis-contracts.yaml")


class TestSkillMarkdownDocs:
    @staticmethod
    def _skill_slugs():
        return ["fund-analysis", "decision-support", "news-research", "sentiment-analysis", "thesis-generation"]

    def test_skill_md_files_exist(self):
        for slug in self._skill_slugs():
            _assert_exists(f"skills/{slug}/SKILL.md")


class TestRuntimeBridgeScript:
    def test_run_skill_script_exists(self):
        _assert_exists("scripts/run_skill.py")


class TestDocsStartHere:
    def test_start_here_exists(self):
        _assert_exists("docs/START_HERE.md")


class TestContractDocs:
    def test_contract_docs_exist(self):
        contracts_dir = ROOT / "docs" / "contracts"
        assert contracts_dir.exists()
        md_files = list(contracts_dir.glob("*.md"))
        assert len(md_files) >= 7, f"Expected at least 7 contract docs, found {len(md_files)}"


class TestExampleFixtures:
    def test_scenario_fixtures_exist(self):
        _glob_exists("*.json", "examples/scenarios")

    def test_decision_support_fixtures_exist(self):
        _glob_exists("*.json", "examples/decision_support")

    def test_thesis_generation_fixtures_exist(self):
        _glob_exists("*.json", "examples/thesis_generation")


class TestOpenCodePlugin:
    def test_opencode_plugin_exists(self):
        _assert_exists("opencode.plugin.js")


class TestPackageJsonFilesList:
    def test_package_json_includes_plugin(self):
        pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        files = pkg.get("files", [])
        assert "opencode.plugin.js" in files
        assert "skillpack/" in files
        assert "skills/" in files

    def test_package_json_includes_docs_install(self):
        pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        files = pkg.get("files", [])
        assert "docs/install/" in files


class TestPyprojectSourceCheckout:
    def test_pyproject_includes_src_packages(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "src" in pyproject
        assert "fund-agent" in pyproject

    def test_pyproject_defines_console_scripts(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "fund-agent-run-skill" in pyproject
        assert "fund-agent-doctor" in pyproject
