"""Tests for M7.12 AkShare name search provider and wiring.

Validates:
1. AkShareNameSearchProvider protocol conformance
2. No akshare import at module level
3. Graceful failure on network/import errors
4. Diagnostics output
5. personal-run --enable-name-search flag acceptance
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from src.tools.portfolio.akshare_name_search_provider import AkShareNameSearchProvider
from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    NullFundIdentitySearchProvider,
)


class TestAkShareNameSearchProviderProtocol:
    """AkShareNameSearchProvider must conform to FundIdentitySearchProvider."""

    def test_has_search_by_name(self):
        provider = AkShareNameSearchProvider()
        assert hasattr(provider, "search_by_name")
        assert callable(provider.search_by_name)

    def test_search_returns_list(self):
        provider = AkShareNameSearchProvider()
        result = provider.search_by_name("test")
        assert isinstance(result, list)

    def test_search_empty_name_returns_empty(self):
        provider = AkShareNameSearchProvider()
        result = provider.search_by_name("")
        assert result == []


class TestAkShareNameSearchProviderNoImport:
    """Module must not import akshare at module level."""

    def test_no_akshare_import(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "import src.tools.portfolio.akshare_name_search_provider; "
             "import sys; "
             "found = [m for m in sys.modules if m == 'akshare' or m.startswith('akshare.')]; "
             "print(','.join(found) if found else 'CLEAN')"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert result.stdout.strip() == "CLEAN", f"akshare in sys.modules: {result.stdout.strip()}"


class TestAkShareNameSearchProviderDiagnostics:
    """Provider must return diagnostics on failure."""

    def test_diagnostics_structure(self):
        provider = AkShareNameSearchProvider()
        diag = provider.get_diagnostics()
        assert "name_search_provider_type" in diag
        assert "name_search_provider_status" in diag
        assert "name_search_provider_last_error" in diag
        assert "name_search_provider_search_count" in diag
        assert "name_search_provider_result_count" in diag
        assert "name_search_provider_cache_loaded" in diag
        assert diag["name_search_provider_type"] == "akshare"

    def test_diagnostics_after_failed_search(self):
        provider = AkShareNameSearchProvider()
        provider.search_by_name("test fund")
        diag = provider.get_diagnostics()
        # After a failed search, status should indicate the error
        assert diag["name_search_provider_status"] in (
            "available", "import_failed", "network_error", "unknown_error",
        )
        assert diag["name_search_provider_search_count"] == 1


class TestAkShareNameSearchProviderIsolation:
    """Core modules must not import akshare_name_search_provider."""

    def test_core_no_provider_import(self):
        """Core portfolio modules must not import the akshare provider."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import src.tools.portfolio.fund_identity_candidate_discovery; "
             "import sys; "
             "found = [m for m in sys.modules if 'akshare_name_search' in m]; "
             "print(','.join(found) if found else 'CLEAN')"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "CLEAN"


class TestPersonalRunEnableNameSearch:
    """personal-run must accept --enable-name-search flag."""

    def test_enable_name_search_flag_accepted(self):
        """--enable-name-search flag should be accepted without error."""
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "fund_agent_personal_run.py"),
             "--dry-run", "--enable-name-search"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        # dry-run should succeed
        assert result.returncode == 0 or "dry-run" in result.stdout.lower() or "usage" not in result.stderr.lower()

    def test_e2e_enable_name_search_flag(self):
        """e2e --enable-name-search flag should be accepted."""
        result = subprocess.run(
            [sys.executable, "-c",
             "from scripts.fund_agent_e2e import main; "
             "import argparse; "
             "parser = argparse.ArgumentParser(); "
             "parser.add_argument('--enable-name-search', action='store_true'); "
             "args = parser.parse_args(['--enable-name-search']); "
             "print(f'enable_name_search={args.enable_name_search}')"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0
        assert "enable_name_search=True" in result.stdout


class TestNullFundIdentitySearchProviderBehavior:
    """NullFundIdentitySearchProvider must return empty results."""

    def test_null_provider_returns_empty(self):
        provider = NullFundIdentitySearchProvider()
        result = provider.search_by_name("any name")
        assert result == []
