"""Tests for data provider contracts — v1.7."""

from __future__ import annotations

import pytest

from src.host_data.provider_contracts import FundDataProvider, NewsDataProvider, ProviderCapability, StockDataProvider
from src.host_data.provider_config import ProviderConfig, ProviderCredentials
from src.host_data.provider_result import ProviderResult
from src.host_data.provider_registry import ProviderRegistry


class TestProviderCapability:
    def test_capability_values(self):
        assert ProviderCapability.FUND_NAV_HISTORY == "FUND_NAV_HISTORY"
        assert ProviderCapability.FUND_PROFILE == "FUND_PROFILE"
        assert ProviderCapability.STOCK_QUOTE == "STOCK_QUOTE"
        assert ProviderCapability.SOCIAL_SENTIMENT == "SOCIAL_SENTIMENT"
        assert ProviderCapability.SEARCH == "SEARCH"


class TestProviderCredentials:
    def test_default_empty(self):
        c = ProviderCredentials()
        assert c.api_key is None
        assert c.token is None
        assert c.cookie is None
        assert not c.has_any()

    def test_has_any(self):
        c = ProviderCredentials(api_key="test")
        assert c.has_any()

    def test_redacted(self):
        c = ProviderCredentials(api_key="secret", token="tok", cookie="ck", user_agent="ua")
        r = c.redacted()
        assert r["api_key"] == "<redacted>"
        assert r["token"] == "<redacted>"
        assert r["cookie"] == "<redacted>"
        assert r["user_agent"] == "ua"

    def test_redacted_none(self):
        c = ProviderCredentials()
        r = c.redacted()
        assert r["api_key"] is None
        assert r["token"] is None


class TestProviderConfig:
    def test_to_dict_redacts_credentials(self):
        c = ProviderConfig(
            provider_name="test",
            credentials=ProviderCredentials(api_key="secret"),
        )
        d = c.to_dict()
        assert d["credentials"]["api_key"] == "<redacted>"
        assert d["provider_name"] == "test"

    def test_defaults(self):
        c = ProviderConfig(provider_name="test")
        assert c.enabled is True
        assert c.priority == 100
        assert c.require_credentials is False


class TestProviderResult:
    def test_to_dict(self):
        r = ProviderResult(ok=True, provider="test", capability="FUND_NAV_HISTORY", data={"nav": 1.0})
        d = r.to_dict()
        assert d["ok"] is True
        assert d["provider"] == "test"
        assert d["data"]["nav"] == 1.0

    def test_missing_credentials(self):
        r = ProviderResult.missing_credentials("test", "FUND_NAV_HISTORY")
        assert r.ok is False
        assert "MISSING_CREDENTIALS" in r.errors

    def test_missing_dependency(self):
        r = ProviderResult.missing_dependency("test", "FUND_NAV_HISTORY")
        assert r.ok is False
        assert "MISSING_DEPENDENCY" in r.errors

    def test_provider_blocked(self):
        r = ProviderResult.provider_blocked("test", "FUND_NAV_HISTORY", "captcha")
        assert r.ok is False
        assert "PROVIDER_BLOCKED" in r.errors

    def test_provider_auth_required(self):
        r = ProviderResult.provider_auth_required("test", "FUND_NAV_HISTORY")
        assert r.ok is False
        assert "PROVIDER_AUTH_REQUIRED" in r.errors

    def test_provider_rate_limited(self):
        r = ProviderResult.provider_rate_limited("test", "FUND_NAV_HISTORY")
        assert r.ok is False
        assert "PROVIDER_RATE_LIMITED" in r.errors

    def test_empty_result(self):
        r = ProviderResult.empty_result("test", "FUND_NAV_HISTORY")
        assert r.ok is False
        assert "EMPTY_RESULT" in r.errors

    def test_partial(self):
        r = ProviderResult.partial("test", "FUND_NAV_HISTORY", ["incomplete data"])
        assert r.ok is False
        assert "PARTIAL" in r.errors
        assert "incomplete data" in r.warnings

    def test_network_error(self):
        r = ProviderResult.network_error("test", "FUND_NAV_HISTORY", "timeout")
        assert r.ok is False
        assert "NETWORK_ERROR" in r.errors
        assert "timeout" in r.errors

    def test_unexpected_schema(self):
        r = ProviderResult.unexpected_schema(
            "test", "FUND_NAV_HISTORY",
            expected={"date", "nav"}, actual={"date", "price"},
        )
        assert r.ok is False
        assert "UNEXPECTED_SCHEMA" in r.errors
        assert any("missing" in w for w in r.warnings)
        assert any("extra" in w for w in r.warnings)

    def test_not_implemented(self):
        r = ProviderResult.not_implemented("test", "FUND_NAV_HISTORY")
        assert r.ok is False
        assert "NOT_IMPLEMENTED" in r.errors

    def test_error(self):
        r = ProviderResult.error("test", "FUND_NAV_HISTORY", "something broke")
        assert r.ok is False
        assert "ERROR" in r.errors
        assert "something broke" in r.errors

    def test_with_override(self):
        r = ProviderResult.not_implemented("test", "FUND_NAV_HISTORY")
        r2 = r._with(fund_code="000001", as_of="2024-01-01")
        assert r2.fund_code == "000001"
        assert r2.as_of == "2024-01-01"
        assert "NOT_IMPLEMENTED" in r2.errors

    def test_new_fields_default(self):
        r = ProviderResult(ok=True, provider="test", capability="FUND_NAV_HISTORY")
        assert r.fetched_at is None
        assert r.limitations == []
        assert r.credential_requirement is None

    def test_to_dict_includes_new_fields(self):
        r = ProviderResult(
            ok=True, provider="test", capability="FUND_NAV_HISTORY",
            fetched_at="2024-01-01T00:00:00Z",
            limitations=["partial data"],
            credential_requirement={"requires_credentials": False},
        )
        d = r.to_dict()
        assert d["fetched_at"] == "2024-01-01T00:00:00Z"
        assert d["limitations"] == ["partial data"]
        assert d["credential_requirement"]["requires_credentials"] is False


class TestProviderRegistry:
    def test_register_and_list(self):
        reg = ProviderRegistry()
        reg.register(ProviderConfig(provider_name="akshare", priority=10))
        reg.register(ProviderConfig(provider_name="eastmoney", priority=20))
        assert reg.list_providers() == ["akshare", "eastmoney"]

    def test_get(self):
        reg = ProviderRegistry()
        reg.register(ProviderConfig(provider_name="akshare"))
        assert reg.get("akshare") is not None
        assert reg.get("missing") is None

    def test_enabled_providers_sorted_by_priority(self):
        reg = ProviderRegistry()
        reg.register(ProviderConfig(provider_name="eastmoney", priority=20, enabled=True))
        reg.register(ProviderConfig(provider_name="akshare", priority=10, enabled=True))
        reg.register(ProviderConfig(provider_name="xueqiu", priority=30, enabled=False))
        names = [p.provider_name for p in reg.enabled_providers()]
        assert names == ["akshare", "eastmoney"]

    def test_providers_for_capability(self):
        reg = ProviderRegistry()
        reg.register(ProviderConfig(
            provider_name="akshare",
            priority=10,
            capabilities=["FUND_NAV_HISTORY", "FUND_PROFILE"],
        ))
        reg.register(ProviderConfig(
            provider_name="eastmoney",
            priority=20,
            capabilities=["FUND_NAV_HISTORY", "FUND_RANKING"],
        ))
        nav_providers = reg.providers_for_capability("FUND_NAV_HISTORY")
        assert len(nav_providers) == 2
        assert nav_providers[0].provider_name == "akshare"
        ranking_providers = reg.providers_for_capability("FUND_RANKING")
        assert len(ranking_providers) == 1
        assert ranking_providers[0].provider_name == "eastmoney"

    def test_to_dict(self):
        reg = ProviderRegistry()
        reg.register(ProviderConfig(provider_name="akshare", priority=10))
        d = reg.to_dict()
        assert "akshare" in d["providers"]


class TestProviderProtocolCompliance:
    def test_fund_data_provider_protocol(self):
        class MockFundProvider:
            name = "mock"
            capabilities = {ProviderCapability.FUND_NAV_HISTORY}
            def health_check(self) -> ProviderResult:
                return ProviderResult(ok=True, provider="mock", capability="HEALTH_CHECK")
            def get_fund_nav_history(self, fund_code, start, end) -> ProviderResult:
                return ProviderResult(ok=True, provider="mock", capability="FUND_NAV_HISTORY", fund_code=fund_code)
            def get_fund_profile(self, fund_code) -> ProviderResult:
                return ProviderResult(ok=True, provider="mock", capability="FUND_PROFILE", fund_code=fund_code)
            def get_fund_holdings(self, fund_code, as_of=None) -> ProviderResult:
                return ProviderResult(ok=True, provider="mock", capability="FUND_HOLDINGS", fund_code=fund_code)
            def get_fee_schedule(self, fund_code) -> ProviderResult:
                return ProviderResult(ok=True, provider="mock", capability="FUND_FEE_SCHEDULE", fund_code=fund_code)
            def get_redemption_rules(self, fund_code) -> ProviderResult:
                return ProviderResult(ok=True, provider="mock", capability="FUND_REDEMPTION_RULES", fund_code=fund_code)

        provider = MockFundProvider()
        assert isinstance(provider, FundDataProvider)
