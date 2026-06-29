"""Tests for M7.10 acceptance gate: provider import isolation.

Validates that:
1. provider_identity_cross_check uses lazy/injected provider (no core import of akshare)
2. core import path does not import akshare
3. no_provider_imports check is order-independent (subprocess isolation)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestProviderCrossCheckUsesLazyProviderImport:
    """provider_identity_cross_check must not import akshare at module level."""

    def test_provider_module_no_akshare_import(self):
        """Importing provider_identity_cross_check must not bring in akshare."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import src.tools.portfolio.provider_identity_cross_check; "
             "import sys; "
             "found = [m for m in sys.modules if 'akshare' in m]; "
             "print(','.join(found) if found else 'CLEAN')"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert result.stdout.strip() == "CLEAN", f"akshare in sys.modules: {result.stdout.strip()}"

    def test_provider_module_uses_injected_fund_name_provider(self):
        """The module must accept an injected FundNameProvider, not import one."""
        from src.tools.portfolio.provider_identity_cross_check import (
            FundNameProvider,
            NullFundNameProvider,
            provider_cross_check,
        )
        # NullFundNameProvider should be the default (no external deps)
        provider = NullFundNameProvider()
        result = provider_cross_check(
            raw_fund_name="Test Fund",
            candidate_fund_code="000001",
            provider=provider,
        )
        # Should not crash, just return a result
        assert isinstance(result, dict)


class TestCoreImportDoesNotImportAkshare:
    """Core portfolio modules must not import akshare."""

    @pytest.mark.parametrize("module_path", [
        "src.tools.portfolio.valuation_source_model",
        "src.tools.portfolio.transaction_derived_reconstruction",
        "src.tools.portfolio.agent_context",
        "src.tools.portfolio.personal_health_report",
        "src.tools.portfolio.trade_date_rules",
    ])
    def test_core_module_no_akshare(self, module_path: str):
        """Importing each core module must not bring in akshare."""
        result = subprocess.run(
            [sys.executable, "-c",
             f"import {module_path}; "
             "import sys; "
             "found = [m for m in sys.modules if 'akshare' in m]; "
             "print(','.join(found) if found else 'CLEAN')"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert result.stdout.strip() == "CLEAN", f"akshare in sys.modules from {module_path}: {result.stdout.strip()}"


class TestNoProviderImportsOrderIndependent:
    """The no-provider-imports check must be order-independent."""

    def test_no_provider_imports_in_fresh_process(self):
        """Check provider imports in an isolated subprocess (order-independent)."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import src.tools.research.query_plan; "
             "import sys; "
             "forbidden = ('tavily','finnhub','exa','firecrawl','akshare','openai','anthropic'); "
             "found = [m for m in sys.modules if any(f in m for f in forbidden)]; "
             "print(','.join(found) if found else 'CLEAN')"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "CLEAN", f"Provider modules found: {result.stdout.strip()}"
