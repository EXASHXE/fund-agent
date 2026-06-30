"""Tests for M7.11 fund identity candidate discovery.

Validates:
1. Name extraction from Alipay raw names
2. Name normalization (fullwidth, QDII, ETF联接, share class)
3. Candidate scoring (9 dimensions)
4. Auto-verify decision logic
5. Discovery orchestrator
6. Discovery summary computation
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.fund_identity_candidate_discovery import (
    AUTO_VERIFY_MIN_MARGIN,
    AUTO_VERIFY_MIN_SCORE,
    BUCKET_AMBIGUOUS,
    BUCKET_EXACT,
    BUCKET_HIGH,
    BUCKET_LOW,
    BUCKET_MEDIUM,
    BUCKET_MISMATCH,
    FundIdentityCandidate,
    NullFundIdentitySearchProvider,
    compute_discovery_summary,
    discover_candidates,
    extract_etf_link_token,
    extract_fund_name_from_alipay_item,
    extract_qdii_token,
    extract_share_class,
    normalize_fund_name_for_search,
    score_candidate,
    should_auto_verify,
)


# ── Name extraction ────────────────────────────────────────────────────


class TestExtractFundNameFromAlipayItem:
    """Test Alipay raw name extraction."""

    def test_simple_buy(self):
        result = extract_fund_name_from_alipay_item("蚂蚁财富-易方达蓝筹精选混合-买入")
        assert result["normalized_name"] == "易方达蓝筹精选混合"
        assert result["extracted_role"] == "primary"
        assert result["conversion_target_name"] is None

    def test_sell(self):
        result = extract_fund_name_from_alipay_item("蚂蚁财富-招商中证白酒指数-卖出至余额宝")
        assert result["normalized_name"] == "招商中证白酒指数"

    def test_conversion(self):
        result = extract_fund_name_from_alipay_item("蚂蚁财富-基金A-[转换至]基金B-转换")
        assert result["extracted_role"] == "conversion_source"
        assert result["conversion_target_name"] == "基金B"

    def test_no_prefix(self):
        result = extract_fund_name_from_alipay_item("易方达蓝筹精选混合-定投")
        assert result["normalized_name"] == "易方达蓝筹精选混合"

    def test_dividend(self):
        result = extract_fund_name_from_alipay_item("蚂蚁财富-天弘余额宝-现金分红至余额宝")
        assert result["normalized_name"] == "天弘余额宝"

    def test_bare_suffix(self):
        result = extract_fund_name_from_alipay_item("蚂蚁财富-某基金定投")
        assert result["normalized_name"] == "某基金"

    def test_empty_input(self):
        result = extract_fund_name_from_alipay_item("")
        assert result["normalized_name"] == ""

    def test_whitespace_input(self):
        result = extract_fund_name_from_alipay_item("  ")
        assert result["normalized_name"] == ""

    def test_share_class_preserved(self):
        result = extract_fund_name_from_alipay_item("蚂蚁财富-易方达蓝筹精选混合A-买入")
        assert "A" in result["normalized_name"]


# ── Name normalization ─────────────────────────────────────────────────


class TestNormalizeFundNameForSearch:
    """Test name normalization for search matching."""

    def test_fullwidth_parentheses(self):
        assert normalize_fund_name_for_search("基金（A类）") == "基金(A类)"

    def test_fullwidth_letters(self):
        assert normalize_fund_name_for_search("基金Ａ类") == "基金A类"

    def test_qdii_normalization(self):
        assert "QDII" in normalize_fund_name_for_search("某QDII基金")

    def test_qdii_fof_normalization(self):
        assert "QDII-FOF" in normalize_fund_name_for_search("某qdii fof基金")

    def test_qdii_lof_normalization(self):
        assert "QDII-LOF" in normalize_fund_name_for_search("某qdii-lof基金")

    def test_etf_link_normalization(self):
        assert "ETF联接" in normalize_fund_name_for_search("沪深300ETF 联接A")

    def test_whitespace_normalization(self):
        result = normalize_fund_name_for_search("基金  A类")
        # Multiple spaces should be collapsed to single space
        assert "  " not in result

    def test_empty_input(self):
        assert normalize_fund_name_for_search("") == ""


# ── Feature extraction ─────────────────────────────────────────────────


class TestExtractShareClass:
    def test_a_class(self):
        assert extract_share_class("易方达蓝筹精选混合A") == "A"

    def test_c_class(self):
        assert extract_share_class("招商中证白酒指数C") == "C"

    def test_e_class(self):
        assert extract_share_class("某基金E") == "E"

    def test_no_class(self):
        assert extract_share_class("易方达蓝筹精选混合") == ""

    def test_empty(self):
        assert extract_share_class("") == ""


class TestExtractQdiiToken:
    def test_qdii(self):
        assert extract_qdii_token("某QDII基金") == "qdii"

    def test_qdii_fof(self):
        assert extract_qdii_token("某QDII-FOF基金") == "qdii-fof"

    def test_qdii_lof(self):
        assert extract_qdii_token("某QDII-LOF基金") == "qdii-lof"

    def test_no_qdii(self):
        assert extract_qdii_token("普通基金") == ""


class TestExtractEtfLinkToken:
    def test_etf_link(self):
        assert extract_etf_link_token("沪深300ETF联接A") == "etf联接"

    def test_no_etf_link(self):
        assert extract_etf_link_token("普通基金") == ""


# ── Candidate scoring ──────────────────────────────────────────────────


class TestScoreCandidate:
    """Test deterministic candidate scoring."""

    def test_exact_match(self):
        cand = FundIdentityCandidate(fund_code="110011", fund_name="易方达蓝筹精选混合A")
        scored = score_candidate("易方达蓝筹精选混合A", cand)
        assert scored.match_bucket == BUCKET_EXACT
        assert scored.match_score == 1.0
        assert "exact_normalized_match" in scored.match_reasons

    def test_near_exact(self):
        cand = FundIdentityCandidate(fund_code="110011", fund_name="易方达蓝筹精选混合A")
        scored = score_candidate("易方达蓝筹精选混合A ", cand)
        # After normalization, should be exact
        assert scored.match_bucket == BUCKET_EXACT

    def test_share_class_mismatch(self):
        cand = FundIdentityCandidate(fund_code="110011", fund_name="易方达蓝筹精选混合C")
        scored = score_candidate("易方达蓝筹精选混合A", cand)
        assert "share_class_mismatch" in scored.risk_flags
        assert scored.match_score < 0.85

    def test_qdii_mismatch(self):
        cand = FundIdentityCandidate(fund_code="000001", fund_name="华夏QDII基金")
        scored = score_candidate("华夏基金", cand)
        assert "candidate_is_qdii_query_is_not" in scored.risk_flags

    def test_etf_link_mismatch(self):
        cand = FundIdentityCandidate(fund_code="000001", fund_name="沪深300ETF联接A")
        scored = score_candidate("沪深300A", cand)
        assert "candidate_is_etf_link_query_is_not" in scored.risk_flags

    def test_empty_names(self):
        cand = FundIdentityCandidate(fund_code="000001", fund_name="")
        scored = score_candidate("", cand)
        assert scored.match_bucket == BUCKET_MISMATCH
        assert scored.match_score == 0.0

    def test_fund_type_token_match(self):
        cand = FundIdentityCandidate(fund_code="000001", fund_name="某债券基金A")
        scored = score_candidate("某债券基金A", cand)
        assert "fund_type_token_match" in scored.match_reasons

    def test_ambiguous_short_name(self):
        cand = FundIdentityCandidate(fund_code="000001", fund_name="混合基金")
        scored = score_candidate("债券基金", cand)
        # Short name with low similarity should get ambiguous penalty
        assert scored.match_score < 0.7


# ── Auto-verify ────────────────────────────────────────────────────────


class TestShouldAutoVerify:
    """Test auto-verify decision logic."""

    def test_single_high_confidence(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="易方达蓝筹精选混合A",
                match_score=0.95, match_bucket=BUCKET_HIGH,
                match_reasons=["high_name_similarity"], risk_flags=[],
                identity_token_overlap=0.8,
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert ok
        assert reason == "auto_verified"

    def test_insufficient_margin(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="易方达蓝筹精选混合A",
                match_score=0.90, match_bucket=BUCKET_HIGH,
                match_reasons=["high_name_similarity"], risk_flags=[],
                identity_token_overlap=0.8,
            ),
            FundIdentityCandidate(
                fund_code="110012", fund_name="易方达蓝筹精选混合C",
                match_score=0.80, match_bucket=BUCKET_MEDIUM,
                match_reasons=["medium_name_similarity"], risk_flags=[],
                identity_token_overlap=0.7,
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "insufficient_margin" in reason

    def test_score_below_threshold(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="某基金",
                match_score=0.70, match_bucket=BUCKET_MEDIUM,
                match_reasons=["medium_name_similarity"], risk_flags=[],
                identity_token_overlap=0.8,
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "score_below_threshold" in reason

    def test_share_class_mismatch_blocks(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="易方达蓝筹精选混合A",
                match_score=0.95, match_bucket=BUCKET_HIGH,
                match_reasons=["high_name_similarity"],
                risk_flags=["share_class_mismatch"],
                identity_token_overlap=0.8,
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "risk_flag:share_class_mismatch" in reason

    def test_invalid_fund_code(self):
        cands = [
            FundIdentityCandidate(
                fund_code="abc", fund_name="某基金",
                match_score=0.95, match_bucket=BUCKET_HIGH,
                match_reasons=["exact_normalized_match"], risk_flags=[],
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "invalid_fund_code" in reason

    def test_no_provider_profile(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="",
                match_score=0.95, match_bucket=BUCKET_HIGH,
                match_reasons=["exact_normalized_match"], risk_flags=[],
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_provider_profile" in reason

    def test_bucket_not_high_enough(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="某基金",
                match_score=0.86, match_bucket=BUCKET_MEDIUM,
                match_reasons=["medium_name_similarity"], risk_flags=[],
                identity_token_overlap=0.8,
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "bucket_not_high_enough" in reason

    def test_no_candidates(self):
        ok, reason = should_auto_verify([])
        assert not ok
        assert reason == "no_candidates"

    def test_qdii_mismatch_blocks(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="某QDII基金A",
                match_score=0.90, match_bucket=BUCKET_HIGH,
                match_reasons=["high_name_similarity"],
                risk_flags=["qdii_mismatch"],
                identity_token_overlap=0.8,
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "risk_flag:qdii_mismatch" in reason

    def test_etf_link_mismatch_blocks(self):
        cands = [
            FundIdentityCandidate(
                fund_code="110011", fund_name="某ETF联接A",
                match_score=0.90, match_bucket=BUCKET_HIGH,
                match_reasons=["high_name_similarity"],
                risk_flags=["etf_link_mismatch"],
                identity_token_overlap=0.8,
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "risk_flag:etf_link_mismatch" in reason


# ── Discovery orchestrator ─────────────────────────────────────────────


class _MockSearchProvider:
    """Mock provider for testing."""

    def __init__(self, results: dict[str, list[FundIdentityCandidate]] | None = None):
        self._results = results or {}

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        return self._results.get(normalized_name, [])


class TestDiscoverCandidates:
    """Test discovery orchestrator."""

    def test_null_provider_returns_empty(self):
        results = discover_candidates(["蚂蚁财富-某基金-买入"])
        # NullFundIdentitySearchProvider returns no candidates
        for candidates in results.values():
            assert candidates == []

    def test_mock_provider_returns_candidates(self):
        provider = _MockSearchProvider({
            "某基金": [
                FundIdentityCandidate(fund_code="000001", fund_name="某基金A"),
            ],
        })
        results = discover_candidates(["蚂蚁财富-某基金-买入"], provider=provider)
        assert len(results) == 1
        for norm_name, candidates in results.items():
            assert len(candidates) == 1
            assert candidates[0].fund_code == "000001"

    def test_duplicate_names_deduped(self):
        results = discover_candidates(["蚂蚁财富-某基金-买入", "蚂蚁财富-某基金-定投"])
        # Same normalized name should only appear once
        assert len(results) <= 1

    def test_empty_name_skipped(self):
        results = discover_candidates(["蚂蚁财富--买入"])
        # Empty normalized name should be skipped
        for norm_name in results:
            assert norm_name != ""


class TestComputeDiscoverySummary:
    """Test discovery summary computation."""

    def test_empty_results(self):
        summary = compute_discovery_summary({})
        assert summary["name_search_requested_count"] == 0
        assert summary["name_search_no_result_count"] == 0

    def test_auto_verified_count(self):
        results = {
            "基金A": [
                FundIdentityCandidate(
                    fund_code="000001", fund_name="基金A",
                    match_score=0.95, match_bucket=BUCKET_EXACT,
                    match_reasons=["exact_normalized_match"], risk_flags=[],
                    identity_token_overlap=0.9,
                ),
            ],
        }
        summary = compute_discovery_summary(results)
        assert summary["name_search_promoted_provider_verified_count"] == 1
        assert summary["name_search_unique_high_confidence_count"] == 1

    def test_ambiguous_count(self):
        results = {
            "基金A": [
                FundIdentityCandidate(
                    fund_code="000001", fund_name="基金A",
                    match_score=0.80, match_bucket=BUCKET_MEDIUM,
                    match_reasons=["medium_name_similarity"], risk_flags=[],
                ),
                FundIdentityCandidate(
                    fund_code="000002", fund_name="基金A类",
                    match_score=0.75, match_bucket=BUCKET_MEDIUM,
                    match_reasons=["medium_name_similarity"], risk_flags=[],
                ),
            ],
        }
        summary = compute_discovery_summary(results)
        assert summary["name_search_ambiguous_count"] == 1

    def test_no_result_count(self):
        results = {"基金A": []}
        summary = compute_discovery_summary(results)
        assert summary["name_search_no_result_count"] == 1


# ── Provider import isolation ──────────────────────────────────────────


class TestFundIdentityCandidateDiscoveryNoProviderImports:
    """fund_identity_candidate_discovery must not import external providers."""

    def test_no_akshare_import(self):
        import subprocess
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent.parent
        result = subprocess.run(
            [sys.executable, "-c",
             "import src.tools.portfolio.fund_identity_candidate_discovery; "
             "import sys; "
             "found = [m for m in sys.modules if 'akshare' in m]; "
             "print(','.join(found) if found else 'CLEAN')"],
            capture_output=True, text=True, timeout=30,
            cwd=str(repo_root),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(repo_root)},
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert result.stdout.strip() == "CLEAN", f"akshare in sys.modules: {result.stdout.strip()}"
