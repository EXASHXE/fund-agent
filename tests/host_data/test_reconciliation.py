"""Tests for provider result reconciliation — v1.7."""

from __future__ import annotations

from src.host_data.reconciliation import compare_provider_results
from src.host_data.provider_result import ProviderResult


class TestCompareProviderResults:
    def test_insufficient_when_no_valid(self):
        r1 = ProviderResult(ok=False, provider="a", capability="FUND_NAV_HISTORY", errors=["FAIL"])
        r2 = ProviderResult(ok=False, provider="b", capability="FUND_NAV_HISTORY", errors=["FAIL"])
        result = compare_provider_results([r1, r2])
        assert result["status"] == "INSUFFICIENT"
        assert "NO_VALID_RESULTS" in result["warnings"]

    def test_consistent_single_source(self):
        r1 = ProviderResult(
            ok=True, provider="akshare", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5}, confidence="high", freshness="fresh",
        )
        result = compare_provider_results([r1])
        assert result["status"] == "CONSISTENT"
        assert "SINGLE_SOURCE" in result["warnings"]
        assert result["primary_provider"] == "akshare"

    def test_consistent_when_agreeing(self):
        r1 = ProviderResult(
            ok=True, provider="akshare", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5, "date": "2025-01-01"}, confidence="high", freshness="fresh",
        )
        r2 = ProviderResult(
            ok=True, provider="eastmoney", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5, "date": "2025-01-01"}, confidence="high", freshness="fresh",
        )
        result = compare_provider_results([r1, r2])
        assert result["status"] == "CONSISTENT"
        assert result["discrepancies"] == []

    def test_divergent_when_nav_differs(self):
        r1 = ProviderResult(
            ok=True, provider="akshare", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5}, confidence="high", freshness="fresh",
        )
        r2 = ProviderResult(
            ok=True, provider="eastmoney", capability="FUND_NAV_HISTORY",
            data={"nav": 1.8}, confidence="high", freshness="fresh",
        )
        result = compare_provider_results([r1, r2])
        assert result["status"] == "DIVERGENT"
        assert len(result["discrepancies"]) > 0

    def test_divergent_when_field_missing(self):
        r1 = ProviderResult(
            ok=True, provider="akshare", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5, "acc_nav": 2.0}, confidence="high", freshness="fresh",
        )
        r2 = ProviderResult(
            ok=True, provider="eastmoney", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5}, confidence="high", freshness="fresh",
        )
        result = compare_provider_results([r1, r2])
        assert result["status"] == "DIVERGENT"
        assert any(d["issue"] == "MISSING_IN_SECOND" for d in result["discrepancies"])

    def test_small_difference_not_divergent(self):
        r1 = ProviderResult(
            ok=True, provider="akshare", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5000}, confidence="high", freshness="fresh",
        )
        r2 = ProviderResult(
            ok=True, provider="eastmoney", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5005}, confidence="high", freshness="fresh",
        )
        result = compare_provider_results([r1, r2])
        assert result["status"] == "CONSISTENT"

    def test_mixed_valid_and_invalid(self):
        r1 = ProviderResult(
            ok=True, provider="akshare", capability="FUND_NAV_HISTORY",
            data={"nav": 1.5}, confidence="high", freshness="fresh",
        )
        r2 = ProviderResult(
            ok=False, provider="eastmoney", capability="FUND_NAV_HISTORY",
            errors=["PROVIDER_BLOCKED"],
        )
        result = compare_provider_results([r1, r2])
        assert result["status"] == "CONSISTENT"
        assert "SINGLE_SOURCE" in result["warnings"]
