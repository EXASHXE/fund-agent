"""Tests for M7.16/M7.17/M7.19 name search auto-verify gate.

Validates:
1. Exact universe match auto-verifies
2. Exact without punctuation auto-verifies
3. Core share class exact auto-verifies (with identity_token_overlap)
4. Fuzzy high score does NOT auto-verify
5. LCS high score does NOT auto-verify
6. Substring match does NOT auto-verify

M7.17 additions:
7. exact_full_name can auto-verify WITHOUT identity_token_overlap
8. exact_without_punctuation can auto-verify WITHOUT identity_token_overlap
9. core_share_class REQUIRES identity_token_overlap > 0
10. local_cache REQUIRES identity_token_overlap > 0

M7.19 additions:
11. Supplement exact match auto-verifies when high confidence
12. Supplement exact match blocks when low confidence
13. Supplement exact match blocks when ambiguous
14. Supplement match reason recorded
"""
from __future__ import annotations

import pytest

from src.tools.portfolio.fund_identity_candidate_discovery import (
    BUCKET_EXACT,
    BUCKET_HIGH,
    BUCKET_MEDIUM,
    EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH,
    EXACT_FUND_UNIVERSE_NAME_MATCH,
    EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH,
    EXACT_FUND_UNIVERSE_SUPPLEMENT_MATCH,
    EXACT_LOCAL_CACHE_NAME_MATCH,
    FundIdentityCandidate,
    should_auto_verify,
)


def _make_candidate(
    match_reasons: list[str],
    match_score: float = 0.95,
    match_bucket: str = BUCKET_EXACT,
    risk_flags: list[str] | None = None,
    identity_token_overlap: float = 0.9,
    hard_reject: bool = False,
    critical_token_mismatch: list[str] | None = None,
    reject_reasons: list[str] | None = None,
    source: str = "",
    universe_confidence: str = "high",
) -> FundIdentityCandidate:
    """Helper to create a candidate with common defaults."""
    return FundIdentityCandidate(
        fund_code="110011",
        fund_name="易方达蓝筹精选混合A",
        match_score=match_score,
        match_bucket=match_bucket,
        match_reasons=match_reasons,
        risk_flags=risk_flags or [],
        identity_token_overlap=identity_token_overlap,
        hard_reject=hard_reject,
        critical_token_mismatch=critical_token_mismatch or [],
        reject_reasons=reject_reasons or [],
        source=source,
        universe_confidence=universe_confidence,
    )


class TestExactUniverseMatchAutoVerifies:
    """Exact universe match reasons should auto-verify."""

    def test_exact_fund_universe_name_match_auto_verifies(self):
        cands = [_make_candidate(match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH])]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify, got: {reason}"
        assert reason == "auto_verified"

    def test_exact_without_punctuation_auto_verifies(self):
        cands = [_make_candidate(match_reasons=[EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH])]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify, got: {reason}"

    def test_core_share_class_exact_auto_verifies(self):
        cands = [_make_candidate(match_reasons=[EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH])]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify, got: {reason}"

    def test_exact_match_with_additional_reasons_still_auto_verifies(self):
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH, "share_class_exact_match"],
        )]
        ok, reason = should_auto_verify(cands)
        assert ok


class TestFuzzyHighScoreDoesNotAutoVerify:
    """Fuzzy high score must NOT auto-verify without exact match reason."""

    def test_fuzzy_high_score_does_not_auto_verify(self):
        cands = [_make_candidate(
            match_reasons=["high_name_similarity"],
            match_score=0.92,
            match_bucket=BUCKET_HIGH,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_exact_universe_match_reason" in reason

    def test_lcs_high_score_does_not_auto_verify(self):
        cands = [_make_candidate(
            match_reasons=["near_exact_name_match"],
            match_score=0.95,
            match_bucket=BUCKET_HIGH,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_exact_universe_match_reason" in reason

    def test_substring_match_does_not_auto_verify(self):
        cands = [_make_candidate(
            match_reasons=["provider_name_contains_query"],
            match_score=0.90,
            match_bucket=BUCKET_HIGH,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_exact_universe_match_reason" in reason

    def test_exact_normalized_match_without_universe_reason_does_not_auto_verify(self):
        """exact_normalized_match from score_candidate is NOT a universe exact reason."""
        cands = [_make_candidate(
            match_reasons=["exact_normalized_match"],
            match_score=1.0,
            match_bucket=BUCKET_EXACT,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_exact_universe_match_reason" in reason

    def test_identity_token_overlap_alone_does_not_auto_verify(self):
        cands = [_make_candidate(
            match_reasons=["medium_name_similarity"],
            match_score=0.88,
            match_bucket=BUCKET_HIGH,
            identity_token_overlap=0.9,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_exact_universe_match_reason" in reason


class TestAutoVerifyStillRequiresOtherChecks:
    """Even with exact match reason, other checks still apply."""

    def test_hard_reject_blocks_even_with_exact_reason(self):
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH],
            hard_reject=True,
            reject_reasons=["rejected_brand_mismatch"],
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "hard_reject" in reason

    def test_critical_token_mismatch_blocks_even_with_exact_reason(self):
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH],
            critical_token_mismatch=["brand:万家!=华宝"],
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "critical_token_mismatch" in reason

    def test_risk_flag_blocks_even_with_exact_reason(self):
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH],
            risk_flags=["share_class_mismatch"],
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "risk_flag:share_class_mismatch" in reason


class TestM717IdentityTokenOverlapRequirements:
    """M7.17: Different exact match levels have different identity_token_overlap requirements."""

    def test_exact_full_name_no_tokens_still_auto_verifies(self):
        """exact_fund_universe_name_match can auto-verify WITHOUT identity_token_overlap."""
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH],
            identity_token_overlap=0.0,
        )]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify for exact_full_name without tokens, got: {reason}"

    def test_exact_without_punctuation_no_tokens_still_auto_verifies(self):
        """exact_without_punctuation can auto-verify WITHOUT identity_token_overlap."""
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH],
            identity_token_overlap=0.0,
        )]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify for exact_without_punctuation without tokens, got: {reason}"

    def test_core_share_class_no_tokens_does_not_auto_verify(self):
        """core_share_class REQUIRES identity_token_overlap > 0."""
        cands = [_make_candidate(
            match_reasons=[EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH],
            identity_token_overlap=0.0,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_identity_token_overlap" in reason

    def test_local_cache_no_tokens_does_not_auto_verify(self):
        """local_cache REQUIRES identity_token_overlap > 0."""
        cands = [_make_candidate(
            match_reasons=[EXACT_LOCAL_CACHE_NAME_MATCH],
            identity_token_overlap=0.0,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_identity_token_overlap" in reason

    def test_core_share_class_with_tokens_auto_verifies(self):
        """core_share_class WITH identity_token_overlap > 0 auto-verifies."""
        cands = [_make_candidate(
            match_reasons=[EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH],
            identity_token_overlap=0.8,
        )]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify for core_share_class with tokens, got: {reason}"

    def test_local_cache_with_tokens_auto_verifies(self):
        """local_cache WITH identity_token_overlap > 0 auto-verifies."""
        cands = [_make_candidate(
            match_reasons=[EXACT_LOCAL_CACHE_NAME_MATCH],
            identity_token_overlap=0.8,
        )]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify for local_cache with tokens, got: {reason}"

    def test_fuzzy_high_score_stays_unverified(self):
        """Fuzzy high score with tokens still does NOT auto-verify."""
        cands = [_make_candidate(
            match_reasons=["fuzzy_fallback"],
            match_score=0.95,
            match_bucket=BUCKET_HIGH,
            identity_token_overlap=0.9,
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "no_exact_universe_match_reason" in reason


class TestM719SupplementAutoVerifyGate:
    """M7.19: Supplement exact match auto-verify gates."""

    def test_supplement_exact_match_auto_verifies_when_high_confidence(self):
        """Supplement exact match with high confidence auto-verifies."""
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH, EXACT_FUND_UNIVERSE_SUPPLEMENT_MATCH],
            source="local_public_fund_universe_supplement",
            universe_confidence="high",
        )]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify for high-confidence supplement, got: {reason}"

    def test_supplement_exact_match_blocks_when_low_confidence(self):
        """Supplement exact match with low confidence does NOT auto-verify."""
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH, EXACT_FUND_UNIVERSE_SUPPLEMENT_MATCH],
            source="local_public_fund_universe_supplement",
            universe_confidence="low",
        )]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "low_universe_confidence" in reason

    def test_supplement_exact_match_blocks_when_ambiguous(self):
        """Supplement exact match with ambiguous candidates does NOT auto-verify."""
        cands = [
            _make_candidate(
                match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH, EXACT_FUND_UNIVERSE_SUPPLEMENT_MATCH],
                match_score=0.95,
                source="local_public_fund_universe_supplement",
                universe_confidence="high",
            ),
            _make_candidate(
                match_reasons=["high_name_similarity"],
                match_score=0.90,
                source="local_public_fund_universe_supplement",
            ),
        ]
        ok, reason = should_auto_verify(cands)
        assert not ok
        assert "insufficient_margin" in reason

    def test_supplement_match_reason_recorded(self):
        """Supplement match reason is preserved in candidate."""
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH, EXACT_FUND_UNIVERSE_SUPPLEMENT_MATCH],
            source="local_public_fund_universe_supplement",
            universe_confidence="high",
        )]
        assert EXACT_FUND_UNIVERSE_SUPPLEMENT_MATCH in cands[0].match_reasons
        assert cands[0].source == "local_public_fund_universe_supplement"

    def test_medium_confidence_supplement_auto_verifies(self):
        """Medium confidence supplement CAN auto-verify (only low is blocked)."""
        cands = [_make_candidate(
            match_reasons=[EXACT_FUND_UNIVERSE_NAME_MATCH, EXACT_FUND_UNIVERSE_SUPPLEMENT_MATCH],
            source="local_public_fund_universe_supplement",
            universe_confidence="medium",
        )]
        ok, reason = should_auto_verify(cands)
        assert ok, f"Expected auto-verify for medium-confidence supplement, got: {reason}"
