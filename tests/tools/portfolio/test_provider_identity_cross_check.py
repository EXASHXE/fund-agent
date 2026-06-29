"""Tests for M7.9 provider identity cross-check.

Covers:
1. Provider cross-check promotes manual_override_unverified to provider_verified
2. Provider name mismatch blocks valuation
3. Provider lookup failed keeps manual_override_unverified
4. Fund share class suffix handled carefully
5. Raw Alipay prefix removed before matching
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.provider_identity_cross_check import (
    DictFundNameProvider,
    NullFundNameProvider,
    batch_provider_cross_check,
    compute_name_similarity,
    normalize_for_comparison,
    provider_cross_check,
    strip_platform_prefix,
    strip_share_class_suffix,
)


class TestProviderCrossCheck:
    def test_provider_cross_check_promotes_manual_override_to_provider_verified(self):
        provider = DictFundNameProvider({
            "000001": "华夏成长混合",
        })
        result = provider_cross_check(
            raw_fund_name="华夏成长混合",
            candidate_fund_code="000001",
            provider=provider,
        )
        assert result["lookup_result"] == "confirmed"
        assert result["identity_verification_status"] == "provider_verified"

    def test_provider_name_mismatch_blocks_valuation(self):
        provider = DictFundNameProvider({
            "000001": "华夏成长混合",
        })
        result = provider_cross_check(
            raw_fund_name="完全不同的基金",
            candidate_fund_code="000001",
            provider=provider,
        )
        assert result["lookup_result"] == "mismatch"
        assert result["identity_verification_status"] == "code_name_mismatch"

    def test_provider_lookup_failed_keeps_manual_override_unverified(self):
        provider = NullFundNameProvider()
        result = provider_cross_check(
            raw_fund_name="华夏成长混合",
            candidate_fund_code="000001",
            provider=provider,
        )
        assert result["lookup_result"] == "failed"
        assert result["identity_verification_status"] == "manual_override_unverified"

    def test_invalid_fund_code_fails(self):
        provider = DictFundNameProvider({})
        result = provider_cross_check(
            raw_fund_name="华夏成长混合",
            candidate_fund_code="abc",
            provider=provider,
        )
        assert result["lookup_result"] == "failed"

    def test_similarity_score_returned(self):
        provider = DictFundNameProvider({
            "000001": "华夏成长混合",
        })
        result = provider_cross_check(
            raw_fund_name="华夏成长混合",
            candidate_fund_code="000001",
            provider=provider,
        )
        assert result["similarity"] == 1.0


class TestNameSimilarity:
    def test_exact_match(self):
        assert compute_name_similarity("华夏成长混合", "华夏成长混合") == 1.0

    def test_different_names(self):
        sim = compute_name_similarity("华夏成长混合", "易方达蓝筹精选")
        assert sim < 0.5

    def test_share_class_suffix_handled_carefully(self):
        # A/C suffix difference should still match highly
        sim = compute_name_similarity("华夏成长混合A", "华夏成长混合C")
        assert sim >= 0.9

    def test_empty_names(self):
        assert compute_name_similarity("", "华夏成长") == 0.0
        assert compute_name_similarity("华夏成长", "") == 0.0

    def test_substring_containment(self):
        sim = compute_name_similarity("华夏成长", "华夏成长混合")
        assert sim >= 0.8


class TestPlatformPrefixStripping:
    def test_strip_alipay_prefix(self):
        assert strip_platform_prefix("蚂蚁财富-华夏成长") == "华夏成长"

    def test_strip_alipay_em_dash(self):
        assert strip_platform_prefix("蚂蚁财富—华夏成长") == "华夏成长"

    def test_no_prefix(self):
        assert strip_platform_prefix("华夏成长") == "华夏成长"

    def test_strip_zhifubao_prefix(self):
        assert strip_platform_prefix("支付宝-华夏成长") == "华夏成长"


class TestShareClassSuffix:
    def test_strip_a_suffix(self):
        stripped, suffix = strip_share_class_suffix("华夏成长混合A")
        assert suffix == "A"

    def test_strip_c_suffix(self):
        stripped, suffix = strip_share_class_suffix("华夏成长混合C")
        assert suffix == "C"

    def test_no_suffix(self):
        stripped, suffix = strip_share_class_suffix("华夏成长混合")
        assert suffix is None


class TestNormalization:
    def test_full_width_conversion(self):
        norm = normalize_for_comparison("华夏成长Ａ")
        assert "a" in norm

    def test_whitespace_removal(self):
        norm = normalize_for_comparison("华夏 成长 混合")
        assert " " not in norm

    def test_platform_prefix_in_normalization(self):
        norm1 = normalize_for_comparison("蚂蚁财富-华夏成长")
        norm2 = normalize_for_comparison("华夏成长")
        assert norm1 == norm2


class TestBatchProviderCrossCheck:
    def test_batch_updates_resolutions(self):
        provider = DictFundNameProvider({
            "000001": "华夏成长混合",
            "000002": "易方达蓝筹精选",
        })
        resolutions = [
            {
                "resolved_fund_code": "000001",
                "raw_fund_name": "华夏成长混合",
                "identity_verification_status": "manual_override_unverified",
            },
            {
                "resolved_fund_code": "000002",
                "raw_fund_name": "完全不同的基金",
                "identity_verification_status": "manual_override_unverified",
            },
        ]
        result = batch_provider_cross_check(resolutions, provider)
        assert result["provider_identity_checked_count"] == 2
        assert result["provider_identity_verified_count"] == 1
        assert result["provider_identity_mismatch_count"] == 1

        # Check status updates
        assert resolutions[0]["identity_verification_status"] == "provider_verified"
        assert resolutions[1]["identity_verification_status"] == "code_name_mismatch"

    def test_batch_skips_non_manual_override(self):
        provider = DictFundNameProvider({"000001": "华夏成长混合"})
        resolutions = [
            {
                "resolved_fund_code": "000001",
                "raw_fund_name": "华夏成长混合",
                "identity_verification_status": "verified",
            },
        ]
        result = batch_provider_cross_check(resolutions, provider)
        assert result["provider_identity_checked_count"] == 0
