"""Tests for provider fallback policy — v1.7."""

from __future__ import annotations

from src.host_data.fallback_policy import select_provider_order
from src.host_data.provider_config import ProviderConfig
from src.host_data.provider_contracts import ProviderCapability
from src.host_data.provider_registry import ProviderRegistry


def _make_registry() -> ProviderRegistry:
    reg = ProviderRegistry()
    reg.register(ProviderConfig(
        provider_name="akshare",
        priority=10,
        enabled=True,
        capabilities=["FUND_NAV_HISTORY", "FUND_PROFILE", "INDEX_HISTORY"],
    ))
    reg.register(ProviderConfig(
        provider_name="eastmoney",
        priority=20,
        enabled=True,
        capabilities=["FUND_NAV_HISTORY", "FUND_RANKING", "STOCK_QUOTE"],
    ))
    reg.register(ProviderConfig(
        provider_name="xueqiu",
        priority=30,
        enabled=False,
        capabilities=["STOCK_QUOTE", "SOCIAL_SENTIMENT"],
    ))
    return reg


class TestSelectProviderOrder:
    def test_returns_providers_sorted_by_priority(self):
        reg = _make_registry()
        order = select_provider_order(ProviderCapability.FUND_NAV_HISTORY, reg)
        assert order == ["akshare", "eastmoney"]

    def test_excludes_disabled_providers(self):
        reg = _make_registry()
        order = select_provider_order(ProviderCapability.STOCK_QUOTE, reg)
        assert "xueqiu" not in order
        assert order == ["eastmoney"]

    def test_empty_when_no_capability(self):
        reg = _make_registry()
        order = select_provider_order(ProviderCapability.SEARCH, reg)
        assert order == []

    def test_preferred_ranks_first(self):
        reg = _make_registry()
        order = select_provider_order(
            ProviderCapability.FUND_NAV_HISTORY, reg, preferred=["eastmoney"],
        )
        assert order[0] == "eastmoney"
        assert order[1] == "akshare"

    def test_preferred_ignored_if_not_capable(self):
        reg = _make_registry()
        order = select_provider_order(
            ProviderCapability.FUND_NAV_HISTORY, reg, preferred=["xueqiu"],
        )
        assert "xueqiu" not in order
        assert order[0] == "akshare"
