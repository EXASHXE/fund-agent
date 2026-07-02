"""Tests for M7.20 provider contracts.

Validates:
1. core_does_not_import_online_provider
2. provider_contracts_are_injected
3. provider_failure_does_not_crash_analysis
4. multisource_same_code_can_boost_confidence
5. fuzzy_provider_result_never_auto_verifies
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.provider_contracts import (
    FailingProvider,
    ProviderDiagnostics,
    SkeletonFundProfileProvider,
    SkeletonFundUniverseProvider,
    SkeletonNAVProvider,
    compute_multisource_confidence,
)


class TestCoreDoesNotImportOnlineProvider:
    """Core modules must not import online provider implementations."""

    def test_current_holding_discovery_no_online_import(self):
        """current_holding_discovery.py must not import any online provider."""
        import src.tools.portfolio.current_holding_discovery as mod
        source = open(mod.__file__, encoding="utf-8").read()
        online_keywords = ["akshare", "tushare", "eastmoney", "tiantian", "requests", "aiohttp"]
        for kw in online_keywords:
            assert kw not in source.lower(), f"Found online keyword '{kw}' in current_holding_discovery"

    def test_pre_valuation_readiness_no_online_import(self):
        """pre_valuation_readiness.py must not import any online provider."""
        import src.tools.portfolio.pre_valuation_readiness as mod
        source = open(mod.__file__, encoding="utf-8").read()
        online_keywords = ["akshare", "tushare", "eastmoney", "tiantian", "requests", "aiohttp"]
        for kw in online_keywords:
            assert kw not in source.lower(), f"Found online keyword '{kw}' in pre_valuation_readiness"


class TestProviderContractsAreInjected:
    """Provider contracts must be injectable (not hardcoded)."""

    def test_skeleton_universe_provider(self):
        provider = SkeletonFundUniverseProvider("test_universe")
        result = provider.lookup_by_name("某基金")
        assert result == []
        diag = provider.get_diagnostics()
        assert diag.provider_name == "test_universe"
        assert diag.request_count == 1
        assert diag.success_count == 1

    def test_skeleton_nav_provider(self):
        provider = SkeletonNAVProvider("test_nav")
        result = provider.get_latest_nav("110011")
        assert result is None
        diag = provider.get_diagnostics()
        assert diag.request_count == 1

    def test_skeleton_profile_provider(self):
        provider = SkeletonFundProfileProvider("test_profile")
        result = provider.get_profile("110011")
        assert result is None
        diag = provider.get_diagnostics()
        assert diag.request_count == 1


class TestProviderFailureDoesNotCrashAnalysis:
    """Provider failures must not crash analysis."""

    def test_failing_provider_records_failure(self):
        provider = FailingProvider("failing_test", "network_error")
        result = provider.lookup_by_name("某基金")
        assert result == []
        diag = provider.get_diagnostics()
        assert diag.failure_count == 1
        assert diag.last_error_type == "network_error"

    def test_failing_nav_provider(self):
        provider = FailingProvider("failing_nav", "timeout")
        result = provider.get_latest_nav("110011")
        assert result is None
        diag = provider.get_diagnostics()
        assert diag.failure_count == 1

    def test_failing_profile_provider(self):
        provider = FailingProvider("failing_profile", "auth_error")
        result = provider.get_profile("110011")
        assert result is None
        diag = provider.get_diagnostics()
        assert diag.failure_count == 1


class TestMultisourceSameCodeCanBoostConfidence:
    """Multiple sources agreeing on same code can boost confidence."""

    def test_single_exact_match_high(self):
        sources = [{"fund_code": "110011", "match_type": "exact"}]
        confidence = compute_multisource_confidence(sources)
        assert confidence == "high"

    def test_two_exact_matches_boosted(self):
        sources = [
            {"fund_code": "110011", "match_type": "exact"},
            {"fund_code": "110011", "match_type": "exact"},
        ]
        confidence = compute_multisource_confidence(sources)
        assert confidence == "high_boosted"

    def test_two_different_exact_codes_still_high(self):
        sources = [
            {"fund_code": "110011", "match_type": "exact"},
            {"fund_code": "110012", "match_type": "exact"},
        ]
        confidence = compute_multisource_confidence(sources)
        assert confidence == "high_boosted"

    def test_single_fuzzy_match_medium(self):
        sources = [{"fund_code": "110011", "match_type": "fuzzy"}]
        confidence = compute_multisource_confidence(sources)
        assert confidence == "medium"

    def test_two_fuzzy_same_code_boosted(self):
        sources = [
            {"fund_code": "110011", "match_type": "fuzzy"},
            {"fund_code": "110011", "match_type": "fuzzy"},
        ]
        confidence = compute_multisource_confidence(sources)
        assert confidence == "medium_boosted"

    def test_no_sources_low(self):
        confidence = compute_multisource_confidence([])
        assert confidence == "low"


class TestFuzzyProviderResultNeverAutoVerifies:
    """Fuzzy top-1 results from any provider must NOT auto-verify."""

    def test_fuzzy_confidence_is_not_high(self):
        """Fuzzy match confidence must never be 'high' or 'high_boosted'."""
        sources = [{"fund_code": "110011", "match_type": "fuzzy"}]
        confidence = compute_multisource_confidence(sources)
        assert "high" not in confidence

    def test_fuzzy_boosted_still_not_high(self):
        """Even boosted fuzzy is 'medium_boosted', not 'high'."""
        sources = [
            {"fund_code": "110011", "match_type": "fuzzy"},
            {"fund_code": "110011", "match_type": "fuzzy"},
        ]
        confidence = compute_multisource_confidence(sources)
        assert confidence == "medium_boosted"
        assert "high" not in confidence


class TestProviderDiagnostics:
    """Provider diagnostics tracking."""

    def test_record_success(self):
        diag = ProviderDiagnostics(provider_name="test")
        diag.record_success()
        assert diag.request_count == 1
        assert diag.success_count == 1
        assert diag.failure_count == 0

    def test_record_failure(self):
        diag = ProviderDiagnostics(provider_name="test")
        diag.record_failure("timeout")
        assert diag.request_count == 1
        assert diag.failure_count == 1
        assert diag.last_error_type == "timeout"

    def test_to_dict(self):
        diag = ProviderDiagnostics(provider_name="test", loaded=True)
        d = diag.to_dict()
        assert d["provider_name"] == "test"
        assert d["loaded"] is True
