"""Release consistency tests for current version.

Ensures all version declarations agree, CHANGELOG is updated,
README does not overclaim, and public API imports work.
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

VERSION_PATH = ROOT / "VERSION"
PYPROJECT_PATH = ROOT / "pyproject.toml"
PACKAGE_JSON_PATH = ROOT / "package.json"
MANIFEST_PATH = ROOT / "skillpack" / "fund-agent.skillpack.yaml"
PLUGIN_PATH = ROOT / "opencode.plugin.js"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
README_PATH = ROOT / "README.md"
CHECKLIST_PATH = ROOT / "docs" / "release" / "v0.10.0-beta-readiness-checklist.md"
PROVIDERS_EXAMPLE_PATH = ROOT / "config" / "providers.example.yaml"


class TestVersionConsistency:
    def test_version_file_matches_expected(self):
        v = VERSION_PATH.read_text(encoding="utf-8").strip()
        assert v == EXPECTED_VERSION, f"VERSION is {v!r}, expected {EXPECTED_VERSION!r}"

    def test_pyproject_version_matches_expected(self):
        data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        pv = data["project"]["version"]
        assert pv == EXPECTED_VERSION, f"pyproject.toml version is {pv!r}"

    def test_package_json_version_matches_expected(self):
        data = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
        pjv = data["version"]
        assert pjv == EXPECTED_VERSION, f"package.json version is {pjv!r}"

    def test_manifest_version_matches_expected(self):
        data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        mv = data["version"]
        assert mv == EXPECTED_VERSION, f"skillpack manifest version is {mv!r}"

    def test_plugin_version_matches_expected(self):
        text = PLUGIN_PATH.read_text(encoding="utf-8")
        pattern = r'PLUGIN_VERSION\s*=\s*["\']' + re.escape(EXPECTED_VERSION) + r'["\']'
        assert re.search(pattern, text), (
            f"opencode.plugin.js PLUGIN_VERSION is not {EXPECTED_VERSION!r}"
        )

    def test_all_version_sources_agree(self):
        v = VERSION_PATH.read_text(encoding="utf-8").strip()
        data_p = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        data_j = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
        data_m = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        versions = {
            "VERSION": v,
            "pyproject.toml": data_p["project"]["version"],
            "package.json": data_j["version"],
            "skillpack manifest": data_m["version"],
        }
        unique = set(versions.values())
        assert len(unique) == 1, f"Version sources disagree: {versions}"

    def test_python_version_returns_expected(self):
        from src.fund_agent.version import __version__
        assert __version__ == EXPECTED_VERSION, (
            f"src.fund_agent.__version__ is {__version__!r}"
        )

    def test_toplevel_version_returns_expected(self):
        from fund_agent.version import __version__
        assert __version__ == EXPECTED_VERSION, (
            f"fund_agent.__version__ is {__version__!r}"
        )


class TestChangelogCurrent:
    def test_changelog_has_current_version_section(self):
        text = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert f"## [{EXPECTED_VERSION}]" in text or f"## {EXPECTED_VERSION}" in text, (
            f"CHANGELOG.md does not have a v{EXPECTED_VERSION} section"
        )

    def test_changelog_current_section_contains_content(self):
        text = CHANGELOG_PATH.read_text(encoding="utf-8")
        pattern = f"## [{EXPECTED_VERSION}]"
        section_start = text.find(pattern) if pattern in text else text.find(f"## {EXPECTED_VERSION}")
        assert section_start >= 0, f"CHANGELOG missing {EXPECTED_VERSION} section"
        next_section = text.find("## [", section_start + len(pattern))
        section = text[section_start:next_section] if next_section > 0 else text[section_start:]
        assert "Added" in section or "### Added" in section or "### v" in section, (
            f"CHANGELOG {EXPECTED_VERSION} section appears empty or malformed"
        )


class TestReadmeCurrent:
    def test_readme_mentions_current_version(self):
        text = README_PATH.read_text(encoding="utf-8")
        assert EXPECTED_VERSION in text, f"README.md does not mention {EXPECTED_VERSION}"

    def test_readme_does_not_overclaim_live_data(self):
        text = README_PATH.read_text(encoding="utf-8").lower()
        assert "no live data" in text or "no-network" in text or "no network" in text, (
            "README does not state no-network/no-live-data boundary"
        )

    def test_readme_does_not_overclaim_broker(self):
        text = README_PATH.read_text(encoding="utf-8").lower()
        assert "not a broker" in text or "no broker" in text or "no order execution" in text, (
            "README does not state no-broker boundary"
        )

    def test_readme_does_not_overclaim_autonomous_trading(self):
        text = README_PATH.read_text(encoding="utf-8").lower()
        assert "not an autonomous trader" in text or "no autonomous" in text, (
            "README does not state no-autonomous-trading boundary"
        )

    def test_readme_says_provider_adapters_optional(self):
        text = README_PATH.read_text(encoding="utf-8").lower()
        assert "optional" in text and ("prototype" in text or "host adapter" in text), (
            "README does not state provider adapters are optional/prototype"
        )

    def test_readme_says_fund_agent_preferred(self):
        text = README_PATH.read_text(encoding="utf-8")
        assert "fund_agent.*" in text and "preferred public API" in text, (
            "README does not state fund_agent.* is preferred public API"
        )

    def test_readme_does_not_claim_v1_stability(self):
        text = README_PATH.read_text(encoding="utf-8")
        assert "v1.0.0" not in text or "not v1.0.0" in text.lower(), (
            "README should not claim v1.0.0 stability"
        )

    def test_readme_title_says_mutual_fund_advisory(self):
        text = README_PATH.read_text(encoding="utf-8")
        assert "mutual fund advisory" in text.lower(), (
            "README title should mention mutual fund advisory"
        )


class TestReadinessChecklist:
    def test_readiness_checklist_exists(self):
        assert CHECKLIST_PATH.exists(), "current release readiness checklist is missing"

    def test_readiness_checklist_mentions_version(self):
        text = CHECKLIST_PATH.read_text(encoding="utf-8")
        assert EXPECTED_VERSION in text, f"Readiness checklist does not mention {EXPECTED_VERSION}"


class TestProvidersExampleNoSecrets:
    def test_providers_example_has_no_real_secrets(self):
        assert PROVIDERS_EXAMPLE_PATH.exists(), (
            f"providers.example.yaml not found at {PROVIDERS_EXAMPLE_PATH}"
        )
        text = PROVIDERS_EXAMPLE_PATH.read_text(encoding="utf-8")
        forbidden_patterns = [
            r'api_key:\s*[A-Za-z0-9]{20,}',
            r'secret:\s*[A-Za-z0-9]{20,}',
            r'token:\s*[A-Za-z0-9]{20,}',
            r'password:\s*\S+',
            r'cookie:\s*[A-Za-z0-9]{20,}',
        ]
        for pat in forbidden_patterns:
            assert not re.search(pat, text, re.IGNORECASE), (
                f"providers.example.yaml may contain real secrets (matched {pat})"
            )

    def test_providers_example_includes_expected_env_placeholders(self):
        text = PROVIDERS_EXAMPLE_PATH.read_text(encoding="utf-8")
        expected_placeholders = [
            "NEWS_API_KEY",
            "TAVILY_API_KEY",
            "EXA_API_KEY",
            "SERPAPI_API_KEY",
            "CUSTOM_NEWS_MCP_TOKEN",
            "XUEQIU_COOKIE",
            "XUEQIU_TOKEN",
            "EASTMONEY_COOKIE",
        ]
        for placeholder in expected_placeholders:
            assert placeholder in text, (
                f"providers.example.yaml missing expected env placeholder: {placeholder}"
            )


class TestPublicImports:
    def test_fund_agent_public_imports_work(self):
        from fund_agent.version import __version__
        assert __version__ == EXPECTED_VERSION

    def test_src_fund_agent_compat_imports_work(self):
        from src.fund_agent.version import __version__
        assert __version__ == EXPECTED_VERSION


class TestNoStaleVersionReferences:
    def test_install_docs_no_stale_v110_current_claims(self):
        install_docs = [
            ROOT / "docs" / "install" / "opencode.md",
            ROOT / "docs" / "install" / "runtime-bridge-cli.md",
            ROOT / "docs" / "install" / "manual-host.md",
            ROOT / "docs" / "install" / "codex.md",
        ]
        for path in install_docs:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in [
                r"v1\.1\.0",
                r"clone --branch v1\.1\.0",
                r"checkout v1\.1\.0",
            ]:
                assert not re.search(pattern, text), (
                    f"{path} contains stale v1.1.0 reference"
                )
