"""Tests for M7.13 ChainedFundIdentitySearchProvider.

Validates:
1. Chain continues after provider failure (SSL, network, import)
2. Chain uses second provider candidates when first fails
3. Chain merges duplicate candidates from multiple providers
4. Chain preserves provider diagnostics
5. Provider failure does not silently become name_only
6. Multi-source confirmation bonus
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    FundIdentitySearchProvider,
    NullFundIdentitySearchProvider,
)
from src.tools.portfolio.name_search_provider_chain import (
    ChainedFundIdentitySearchProvider,
)


class _FakeSuccessProvider:
    """Fake provider that returns candidates."""

    _provider_name = "fake_success"

    def __init__(self, candidates: list[FundIdentityCandidate] | None = None):
        self._candidates = candidates or []
        self._status = "available"

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        return list(self._candidates)

    def get_diagnostics(self):
        return {
            "name_search_provider_type": "fake_success",
            "name_search_provider_status": self._status,
            "name_search_provider_last_error": "",
        }


class _FakeNetworkErrorProvider:
    """Fake provider that simulates SSL/network failure."""

    _provider_name = "fake_network_error"

    def __init__(self):
        self._status = "network_error"
        self._error = "SSL: CERTIFICATE_VERIFY_FAILED"

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        return []

    def get_diagnostics(self):
        return {
            "name_search_provider_type": "fake_akshare",
            "name_search_provider_status": self._status,
            "name_search_provider_last_error": self._error,
        }


class _FakeExceptionProvider:
    """Fake provider that raises an exception."""

    _provider_name = "fake_exception"

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        raise ConnectionError("Network unreachable")

    def get_diagnostics(self):
        return {
            "name_search_provider_type": "fake_exception",
            "name_search_provider_status": "unknown_error",
        }


class TestChainContinuesAfterFailure:
    """Chain must continue to next provider after a failure."""

    def test_ssl_failure_does_not_terminate_chain(self):
        """When first provider has SSL failure, chain continues to second."""
        candidate = FundIdentityCandidate(
            fund_code="000001", fund_name="Test Fund A",
            source="fake_success",
        )
        chain = ChainedFundIdentitySearchProvider([
            _FakeNetworkErrorProvider(),
            _FakeSuccessProvider([candidate]),
        ])
        results = chain.search_by_name("Test Fund A")
        assert len(results) == 1
        assert results[0].fund_code == "000001"

    def test_exception_does_not_terminate_chain(self):
        """When first provider raises exception, chain continues."""
        candidate = FundIdentityCandidate(
            fund_code="000002", fund_name="Test Fund B",
            source="fake_success",
        )
        chain = ChainedFundIdentitySearchProvider([
            _FakeExceptionProvider(),
            _FakeSuccessProvider([candidate]),
        ])
        results = chain.search_by_name("Test Fund B")
        assert len(results) == 1
        assert results[0].fund_code == "000002"

    def test_all_providers_fail_returns_empty(self):
        """When all providers fail, returns empty list (not exception)."""
        chain = ChainedFundIdentitySearchProvider([
            _FakeNetworkErrorProvider(),
            _FakeExceptionProvider(),
        ])
        results = chain.search_by_name("Test Fund")
        assert results == []


class TestChainUsesSecondProviderCandidates:
    """Chain must use candidates from second provider when first has none."""

    def test_second_provider_candidates_used(self):
        candidate = FundIdentityCandidate(
            fund_code="000003", fund_name="Backup Fund",
            source="fake_success", match_score=0.9,
        )
        chain = ChainedFundIdentitySearchProvider([
            NullFundIdentitySearchProvider(),
            _FakeSuccessProvider([candidate]),
        ])
        results = chain.search_by_name("Backup Fund")
        assert len(results) == 1
        assert results[0].fund_code == "000003"


class TestChainMergesDuplicateCandidates:
    """Chain must merge candidates with same fund_code from different providers."""

    def test_dedup_preserves_first_candidate(self):
        """When two providers return same fund_code, keep first occurrence."""
        cand1 = FundIdentityCandidate(
            fund_code="000001", fund_name="Fund A",
            source="provider1", match_score=0.9,
        )
        cand2 = FundIdentityCandidate(
            fund_code="000001", fund_name="Fund A",
            source="provider2", match_score=0.85,
        )
        chain = ChainedFundIdentitySearchProvider([
            _FakeSuccessProvider([cand1]),
            _FakeSuccessProvider([cand2]),
        ])
        results = chain.search_by_name("Fund A")
        # Should have 1 candidate (deduped)
        assert len(results) == 1
        assert results[0].fund_code == "000001"

    def test_multi_source_bonus(self):
        """Same fund_code from multiple providers gets multi_source bonus."""
        cand1 = FundIdentityCandidate(
            fund_code="000001", fund_name="Fund A",
            source="provider1", match_score=0.9,
        )
        cand2 = FundIdentityCandidate(
            fund_code="000001", fund_name="Fund A",
            source="provider2", match_score=0.85,
        )
        chain = ChainedFundIdentitySearchProvider([
            _FakeSuccessProvider([cand1]),
            _FakeSuccessProvider([cand2]),
        ])
        results = chain.search_by_name("Fund A")
        assert "multi_source_confirmation" in results[0].match_reasons
        assert results[0].match_score >= 0.9  # Bonus added

    def test_different_codes_not_deduped(self):
        """Different fund_codes from different providers are both kept."""
        cand1 = FundIdentityCandidate(
            fund_code="000001", fund_name="Fund A",
            source="provider1", match_score=0.9,
        )
        cand2 = FundIdentityCandidate(
            fund_code="000002", fund_name="Fund B",
            source="provider2", match_score=0.8,
        )
        chain = ChainedFundIdentitySearchProvider([
            _FakeSuccessProvider([cand1]),
            _FakeSuccessProvider([cand2]),
        ])
        results = chain.search_by_name("Fund")
        assert len(results) == 2


class TestChainPreservesProviderDiagnostics:
    """Chain must aggregate diagnostics from all providers."""

    def test_diagnostics_structure(self):
        chain = ChainedFundIdentitySearchProvider([
            _FakeNetworkErrorProvider(),
            _FakeSuccessProvider(),
        ])
        chain.search_by_name("Test")

        diag = chain.get_diagnostics()
        assert diag["provider_chain_enabled"] is True
        assert len(diag["providers_attempted"]) == 2
        assert "fake_network_error" in diag["providers_failed"]
        assert "fake_success" in diag["providers_succeeded"]

    def test_provider_errors_recorded(self):
        chain = ChainedFundIdentitySearchProvider([
            _FakeNetworkErrorProvider(),
        ])
        chain.search_by_name("Test")

        diag = chain.get_diagnostics()
        assert "fake_network_error" in diag["provider_errors_by_name"]
        assert "SSL" in diag["provider_errors_by_name"]["fake_network_error"]

    def test_fallback_used_flag(self):
        """fallback_used is True when a later provider returns results."""
        cand = FundIdentityCandidate(
            fund_code="000001", fund_name="Fund A", source="p2",
        )
        chain = ChainedFundIdentitySearchProvider([
            _FakeSuccessProvider([cand]),
            _FakeSuccessProvider([cand]),
        ])
        chain.search_by_name("Fund A")
        diag = chain.get_diagnostics()
        assert diag["fallback_used"] is True


class TestProviderFailureDoesNotBecomeNameOnly:
    """Provider failure must be structurally recorded, not silent name_only."""

    def test_network_error_in_diagnostics(self):
        chain = ChainedFundIdentitySearchProvider([
            _FakeNetworkErrorProvider(),
        ])
        chain.search_by_name("Test Fund")

        diag = chain.get_diagnostics()
        assert "fake_network_error" in diag["providers_failed"]
        assert len(diag["providers_succeeded"]) == 0

    def test_empty_name_returns_empty(self):
        chain = ChainedFundIdentitySearchProvider([
            _FakeSuccessProvider(),
        ])
        results = chain.search_by_name("")
        assert results == []

    def test_single_provider_chain(self):
        """Chain with one provider works normally."""
        cand = FundIdentityCandidate(
            fund_code="000001", fund_name="Fund A", source="p1",
        )
        chain = ChainedFundIdentitySearchProvider([
            _FakeSuccessProvider([cand]),
        ])
        results = chain.search_by_name("Fund A")
        assert len(results) == 1
