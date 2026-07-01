"""M7.15: Strict identity candidate matching — hard reject rules.

Tests that brand, theme, structure, and share class mismatches
result in hard_reject=True and candidate_status reflecting the reason.
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.fund_identity_candidate_discovery import (
    FundIdentityCandidate,
    apply_hard_reject,
    score_candidate,
    should_auto_verify,
    BUCKET_MISMATCH,
)


def _make_candidate(fund_code: str, fund_name: str) -> FundIdentityCandidate:
    """Create a minimal candidate for testing."""
    return FundIdentityCandidate(
        fund_code=fund_code,
        fund_name=fund_name,
    )


class TestBrandMismatchHardReject:
    """Different fund companies must not match."""

    def test_huaxia_vs_huaan(self):
        """华夏消费电子ETF联接C 不得匹配 华安黄金ETF联接C"""
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert result.hard_reject is True
        assert "rejected_brand_mismatch" in result.reject_reasons
        assert result.candidate_status == "rejected_brand_mismatch"

    def test_dongfang_vs_jianxin(self):
        """东方惠新灵活配置混合A 不得匹配 建信灵活配置混合A"""
        c = _make_candidate("000270", "建信灵活配置混合A")
        scored = score_candidate("东方惠新灵活配置混合A", c)
        result = apply_hard_reject("东方惠新灵活配置混合A", scored)
        assert result.hard_reject is True
        assert "rejected_brand_mismatch" in result.reject_reasons

    def test_wanjia_vs_guotai(self):
        """万家国证新能源车电池ETF联接C 不得匹配 国泰中证新能源汽车ETF联接C"""
        c = _make_candidate("009068", "国泰中证新能源汽车ETF联接C")
        scored = score_candidate("万家国证新能源车电池ETF联接C", c)
        result = apply_hard_reject("万家国证新能源车电池ETF联接C", scored)
        assert result.hard_reject is True
        assert "rejected_brand_mismatch" in result.reject_reasons

    def test_huabao_vs_guangfa(self):
        """华宝纳斯达克精选股票(QDII)A 不得匹配 广发全球精选股票(QDII)美元A"""
        c = _make_candidate("000906", "广发全球精选股票(QDII)美元A")
        scored = score_candidate("华宝纳斯达克精选股票(QDII)A", c)
        result = apply_hard_reject("华宝纳斯达克精选股票(QDII)A", scored)
        assert result.hard_reject is True
        assert "rejected_brand_mismatch" in result.reject_reasons

    def test_huabao_zhiyuan_vs_mogen(self):
        """华宝致远混合(QDII)A 不得匹配 摩根中国生物医药混合(QDII)A"""
        c = _make_candidate("001984", "摩根中国生物医药混合(QDII)A")
        scored = score_candidate("华宝致远混合(QDII)A", c)
        result = apply_hard_reject("华宝致远混合(QDII)A", scored)
        assert result.hard_reject is True
        assert "rejected_brand_mismatch" in result.reject_reasons

    def test_same_brand_accepted(self):
        """Same brand should not trigger brand mismatch."""
        c = _make_candidate("007467", "华泰柏瑞中证红利低波动ETF联接C")
        scored = score_candidate("华泰柏瑞中证红利低波动ETF联接C", c)
        result = apply_hard_reject("华泰柏瑞中证红利低波动ETF联接C", scored)
        # Same brand — no brand mismatch
        assert "rejected_brand_mismatch" not in result.reject_reasons


class TestThemeMismatchHardReject:
    """Conflicting themes must not match."""

    def test_xiaofeidianzi_vs_huangjin(self):
        """消费电子 vs 黄金 — theme mismatch"""
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert result.hard_reject is True
        assert "rejected_theme_mismatch" in result.reject_reasons

    def test_chuangxinyao_vs_huangjin(self):
        """创新药 vs 黄金 — theme mismatch"""
        c = _make_candidate("004253", "国泰黄金ETF联接C")
        scored = score_candidate("国泰创新药ETF联接C", c)
        result = apply_hard_reject("国泰创新药ETF联接C", scored)
        assert result.hard_reject is True
        assert "rejected_theme_mismatch" in result.reject_reasons

    def test_youqi_vs_guangfu(self):
        """油气 vs 光伏 — theme mismatch"""
        c = _make_candidate("011103", "天弘中证光伏产业指数C")
        scored = score_candidate("天弘中证油气产业指数C", c)
        result = apply_hard_reject("天弘中证油气产业指数C", scored)
        assert result.hard_reject is True
        assert "rejected_theme_mismatch" in result.reject_reasons

    def test_yifangda_hongli_vs_huangjin(self):
        """红利 vs 黄金 — theme mismatch"""
        c = _make_candidate("002963", "易方达黄金ETF联接C")
        scored = score_candidate("易方达中证红利ETF联接C", c)
        result = apply_hard_reject("易方达中证红利ETF联接C", scored)
        assert result.hard_reject is True
        assert "rejected_theme_mismatch" in result.reject_reasons


class TestStructureMismatchHardReject:
    """QDII/non-QDII, ETF联接/non-ETF联接, 短债/非短债 must not cross."""

    def test_qdii_vs_non_qdii(self):
        """QDII fund must not match non-QDII fund."""
        c = _make_candidate("000906", "广发全球精选股票(QDII)美元A")
        scored = score_candidate("华宝纳斯达克精选股票A", c)
        result = apply_hard_reject("华宝纳斯达克精选股票A", scored)
        # query has no QDII, candidate has QDII → structure mismatch
        assert "rejected_structure_mismatch" in result.reject_reasons

    def test_etf_link_vs_non_etf_link(self):
        """ETF联接 fund must not match non-ETF联接 fund."""
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子C", c)
        result = apply_hard_reject("华夏消费电子C", scored)
        # query has no ETF联接, candidate has ETF联接 → structure mismatch
        assert "rejected_structure_mismatch" in result.reject_reasons

    def test_duanzhai_vs_shuangzhai(self):
        """短债 must not match 双债增强."""
        c = _make_candidate("000208", "建信双债增强债券C")
        scored = score_candidate("建信短债债券C", c)
        result = apply_hard_reject("建信短债债券C", scored)
        assert "rejected_structure_mismatch" in result.reject_reasons


class TestShareClassMismatchHardReject:
    """A/C share class must not cross."""

    def test_a_vs_c(self):
        """A share must not match C share."""
        c = _make_candidate("009068", "国泰中证新能源汽车ETF联接C")
        scored = score_candidate("万家国证新能源车电池ETF联接A", c)
        result = apply_hard_reject("万家国证新能源车电池ETF联接A", scored)
        assert "rejected_share_class_mismatch" in result.reject_reasons


class TestHardRejectBlocksAutoVerify:
    """Hard-rejected candidates must not auto-verify."""

    def test_hard_reject_prevents_auto_verify(self):
        c = FundIdentityCandidate(
            fund_code="000217",
            fund_name="华安黄金ETF联接C",
            match_score=0.78,
            match_bucket="medium",
            hard_reject=True,
            reject_reasons=["rejected_brand_mismatch", "rejected_theme_mismatch"],
            critical_token_mismatch=["brand:华夏!=华安"],
        )
        can_verify, reason = should_auto_verify([c])
        assert can_verify is False
        assert "hard_reject" in reason

    def test_critical_token_mismatch_prevents_auto_verify(self):
        c = FundIdentityCandidate(
            fund_code="000217",
            fund_name="华安黄金ETF联接C",
            match_score=0.90,
            match_bucket="high",
            hard_reject=False,
            critical_token_mismatch=["brand:华夏!=华安"],
        )
        can_verify, reason = should_auto_verify([c])
        assert can_verify is False
        assert "critical_token_mismatch" in reason

    def test_no_identity_token_overlap_prevents_auto_verify(self):
        from src.tools.portfolio.fund_identity_candidate_discovery import EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH
        c = FundIdentityCandidate(
            fund_code="000217",
            fund_name="华安黄金ETF联接C",
            match_score=0.90,
            match_bucket="high",
            hard_reject=False,
            critical_token_mismatch=[],
            identity_token_overlap=0.0,
            match_reasons=[EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH],
        )
        can_verify, reason = should_auto_verify([c])
        assert can_verify is False
        assert "no_identity_token_overlap" in reason


class TestHardRejectForcesZeroScore:
    """Hard-rejected candidates should have score forced to 0."""

    def test_hard_reject_zeroes_score(self):
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        if result.hard_reject:
            assert result.match_score == 0.0
            assert result.match_bucket == BUCKET_MISMATCH


class TestIdentityTokenOverlap:
    """Identity token overlap should be computed correctly."""

    def test_same_brand_same_theme_high_overlap(self):
        c = _make_candidate("007467", "华泰柏瑞中证红利低波动ETF联接C")
        scored = score_candidate("华泰柏瑞中证红利低波动ETF联接C", c)
        result = apply_hard_reject("华泰柏瑞中证红利低波动ETF联接C", scored)
        assert result.identity_token_overlap > 0.5

    def test_different_brand_different_theme_low_overlap(self):
        c = _make_candidate("000217", "华安黄金ETF联接C")
        scored = score_candidate("华夏消费电子ETF联接C", c)
        result = apply_hard_reject("华夏消费电子ETF联接C", scored)
        assert result.identity_token_overlap < 0.3
