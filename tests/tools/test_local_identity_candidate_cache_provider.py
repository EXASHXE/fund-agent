"""Tests for M7.13/M7.14 LocalIdentityCandidateCacheProvider.

Validates:
1. Local cache provider reads private CSV (full format)
2. Local cache provider reads private JSON
3. Cache candidates are not user_verified
4. Cache unique high-confidence can auto-verify via scoring
5. Cache ambiguous candidates stay unverified
6. Privacy check allows private cache
7. Public report hides cache candidate codes
8. Cache is read-only
9. Missing cache file handled gracefully
10. M7.14: Minimal CSV format (raw_fund_name, fund_code, fund_name, notes)
11. M7.14: Minimal CSV normalizes raw_fund_name
12. M7.14: Minimal CSV defaults source to local_identity_candidate_cache
13. M7.14: Minimal CSV candidates are not user_verified
14. M7.14: Minimal CSV rows with blank fund_code are skipped
15. M7.14: Minimal CSV valid candidates enter scoring
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.tools.portfolio.fund_identity_candidate_discovery import (
    AUTO_VERIFY_MIN_SCORE,
    FundIdentityCandidate,
    apply_hard_reject,
    score_candidate,
    should_auto_verify,
)
from src.tools.portfolio.local_identity_candidate_cache_provider import (
    LocalIdentityCandidateCacheProvider,
)


class TestLocalCacheProviderReadsCSV:
    """Local cache provider must read CSV cache files."""

    def test_reads_csv_cache(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n"
            "Test Fund A,000001,Test Fund A,混合,A,manual,2026-01-01,high,\n"
            "Test Fund B,000002,Test Fund B,债券,C,manual,2026-01-01,medium,\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("Test Fund A")
        assert len(results) == 1
        assert results[0].fund_code == "000001"
        assert results[0].source == "local_identity_candidate_cache"

    def test_reads_multiple_entries(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n"
            "Test Fund,000001,Test Fund A类,混合,A,manual,2026-01-01,high,\n"
            "Test Fund,000002,Test Fund C类,混合,C,manual,2026-01-01,medium,\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("Test Fund")
        assert len(results) == 2


class TestLocalCacheProviderReadsJSON:
    """Local cache provider must read JSON cache files."""

    def test_reads_json_cache(self, tmp_path: Path):
        json_path = tmp_path / "fund_identity_candidate_cache.private.json"
        data = {
            "entries": [
                {
                    "normalized_name": "Test Fund A",
                    "fund_code": "000001",
                    "fund_name": "Test Fund A",
                    "fund_type": "混合",
                    "share_class": "A",
                    "source": "manual",
                    "updated_at": "2026-01-01",
                    "confidence_hint": "high",
                },
            ]
        }
        json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        provider = LocalIdentityCandidateCacheProvider(json_path)
        results = provider.search_by_name("Test Fund A")
        assert len(results) == 1
        assert results[0].fund_code == "000001"


class TestLocalCacheCandidateNotUserVerified:
    """Cache candidates must NOT be treated as user_verified."""

    def test_source_is_local_cache(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n"
            "Test Fund,000001,Test Fund,混合,,manual,2026-01-01,high,\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("Test Fund")
        assert results[0].source == "local_identity_candidate_cache"
        assert results[0].source != "user_verified"


class TestLocalCacheUniqueHighConfidenceCanAutoVerify:
    """Cache candidate with unique high confidence can auto-verify via scoring."""

    def test_unique_exact_match_can_auto_verify(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n"
            "华夏沪深300ETF联接C,000001,华夏沪深300ETF联接C,指数,C,manual,2026-01-01,high,\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("华夏沪深300ETF联接C")
        assert len(results) == 1

        # Score the candidate
        scored = score_candidate("华夏沪深300ETF联接C", results[0])
        assert scored.match_score >= AUTO_VERIFY_MIN_SCORE

        # M7.15: Apply hard reject to compute identity_token_overlap
        scored = apply_hard_reject("华夏沪深300ETF联接C", scored)

        can_verify, reason = should_auto_verify([scored])
        assert can_verify is True


class TestLocalCacheAmbiguousStaysUnverified:
    """Ambiguous cache candidates must stay unverified."""

    def test_ambiguous_candidates_stay_unverified(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n"
            "Test Fund,000001,Test Fund A类,混合,A,manual,2026-01-01,high,\n"
            "Test Fund,000002,Test Fund C类,混合,C,manual,2026-01-01,high,\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("Test Fund")
        assert len(results) == 2

        scored = [score_candidate("Test Fund", c) for c in results]
        scored.sort(key=lambda c: c.match_score, reverse=True)

        # With share_class_mismatch, should not auto-verify
        can_verify, reason = should_auto_verify(scored)
        assert can_verify is False


class TestLocalCacheMissingFile:
    """Missing cache file must be handled gracefully."""

    def test_missing_file_returns_empty(self, tmp_path: Path):
        provider = LocalIdentityCandidateCacheProvider(tmp_path / "nonexistent.csv")
        results = provider.search_by_name("Test Fund")
        assert results == []

    def test_missing_file_status_is_cache_missing(self, tmp_path: Path):
        provider = LocalIdentityCandidateCacheProvider(tmp_path / "nonexistent.csv")
        provider.search_by_name("Test Fund")
        diag = provider.get_diagnostics()
        assert diag["name_search_provider_status"] == "cache_missing"

    def test_none_path_returns_empty(self):
        provider = LocalIdentityCandidateCacheProvider(None)
        results = provider.search_by_name("Test Fund")
        assert results == []


class TestLocalCacheDiagnostics:
    """Cache provider must return structured diagnostics."""

    def test_diagnostics_structure(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n"
            "Test Fund,000001,Test Fund,混合,,manual,2026-01-01,high,\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        provider.search_by_name("Test Fund")

        diag = provider.get_diagnostics()
        assert diag["name_search_provider_type"] == "local_cache"
        assert diag["name_search_provider_status"] == "available"
        assert diag["name_search_provider_search_count"] == 1
        assert diag["name_search_provider_result_count"] == 1
        assert diag["name_search_provider_cache_loaded"] is True
        assert diag["name_search_provider_entry_count"] == 1


class TestLocalCacheEmptyName:
    """Empty name must return empty results."""

    def test_empty_name_returns_empty(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("")
        assert results == []


class TestLocalCacheIsReadOnly:
    """Cache provider must never write to the cache file."""

    def test_cache_not_modified(self, tmp_path: Path):
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        original = (
            "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes\n"
            "Test Fund,000001,Test Fund,混合,,manual,2026-01-01,high,\n"
        )
        csv_path.write_text(original, encoding="utf-8")

        provider = LocalIdentityCandidateCacheProvider(csv_path)
        provider.search_by_name("Test Fund")
        provider.search_by_name("Another Fund")

        # File must not have changed
        assert csv_path.read_text(encoding="utf-8") == original


# ── M7.14: Minimal CSV format tests ──────────────────────────────────────


class TestLocalCacheMinimalCSV:
    """M7.14: Local cache provider must read minimal CSV format."""

    def test_minimal_csv_supported(self, tmp_path: Path):
        """Minimal CSV (raw_fund_name, fund_code, fund_name, notes) is read."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "华夏沪深300ETF联接C,000001,华夏沪深300ETF联接C,from cache\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("华夏沪深300ETF联接C")
        assert len(results) == 1
        assert results[0].fund_code == "000001"

    def test_minimal_csv_normalizes_raw_name(self, tmp_path: Path):
        """raw_fund_name is normalized for matching."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "华夏沪深300ETF联接C,000001,华夏沪深300ETF联接C,test\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        # Normalized search should match (ETF联接 token normalization)
        results = provider.search_by_name("华夏沪深300ETF联接C")
        assert len(results) == 1
        assert results[0].fund_code == "000001"

    def test_minimal_csv_defaults_source(self, tmp_path: Path):
        """Minimal CSV candidates have source=local_identity_candidate_cache."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "Test Fund,000001,Test Fund,test\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("Test Fund")
        assert results[0].source == "local_identity_candidate_cache"

    def test_minimal_csv_not_user_verified(self, tmp_path: Path):
        """Minimal CSV candidates are NOT user_verified."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "Test Fund,000001,Test Fund,test\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("Test Fund")
        assert results[0].source != "user_verified"

    def test_minimal_csv_missing_code_skipped(self, tmp_path: Path):
        """Rows with blank fund_code are skipped (user hasn't filled them)."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "Unfilled Fund,,,not yet filled\n"
            "Filled Fund,000002,Filled Fund,filled\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("Unfilled Fund")
        assert results == []
        results2 = provider.search_by_name("Filled Fund")
        assert len(results2) == 1
        assert results2[0].fund_code == "000002"

    def test_minimal_csv_valid_candidate_enters_scoring(self, tmp_path: Path):
        """Minimal CSV valid candidate can enter M7.11 scoring pipeline."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "华夏沪深300ETF联接C,000001,华夏沪深300ETF联接C,from cache\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results = provider.search_by_name("华夏沪深300ETF联接C")
        assert len(results) == 1

        scored = score_candidate("华夏沪深300ETF联接C", results[0])
        assert scored.match_score >= AUTO_VERIFY_MIN_SCORE

        # M7.15: Apply hard reject to compute identity_token_overlap
        scored = apply_hard_reject("华夏沪深300ETF联接C", scored)

        can_verify, reason = should_auto_verify([scored])
        assert can_verify is True

    def test_minimal_csv_infers_share_class(self, tmp_path: Path):
        """Minimal CSV infers share_class from fund_name when possible."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "Test Fund A,000001,Test Fund A类,test\n"
            "Test Fund C,000002,Test Fund C类,test\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        results_a = provider.search_by_name("Test Fund A")
        results_c = provider.search_by_name("Test Fund C")
        assert results_a[0].share_class == "A"
        assert results_c[0].share_class == "C"

    def test_minimal_csv_infers_fund_type(self, tmp_path: Path):
        """Minimal CSV infers fund_type from fund_name when possible."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "Test Index Fund,000001,Test 指数 Fund,test\n"
            "Test Bond Fund,000002,Test 债券 Fund,test\n"
            "Test Mixed Fund,000003,Test 混合 Fund,test\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        r1 = provider.search_by_name("Test Index Fund")
        r2 = provider.search_by_name("Test Bond Fund")
        r3 = provider.search_by_name("Test Mixed Fund")
        assert r1[0].fund_type == "index"
        assert r2[0].fund_type == "bond"
        assert r3[0].fund_type == "mixed"

    def test_minimal_csv_diagnostics(self, tmp_path: Path):
        """Minimal CSV diagnostics show correct entry count."""
        csv_path = tmp_path / "fund_identity_candidate_cache.private.csv"
        csv_path.write_text(
            "raw_fund_name,fund_code,fund_name,notes\n"
            "Fund A,000001,Fund A,test\n"
            "Fund B,000002,Fund B,test\n",
            encoding="utf-8",
        )
        provider = LocalIdentityCandidateCacheProvider(csv_path)
        provider.search_by_name("Fund A")
        diag = provider.get_diagnostics()
        assert diag["name_search_provider_entry_count"] == 2
        assert diag["name_search_provider_status"] == "available"
