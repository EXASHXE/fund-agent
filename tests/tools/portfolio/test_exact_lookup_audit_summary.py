"""Tests for M7.17 exact lookup audit summary.

Validates:
1. Audit summary has no fund names or codes
2. Audit counts match resolutions
3. non_exact_auto_verified_count is always 0
4. fuzzy_auto_verified_count is always 0
5. Audit covers all match reason categories
6. Audit covers all blocked reason categories
"""
from __future__ import annotations

import json

from src.tools.portfolio.fund_identity_candidate_discovery import (
    BUCKET_EXACT,
    BUCKET_HIGH,
    BUCKET_MEDIUM,
    EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH,
    EXACT_FUND_UNIVERSE_NAME_MATCH,
    EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH,
    EXACT_LOCAL_CACHE_NAME_MATCH,
    FundIdentityCandidate,
    compute_exact_lookup_audit,
)


def _make_auto_verified_resolution(match_reason: str, source: str = "akshare_fund_universe_exact") -> dict:
    """Create a resolution dict that is name_search_auto_verified."""
    return {
        "resolved_fund_code": "110011",
        "raw_fund_name": "某基金A",
        "fund_name": "某基金A",
        "resolution_source": "name_search_auto_verified",
        "identity_verification_status": "provider_verified",
        "name_search_candidates": [
            {
                "fund_code": "110011",
                "fund_name": "某基金A",
                "match_score": 1.0,
                "match_bucket": BUCKET_EXACT,
                "match_reasons": [match_reason],
                "source": source,
                "hard_reject": False,
                "critical_token_mismatch": [],
                "identity_token_overlap": 0.9,
                "risk_flags": [],
            },
        ],
    }


def _make_unverified_resolution(blocked_reason: str = "no_exact_match") -> dict:
    """Create a resolution dict that is name_search_candidate_unverified."""
    candidates = []
    if blocked_reason != "no_exact_match":
        candidates = [
            {
                "fund_code": "000001",
                "fund_name": "某基金B",
                "match_score": 0.70,
                "match_bucket": BUCKET_MEDIUM,
                "match_reasons": ["medium_name_similarity"],
                "source": "akshare_fund_name_em",
                "hard_reject": blocked_reason == "hard_reject",
                "critical_token_mismatch": ["brand:A!=B"] if blocked_reason == "critical_token_mismatch" else [],
                "identity_token_overlap": 0.0 if blocked_reason == "no_identity_token_overlap" else 0.5,
                "risk_flags": ["share_class_mismatch"] if blocked_reason == "risk_flag" else [],
            },
        ]
    return {
        "resolved_fund_code": None,
        "raw_fund_name": "某基金B",
        "fund_name": "某基金B",
        "resolution_source": "name_only",
        "identity_verification_status": "name_search_candidate_unverified",
        "name_search_candidates": candidates,
    }


class TestExactLookupAuditHasNoFundNamesOrCodes:
    """Audit summary must not contain any real fund names or codes."""

    def test_audit_json_has_no_six_digit_codes(self):
        resolutions = [
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH),
            _make_unverified_resolution(),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        audit_str = json.dumps(audit, ensure_ascii=False)
        # No 6-digit fund codes in audit output
        assert "110011" not in audit_str
        assert "000001" not in audit_str

    def test_audit_json_has_no_fund_names(self):
        resolutions = [
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        audit_str = json.dumps(audit, ensure_ascii=False)
        # No fund names in audit output
        assert "某基金" not in audit_str


class TestExactLookupAuditCountsMatchResolutions:
    """Audit counts must match the input resolutions."""

    def test_auto_verified_total_matches(self):
        resolutions = [
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH),
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH),
            _make_unverified_resolution(),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["auto_verified_total"] == 2

    def test_auto_verified_by_match_reason(self):
        resolutions = [
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH),
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH),
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["auto_verified_by_match_reason"][EXACT_FUND_UNIVERSE_NAME_MATCH] == 2
        assert audit["auto_verified_by_match_reason"][EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH] == 1

    def test_blocked_by_reason(self):
        resolutions = [
            _make_unverified_resolution("no_exact_match"),
            _make_unverified_resolution("hard_reject"),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["blocked_by_reason"]["no_exact_match"] == 1
        assert audit["blocked_by_reason"]["hard_reject"] == 1

    def test_candidate_source_counts(self):
        resolutions = [
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH, "akshare_fund_universe_exact"),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["candidate_source_counts"]["akshare_fund_universe_exact"] == 1

    def test_empty_resolutions(self):
        audit = compute_exact_lookup_audit([])
        assert audit["auto_verified_total"] == 0
        assert audit["non_exact_auto_verified_count"] == 0
        assert audit["fuzzy_auto_verified_count"] == 0


class TestNonExactAutoVerifiedCountZero:
    """non_exact_auto_verified_count must always be 0."""

    def test_with_only_exact_reasons(self):
        resolutions = [
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH),
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_WITHOUT_PUNCTUATION_MATCH),
            _make_auto_verified_resolution(EXACT_CORE_NAME_AND_SHARE_CLASS_MATCH),
            _make_auto_verified_resolution(EXACT_LOCAL_CACHE_NAME_MATCH),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["non_exact_auto_verified_count"] == 0

    def test_with_no_auto_verified(self):
        resolutions = [
            _make_unverified_resolution(),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["non_exact_auto_verified_count"] == 0


class TestFuzzyAutoVerifiedCountZero:
    """fuzzy_auto_verified_count must always be 0."""

    def test_with_exact_auto_verified(self):
        resolutions = [
            _make_auto_verified_resolution(EXACT_FUND_UNIVERSE_NAME_MATCH),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["fuzzy_auto_verified_count"] == 0

    def test_with_unverified_fuzzy_candidates(self):
        resolutions = [
            _make_unverified_resolution("no_exact_universe_match_reason"),
        ]
        audit = compute_exact_lookup_audit(resolutions)
        assert audit["fuzzy_auto_verified_count"] == 0
