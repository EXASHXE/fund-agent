"""Tests for M7.11 identity pipeline integration with name search.

Validates:
1. resolve_fund_identities with name_search_provider
2. name_search_auto_verified → provider_verified
3. name_search_candidate_unverified status
4. --enable-name-search flag
5. Identity verification status propagation
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from src.tools.portfolio.fund_identity_candidate_discovery import (
    BUCKET_EXACT,
    BUCKET_HIGH,
    BUCKET_MEDIUM,
    FundIdentityCandidate,
)
from scripts.resolve_fund_identities import (
    _compute_identity_verification_status,
    resolve_fund_identities,
)


# ── Mock provider ──────────────────────────────────────────────────────


class _MockNameSearchProvider:
    """Mock name search provider for testing."""

    def __init__(self, results: dict[str, list[FundIdentityCandidate]] | None = None):
        self._results = results or {}

    def search_by_name(self, normalized_name: str) -> list[FundIdentityCandidate]:
        return self._results.get(normalized_name, [])


# ── Identity verification status ───────────────────────────────────────


class TestComputeIdentityVerificationStatusNameSearch:
    """Test _compute_identity_verification_status with name_search_result."""

    def test_name_search_auto_verified(self):
        status = _compute_identity_verification_status(
            resolved_code="110011",
            resolution_status="valid_code",
            ref_info={},
            name_search_result="auto_verified",
        )
        assert status == "provider_verified"

    def test_name_search_candidate_unverified(self):
        status = _compute_identity_verification_status(
            resolved_code=None,
            resolution_status="name_only",
            ref_info={},
            name_search_result="candidate_unverified",
        )
        assert status == "name_search_candidate_unverified"

    def test_name_search_none_falls_through(self):
        status = _compute_identity_verification_status(
            resolved_code=None,
            resolution_status="name_only",
            ref_info={},
            name_search_result=None,
        )
        assert status == "name_only"


# ── resolve_fund_identities integration ────────────────────────────────


class TestResolveFundIdentitiesNameSearch:
    """Test resolve_fund_identities with name search enabled."""

    def test_name_search_auto_verified(self):
        """When name search finds a unique high-confidence match, code is resolved."""
        provider = _MockNameSearchProvider({
            "易方达蓝筹精选混合A": [
                FundIdentityCandidate(
                    fund_code="110011",
                    fund_name="易方达蓝筹精选混合A",
                    match_score=1.0,
                    match_bucket=BUCKET_EXACT,
                    match_reasons=["exact_normalized_match"],
                    risk_flags=[],
                ),
            ],
        })
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": None,
                        "fund_name": "蚂蚁财富-易方达蓝筹精选混合A-买入",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=provider,
            enable_name_search=True,
        )
        resolutions = result["resolutions"]
        assert len(resolutions) >= 1
        # Find the resolution for the fund
        for res in resolutions:
            if "易方达蓝筹精选混合A" in (res.get("raw_fund_name") or ""):
                assert res["identity_verification_status"] == "provider_verified"
                assert res["resolved_fund_code"] == "110011"
                assert res["resolution_source"] == "name_search_auto_verified"
                break
        else:
            pytest.fail("No resolution found for 易方达蓝筹精选混合A")

    def test_name_search_candidate_unverified(self):
        """When name search finds candidates but auto-verify fails, status is unverified."""
        provider = _MockNameSearchProvider({
            "某基金A": [
                FundIdentityCandidate(
                    fund_code="000001",
                    fund_name="某基金混合A",
                    match_score=0.75,
                    match_bucket=BUCKET_MEDIUM,
                    match_reasons=["medium_name_similarity"],
                    risk_flags=[],
                ),
                FundIdentityCandidate(
                    fund_code="000002",
                    fund_name="某基金债券A",
                    match_score=0.70,
                    match_bucket=BUCKET_MEDIUM,
                    match_reasons=["medium_name_similarity"],
                    risk_flags=[],
                ),
            ],
        })
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": None,
                        "fund_name": "蚂蚁财富-某基金A-买入",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=provider,
            enable_name_search=True,
        )
        resolutions = result["resolutions"]
        for res in resolutions:
            if "某基金A" in (res.get("raw_fund_name") or ""):
                assert res["identity_verification_status"] == "name_search_candidate_unverified"
                assert res["resolved_fund_code"] is None
                assert "name_search_candidates" in res
                break
        else:
            pytest.fail("No resolution found for 某基金A")

    def test_name_search_disabled(self):
        """When name search is disabled, name-only funds stay name_only."""
        provider = _MockNameSearchProvider({
            "某基金A": [
                FundIdentityCandidate(
                    fund_code="000001",
                    fund_name="某基金A",
                    match_score=0.95,
                    match_bucket=BUCKET_HIGH,
                    match_reasons=["high_name_similarity"],
                    risk_flags=[],
                ),
            ],
        })
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": None,
                        "fund_name": "蚂蚁财富-某基金A-买入",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=provider,
            enable_name_search=False,
        )
        resolutions = result["resolutions"]
        for res in resolutions:
            if "某基金A" in (res.get("raw_fund_name") or ""):
                assert res["identity_verification_status"] == "name_only"
                assert res["resolved_fund_code"] is None
                break

    def test_name_search_no_provider(self):
        """When enable_name_search=True but no provider, falls through gracefully."""
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": None,
                        "fund_name": "蚂蚁财富-某基金A-买入",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=None,
            enable_name_search=True,
        )
        resolutions = result["resolutions"]
        for res in resolutions:
            if "某基金A" in (res.get("raw_fund_name") or ""):
                assert res["identity_verification_status"] == "name_only"
                break

    def test_name_search_does_not_override_existing_code(self):
        """Name search should not override a code already from plan or override."""
        provider = _MockNameSearchProvider({
            "某基金A": [
                FundIdentityCandidate(
                    fund_code="999999",
                    fund_name="某基金A",
                    match_score=1.0,
                    match_bucket=BUCKET_EXACT,
                    match_reasons=["exact_normalized_match"],
                    risk_flags=[],
                ),
            ],
        })
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": "110011",
                        "fund_name": "某基金A",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=provider,
            enable_name_search=True,
        )
        resolutions = result["resolutions"]
        for res in resolutions:
            if "某基金A" in (res.get("raw_fund_name") or ""):
                # Should use the existing code, not the name search result
                assert res["resolved_fund_code"] == "110011"
                assert res["resolution_source"] != "name_search_auto_verified"
                break

    def test_summary_includes_name_search_counts(self):
        """Summary should include name search counts."""
        provider = _MockNameSearchProvider({
            "某基金A": [
                FundIdentityCandidate(
                    fund_code="000001",
                    fund_name="某基金A",
                    match_score=0.95,
                    match_bucket=BUCKET_HIGH,
                    match_reasons=["high_name_similarity"],
                    risk_flags=[],
                ),
            ],
        })
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": None,
                        "fund_name": "蚂蚁财富-某基金A-买入",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=provider,
            enable_name_search=True,
        )
        summary = result["summary"]
        assert "name_search_enabled" in summary
        assert summary["name_search_enabled"] is True
        assert "name_search_auto_verified_count" in summary
        assert "name_search_candidate_unverified_count" in summary
        assert "name_search_candidate_unverified" in summary["identity_verification_status_counts"]

    def test_audit_trail_includes_name_search(self):
        """Audit trail should include name search steps."""
        provider = _MockNameSearchProvider({
            "华夏沪深300ETF联接C": [
                FundIdentityCandidate(
                    fund_code="000001",
                    fund_name="华夏沪深300ETF联接C",
                    match_score=0.95,
                    match_bucket=BUCKET_HIGH,
                    match_reasons=["high_name_similarity"],
                    risk_flags=[],
                ),
            ],
            "易方达蓝筹精选混合A": [
                FundIdentityCandidate(
                    fund_code="110011",
                    fund_name="易方达蓝筹精选混合A",
                    match_score=0.95,
                    match_bucket=BUCKET_HIGH,
                    match_reasons=["high_name_similarity"],
                    risk_flags=[],
                ),
            ],
        })
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": None,
                        "fund_name": "蚂蚁财富-华夏沪深300ETF联接C-买入",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=provider,
            enable_name_search=True,
        )
        resolutions = result["resolutions"]
        for res in resolutions:
            if "华夏沪深300ETF联接C" in (res.get("raw_fund_name") or ""):
                steps = [s["step"] for s in res["audit_trail"]]
                assert "name_search_auto_verified" in steps
                break
        result = resolve_fund_identities(
            ledger_data={
                "transactions": [
                    {
                        "fund_code": None,
                        "fund_name": "蚂蚁财富-易方达蓝筹精选混合A-买入",
                        "source": "alipay",
                    },
                ],
            },
            name_search_provider=provider,
            enable_name_search=True,
        )
        resolutions = result["resolutions"]
        for res in resolutions:
            if "易方达蓝筹精选混合A" in (res.get("raw_fund_name") or ""):
                steps = [s["step"] for s in res["audit_trail"]]
                assert "name_search_auto_verified" in steps
                break


# ── CLI flag ───────────────────────────────────────────────────────────


class TestResolveFundIdentitiesCLI:
    """Test CLI --enable-name-search flag."""

    def test_enable_name_search_flag(self, tmp_path: Path):
        """--enable-name-search flag should be accepted."""
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text(json.dumps({"transactions": []}), encoding="utf-8")
        output_path = tmp_path / "output.json"

        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "resolve_fund_identities.py"),
             "--ledger", str(ledger_path),
             "--enable-name-search",
             "--output", str(output_path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        output = json.loads(output_path.read_text(encoding="utf-8"))
        assert output["summary"]["name_search_enabled"] is True
