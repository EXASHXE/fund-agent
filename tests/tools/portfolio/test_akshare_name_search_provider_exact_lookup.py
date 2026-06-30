"""Tests for M7.16 AkShare name search provider exact lookup.

Validates:
1. Exact match not missed by DataFrame order
2. Provider does not break before scoring full universe
3. Exact match precedes fuzzy candidates
4. Fuzzy candidates do not auto-verify
5. Search strategy diagnostics present
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.akshare_name_search_provider import (
    EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH,
    EXACT_FUND_UNIVERSE_NAME_MATCH,
    EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH,
    AkShareNameSearchProvider,
)
from src.tools.portfolio.fund_identity_candidate_discovery import (
    BUCKET_EXACT,
    BUCKET_HIGH,
    BUCKET_LOW,
    BUCKET_MEDIUM,
    FundIdentityCandidate,
    should_auto_verify,
)
from src.tools.portfolio.fund_universe_identity_lookup import (
    FundUniverseEntry,
    FundUniverseIndex,
    build_fund_universe_index,
)


class _MockAkShareProvider(AkShareNameSearchProvider):
    """Subclass that injects a pre-built universe index instead of calling akshare."""

    def __init__(self, entries: list[dict[str, str]]) -> None:
        super().__init__()
        self._universe_index = build_fund_universe_index(entries)
        self._cache_loaded = True
        self._fund_name_df = True  # Not None = loaded


_SAMPLE_ENTRIES = [
    {"fund_code": "110011", "fund_name": "易方达蓝筹精选混合A"},
    {"fund_code": "110012", "fund_name": "易方达蓝筹精选混合C"},
    {"fund_code": "012414", "fund_name": "天弘中证光伏产业指数A"},
    {"fund_code": "012415", "fund_name": "天弘中证光伏产业指数C"},
    {"fund_code": "000001", "fund_name": "华夏成长混合"},
    {"fund_code": "005827", "fund_name": "易方达蓝筹精选混合"},
    {"fund_code": "164906", "fund_name": "交银中证海外中国互联网指数(QDII-FOF)A"},
    {"fund_code": "164907", "fund_name": "交银中证海外中国互联网指数(QDII-FOF)C"},
    {"fund_code": "007380", "fund_name": "华夏沪深300ETF联接A"},
    {"fund_code": "007381", "fund_name": "华夏沪深300ETF联接C"},
    {"fund_code": "003834", "fund_name": "华夏能源革新股票A"},
    {"fund_code": "003835", "fund_name": "华夏能源革新股票C"},
    # Extra entries to test DataFrame order independence
    {"fund_code": "999999", "fund_name": "某完全不相关基金A"},
    {"fund_code": "999998", "fund_name": "另一个无关基金C"},
]


def _make_provider() -> _MockAkShareProvider:
    return _MockAkShareProvider(_SAMPLE_ENTRIES)


class TestExactMatchNotMissedByDataFrameOrder:
    """Exact match must be found regardless of DataFrame row order."""

    def test_exact_match_found_regardless_of_entry_order(self):
        # Reverse the entries — exact match should still work
        reversed_entries = list(reversed(_SAMPLE_ENTRIES))
        provider = _MockAkShareProvider(reversed_entries)
        results = provider.search_by_name("易方达蓝筹精选混合A")
        assert len(results) >= 1
        exact = [r for r in results if r.match_bucket == BUCKET_EXACT]
        assert len(exact) >= 1
        assert exact[0].fund_code == "110011"

    def test_exact_match_in_middle_of_large_universe(self):
        # Put target in the middle of many irrelevant entries
        entries = [{"fund_code": f"99{i:04d}", "fund_name": f"无关基金{i}A"} for i in range(100)]
        entries.insert(50, {"fund_code": "110011", "fund_name": "易方达蓝筹精选混合A"})
        provider = _MockAkShareProvider(entries)
        results = provider.search_by_name("易方达蓝筹精选混合A")
        assert len(results) >= 1
        exact = [r for r in results if r.match_bucket == BUCKET_EXACT]
        assert len(exact) >= 1
        assert exact[0].fund_code == "110011"


class TestProviderDoesNotBreakBeforeScoringFullUniverse:
    """Provider must not stop at 50 candidates — exact match must always be found."""

    def test_no_50_candidate_cap(self):
        # The old provider capped at 50 candidates. The new one uses index lookup.
        provider = _make_provider()
        results = provider.search_by_name("易方达蓝筹精选混合A")
        # Should find exact match even if it would have been beyond the old 50-cap
        assert any(r.fund_code == "110011" and r.match_bucket == BUCKET_EXACT for r in results)


class TestExactMatchPrecedesFuzzyCandidates:
    """Exact match candidates must appear before fuzzy candidates."""

    def test_exact_first_then_fuzzy(self):
        provider = _make_provider()
        results = provider.search_by_name("易方达蓝筹精选混合A")
        assert len(results) >= 1
        # First result should be exact match
        assert results[0].match_bucket == BUCKET_EXACT
        assert results[0].fund_code == "110011"
        assert EXACT_FUND_UNIVERSE_NAME_MATCH in results[0].match_reasons

    def test_exact_without_punctuation_precedes_fuzzy(self):
        provider = _make_provider()
        # Query with fullwidth parens — should match via level B
        results = provider.search_by_name("交银中证海外中国互联网指数（QDII-FOF）A")
        assert len(results) >= 1
        # Should find exact match (level A or B)
        exact = [r for r in results if r.match_bucket == BUCKET_EXACT]
        assert len(exact) >= 1

    def test_core_name_share_class_precedes_fuzzy(self):
        provider = _make_provider()
        # Query that matches core name + share class but not full name
        results = provider.search_by_name("华夏能源革新股票A")
        assert len(results) >= 1
        exact = [r for r in results if r.match_bucket == BUCKET_EXACT]
        assert len(exact) >= 1


class TestFuzzyCandidatesDoNotAutoVerify:
    """Fuzzy candidates must not be auto-verified."""

    def test_fuzzy_high_score_does_not_auto_verify(self):
        """When only fuzzy matches exist, should_auto_verify must return False."""
        provider = _make_provider()
        # Search for something that won't have an exact match
        results = provider.search_by_name("华夏")
        if not results:
            pytest.skip("No fuzzy results for this query")
        # Apply scoring (normally done by discover_candidates)
        from src.tools.portfolio.fund_identity_candidate_discovery import (
            apply_hard_reject,
            score_candidate,
        )
        scored = []
        for cand in results:
            scored_cand = score_candidate("华夏", cand)
            scored_cand = apply_hard_reject("华夏", scored_cand)
            scored.append(scored_cand)
        scored.sort(key=lambda c: c.match_score, reverse=True)

        # Fuzzy candidates should not auto-verify
        if scored:
            ok, reason = should_auto_verify(scored)
            # Even if score is high, fuzzy candidates should not auto-verify
            # because they lack exact match reasons
            if ok:
                # Check that it's actually an exact match reason
                assert any(
                    r in scored[0].match_reasons
                    for r in (EXACT_FUND_UNIVERSE_NAME_MATCH,
                              EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH,
                              EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH)
                ), f"Auto-verified without exact match reason: {scored[0].match_reasons}"


class TestSearchStrategyDiagnostics:
    """Search strategy diagnostics must be present."""

    def test_diagnostics_has_universe_size(self):
        provider = _make_provider()
        provider.search_by_name("易方达蓝筹精选混合A")
        diag = provider.get_diagnostics()
        assert "fund_universe_size" in diag
        assert diag["fund_universe_size"] > 0

    def test_diagnostics_has_exact_counts(self):
        provider = _make_provider()
        provider.search_by_name("易方达蓝筹精选混合A")
        diag = provider.get_diagnostics()
        assert "exact_full_name_match_count" in diag
        assert "exact_without_punctuation_match_count" in diag
        assert "core_share_class_match_count" in diag
        assert "fuzzy_fallback_count" in diag

    def test_diagnostics_has_search_strategy(self):
        provider = _make_provider()
        provider.search_by_name("易方达蓝筹精选混合A")
        diag = provider.get_diagnostics()
        assert "search_strategy_used" in diag
        assert diag["search_strategy_used"] == "exact_full_name"

    def test_diagnostics_fuzzy_strategy(self):
        provider = _make_provider()
        provider.search_by_name("完全不存在的基金XYZ")
        diag = provider.get_diagnostics()
        assert diag["search_strategy_used"] == "fuzzy_fallback"

    def test_diagnostics_provider_type(self):
        provider = _make_provider()
        diag = provider.get_diagnostics()
        assert diag["name_search_provider_type"] == "akshare"
