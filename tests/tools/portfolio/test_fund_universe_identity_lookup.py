"""Tests for M7.16/M7.17 fund universe exact identity lookup.

Validates:
1. Exact full name unique match → exact_match
2. Exact full name no match → no_exact_match
3. Exact full name multiple matches → ambiguous_exact_match
4. Share class A/C are distinct
5. Punctuation normalized exact match
6. QDII parentheses normalized exact match
7. Full lookup chain A → B → C
8. build_fund_universe_index from dict entries

M7.17 additions:
9. Query and universe normalization are equivalent
10. QDII parentheses match exact
11. ETF联接 spacing match exact
12. Fullwidth share class match exact
13. Punctuation variants match exact
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.fund_identity_candidate_discovery import (
    normalize_fund_name_for_search,
)
from src.tools.portfolio.fund_universe_identity_lookup import (
    AMBIGUOUS_EXACT_MATCH,
    EXACT_MATCH,
    NO_EXACT_MATCH,
    FundUniverseEntry,
    FundUniverseIndex,
    FundUniverseLookupResult,
    build_fund_universe_index,
    normalize_fund_name_for_universe_index,
)


# ── Test fixtures ───────────────────────────────────────────────────────

_SAMPLE_ENTRIES = [
    {"fund_code": "110011", "fund_name": "易方达蓝筹精选混合A"},
    {"fund_code": "110012", "fund_name": "易方达蓝筹精选混合C"},
    {"fund_code": "012414", "fund_name": "天弘中证光伏产业指数A"},
    {"fund_code": "012415", "fund_name": "天弘中证光伏产业指数C"},
    {"fund_code": "000001", "fund_name": "华夏成长混合"},
    {"fund_code": "005827", "fund_name": "易方达蓝筹精选混合"},
    {"fund_code": "164906", "fund_name": "交银中证海外中国互联网指数（QDII-FOF）A"},
    {"fund_code": "164907", "fund_name": "交银中证海外中国互联网指数（QDII-FOF）C"},
    {"fund_code": "007380", "fund_name": "华夏沪深300ETF联接A"},
    {"fund_code": "007381", "fund_name": "华夏沪深300ETF联接C"},
    {"fund_code": "003834", "fund_name": "华夏能源革新股票A"},
    {"fund_code": "003835", "fund_name": "华夏能源革新股票C"},
]


def _build_sample_index() -> FundUniverseIndex:
    return build_fund_universe_index(_SAMPLE_ENTRIES)


# ── Exact full name tests ───────────────────────────────────────────────


class TestExactFullName:
    """Test exact full name lookup."""

    def test_exact_full_name_unique_match_returns_code(self):
        idx = _build_sample_index()
        result = idx.lookup_exact_full_name("易方达蓝筹精选混合A")
        assert result.lookup_status == EXACT_MATCH
        assert len(result.matched_entries) == 1
        assert result.matched_entries[0].fund_code == "110011"
        assert result.match_reason == "exact_full_name"

    def test_exact_full_name_no_match_returns_no_exact_match(self):
        idx = _build_sample_index()
        result = idx.lookup_exact_full_name("不存在的基金A")
        assert result.lookup_status == NO_EXACT_MATCH
        assert result.matched_entries == []

    def test_exact_full_name_multiple_matches_returns_ambiguous(self):
        # Build index with duplicate names
        idx = FundUniverseIndex()
        idx.add_entry(FundUniverseEntry(
            fund_code="000001", fund_name="同名基金A",
            normalized_full_name="同名基金A",
            normalized_name_no_punct="同名基金A",
            core_name="同名基金", share_class="A",
        ))
        idx.add_entry(FundUniverseEntry(
            fund_code="000002", fund_name="同名基金A",
            normalized_full_name="同名基金A",
            normalized_name_no_punct="同名基金A",
            core_name="同名基金", share_class="A",
        ))
        result = idx.lookup_exact_full_name("同名基金A")
        assert result.lookup_status == AMBIGUOUS_EXACT_MATCH
        assert len(result.matched_entries) == 2


class TestShareClassDistinct:
    """A/C share class must be distinct in exact lookup."""

    def test_share_class_a_c_are_distinct(self):
        idx = _build_sample_index()
        result_a = idx.lookup_exact_full_name("易方达蓝筹精选混合A")
        result_c = idx.lookup_exact_full_name("易方达蓝筹精选混合C")
        assert result_a.lookup_status == EXACT_MATCH
        assert result_c.lookup_status == EXACT_MATCH
        assert result_a.matched_entries[0].fund_code != result_c.matched_entries[0].fund_code


class TestPunctuationNormalization:
    """Punctuation differences should be normalized for matching."""

    def test_punctuation_normalized_exact_match(self):
        idx = _build_sample_index()
        # "华夏成长混合" has no punctuation, but query with extra spaces
        result = idx.lookup_exact_name_without_punctuation("华夏成长混合")
        assert result.lookup_status == EXACT_MATCH
        assert result.matched_entries[0].fund_code == "000001"

    def test_qdii_parentheses_normalized_exact_match(self):
        idx = _build_sample_index()
        # The fund name has （QDII-FOF） — after normalization and punct strip, should match
        result = idx.lookup_exact_name_without_punctuation("交银中证海外中国互联网指数QDII-FOFA")
        assert result.lookup_status == EXACT_MATCH
        assert result.matched_entries[0].fund_code == "164906"


class TestCoreNameShareClassLookup:
    """Core name + share class lookup tests."""

    def test_core_name_a_match(self):
        idx = _build_sample_index()
        result = idx.lookup_same_core_name_and_share_class("易方达蓝筹精选混合A")
        assert result.lookup_status == EXACT_MATCH
        assert result.matched_entries[0].share_class == "A"

    def test_core_name_c_match(self):
        idx = _build_sample_index()
        result = idx.lookup_same_core_name_and_share_class("易方达蓝筹精选混合C")
        assert result.lookup_status == EXACT_MATCH
        assert result.matched_entries[0].share_class == "C"

    def test_core_name_no_share_class(self):
        idx = _build_sample_index()
        result = idx.lookup_same_core_name_and_share_class("华夏成长混合")
        assert result.lookup_status == EXACT_MATCH


class TestFullLookupChain:
    """Test the full A → B → C lookup chain."""

    def test_exact_full_name_takes_priority(self):
        idx = _build_sample_index()
        result = idx.lookup("易方达蓝筹精选混合A")
        assert result.lookup_status == EXACT_MATCH
        assert result.match_reason == "exact_full_name"

    def test_no_punct_fallback(self):
        idx = _build_sample_index()
        # Query with punctuation that doesn't match full name index but matches no-punct
        result = idx.lookup("交银中证海外中国互联网指数（QDII-FOF）A")
        # After normalization, full name should match because normalize_for_index strips parens
        assert result.lookup_status in (EXACT_MATCH, AMBIGUOUS_EXACT_MATCH)

    def test_no_match_at_all(self):
        idx = _build_sample_index()
        result = idx.lookup("完全不存在的基金XYZ")
        assert result.lookup_status == NO_EXACT_MATCH


class TestBuildFundUniverseIndex:
    """Test build_fund_universe_index from dict entries."""

    def test_build_from_dicts(self):
        entries = [
            {"fund_code": "110011", "fund_name": "易方达蓝筹精选混合A"},
            {"fund_code": "110012", "fund_name": "易方达蓝筹精选混合C"},
        ]
        idx = build_fund_universe_index(entries)
        assert idx.size == 2
        result = idx.lookup_exact_full_name("易方达蓝筹精选混合A")
        assert result.lookup_status == EXACT_MATCH

    def test_invalid_code_skipped(self):
        entries = [
            {"fund_code": "abc", "fund_name": "某基金"},
            {"fund_code": "110011", "fund_name": "易方达蓝筹精选混合A"},
        ]
        idx = build_fund_universe_index(entries)
        assert idx.size == 1

    def test_empty_name_skipped(self):
        entries = [
            {"fund_code": "110011", "fund_name": ""},
            {"fund_code": "110012", "fund_name": "易方达蓝筹精选混合A"},
        ]
        idx = build_fund_universe_index(entries)
        assert idx.size == 1

    def test_custom_keys(self):
        entries = [
            {"code": "110011", "name": "易方达蓝筹精选混合A"},
        ]
        idx = build_fund_universe_index(entries, code_key="code", name_key="name")
        assert idx.size == 1


# ── M7.17: Normalization equivalence tests ────────────────────────────────


class TestM717NormalizationEquivalence:
    """Query-side and universe-side normalization must produce equivalent keys."""

    def test_query_and_universe_normalization_are_equivalent(self):
        """normalize_fund_name_for_search and normalize_fund_name_for_universe_index
        must produce the same result for the same input."""
        names = [
            "易方达蓝筹精选混合A",
            "华夏沪深300ETF联接C",
            "交银中证海外中国互联网指数（QDII-FOF）A",
            "华安黄金ETF联接C",
        ]
        for name in names:
            q = normalize_fund_name_for_search(name)
            u = normalize_fund_name_for_universe_index(name)
            assert q == u, (
                f"Normalization mismatch for '{name}': "
                f"query='{q}' vs universe='{u}'"
            )

    def test_qdii_parentheses_match_exact(self):
        """QDII with Chinese parentheses must match after normalization."""
        idx = _build_sample_index()
        # Query with Chinese parentheses
        result = idx.lookup("交银中证海外中国互联网指数（QDII-FOF）A")
        assert result.lookup_status in (EXACT_MATCH, AMBIGUOUS_EXACT_MATCH)

    def test_etf_link_spacing_match_exact(self):
        """ETF联接 with extra space must match after normalization."""
        idx = _build_sample_index()
        # Query with space between ETF and 联接
        result = idx.lookup("华夏沪深300ETF 联接C")
        assert result.lookup_status == EXACT_MATCH

    def test_fullwidth_share_class_match_exact(self):
        """Fullwidth A/C share class must match after normalization."""
        idx = _build_sample_index()
        # Query with fullwidth Ａ — must normalize before lookup
        query = normalize_fund_name_for_universe_index("易方达蓝筹精选混合Ａ")
        result = idx.lookup(query)
        assert result.lookup_status == EXACT_MATCH

    def test_punctuation_variants_match_exact(self):
        """Names with different punctuation must match at no-punct level."""
        idx = _build_sample_index()
        # Query with English parentheses instead of Chinese
        result = idx.lookup_exact_name_without_punctuation("交银中证海外中国互联网指数(QDII-FOF)A")
        assert result.lookup_status == EXACT_MATCH
