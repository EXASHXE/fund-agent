"""Clean checkout runtime assumptions tests.

Verifies that a clean source checkout can run the runtime bridge without
requiring user credentials, provider API keys, network env vars, or
local databases. Uses static checks and subprocess smoke commands.
Does not call the network.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class TestManifestResolution:
    def test_default_manifest_path_resolves(self):
        from src.skillpack.run_skill import DEFAULT_MANIFEST_PATH
        manifest_path = ROOT / DEFAULT_MANIFEST_PATH
        assert manifest_path.exists(), (
            f"DEFAULT_MANIFEST_PATH ({DEFAULT_MANIFEST_PATH}) does not resolve"
        )

    def test_manifest_is_valid_yaml(self):
        import yaml
        from src.skillpack.run_skill import DEFAULT_MANIFEST_PATH
        path = ROOT / DEFAULT_MANIFEST_PATH
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "skills" in data
        assert isinstance(data["skills"], list)
        assert len(data["skills"]) == 5

    def test_contract_yamls_resolvable_from_root(self):
        contract_yamls = [
            "skillpack/capabilities.yaml",
            "skillpack/input-contracts.yaml",
            "skillpack/artifact-contracts.yaml",
            "skillpack/decision-contracts.yaml",
            "skillpack/thesis-contracts.yaml",
        ]
        for relpath in contract_yamls:
            assert (ROOT / relpath).exists(), (
                f"contract YAML {relpath} not resolvable from repo root"
            )

    def test_example_fixtures_resolvable_from_root(self):
        fixture_dirs = [
            "examples/scenarios",
            "examples/decision_support",
            "examples/thesis_generation",
        ]
        for relpath in fixture_dirs:
            d = ROOT / relpath
            assert d.is_dir(), f"{relpath}/ not resolvable from repo root"
            jsons = list(d.glob("*.json"))
            assert jsons, f"{relpath}/ has no JSON fixtures"


class TestNoRequiredEnvVars:
    FORBIDDEN_ENV_VARS = [
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "FINNHUB_API_KEY",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "REDDIT_CLIENT_ID",
        "AKSHARE_ENABLED",
    ]

    @pytest.mark.parametrize("env_var", FORBIDDEN_ENV_VARS)
    def test_runtime_bridge_does_not_read_provider_env_vars(self, env_var):
        import ast
        run_skill_path = ROOT / "src" / "skillpack" / "run_skill.py"
        source = run_skill_path.read_text(encoding="utf-8")
        assert f"os.environ[{env_var!r}]" not in source, (
            f"run_skill.py must not read {env_var} from os.environ"
        )
        assert f"os.getenv({env_var!r})" not in source, (
            f"run_skill.py must not read {env_var} via os.getenv"
        )

    def test_runtime_bridge_does_not_import_os_environ_directly(self):
        run_skill_path = ROOT / "src" / "skillpack" / "run_skill.py"
        source = run_skill_path.read_text(encoding="utf-8")
        assert "os.environ" not in source, (
            "run_skill.py must not access os.environ directly"
        )

    def test_runtime_bridge_does_not_import_requests_or_httpx(self):
        run_skill_path = ROOT / "src" / "skillpack" / "run_skill.py"
        source = run_skill_path.read_text(encoding="utf-8")
        for forbidden in ["import requests", "import httpx", "import urllib", "import aiohttp"]:
            assert forbidden not in source, (
                f"run_skill.py must not {forbidden}"
            )


class TestNoCredentialsRequired:
    def test_list_skills_without_credentials(self, monkeypatch):
        for key in [
            "OPENAI_API_KEY", "TAVILY_API_KEY", "FINNHUB_API_KEY",
            "EXA_API_KEY", "FIRECRAWL_API_KEY",
        ]:
            monkeypatch.delenv(key, raising=False)
        from tests.support.bridge_runner import run_bridge_inprocess_metadata
        data = run_bridge_inprocess_metadata(list_skills=True, pretty=True)
        assert data.get("ok") is True

    def test_fund_analysis_without_credentials(self, monkeypatch):
        for key in [
            "OPENAI_API_KEY", "TAVILY_API_KEY", "FINNHUB_API_KEY",
            "EXA_API_KEY", "FIRECRAWL_API_KEY",
        ]:
            monkeypatch.delenv(key, raising=False)
        from tests.support.bridge_runner import run_bridge_inprocess_json
        input_text = (ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json").read_text(encoding="utf-8")
        data = run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text, pretty=True)
        assert data.get("ok") is True


class TestNoLocalDatabaseRequired:
    def test_runtime_bridge_does_not_import_sqlite(self):
        run_skill_path = ROOT / "src" / "skillpack" / "run_skill.py"
        source = run_skill_path.read_text(encoding="utf-8")
        assert "import sqlite" not in source
        assert "import psycopg" not in source
        assert "import pymongo" not in source
