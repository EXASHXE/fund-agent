"""Live provider adapter tests — opt-in only.

These tests require real provider dependencies and/or network access.
They are skipped by default. To run them, set the environment variable:

    FUND_AGENT_RUN_LIVE_PROVIDER_TESTS=1

Do NOT run these in CI unless credentials/network are intentionally configured.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live_provider

_LIVE_ENABLED = bool(os.getenv("FUND_AGENT_RUN_LIVE_PROVIDER_TESTS"))


@pytest.mark.skipif(not _LIVE_ENABLED, reason="live provider tests are opt-in; set FUND_AGENT_RUN_LIVE_PROVIDER_TESTS=1")
class TestAkShareLive:
    def test_health_check_live(self):
        from examples.host_data_adapters.akshare_adapter import AkShareAdapter
        adapter = AkShareAdapter()
        result = adapter.health_check()
        if result.ok:
            assert result.provider == "akshare"
        else:
            assert "MISSING_DEPENDENCY" in result.errors

    def test_fund_nav_history_live(self):
        from examples.host_data_adapters.akshare_adapter import AkShareAdapter
        adapter = AkShareAdapter()
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        if not result.ok and "MISSING_DEPENDENCY" in result.errors:
            pytest.skip("akshare not installed")
        assert result.provider == "akshare"


@pytest.mark.skipif(not _LIVE_ENABLED, reason="live provider tests are opt-in; set FUND_AGENT_RUN_LIVE_PROVIDER_TESTS=1")
class TestEastmoneyLive:
    def test_health_check_live(self):
        from examples.host_data_adapters.eastmoney_adapter import EastmoneyAdapter
        adapter = EastmoneyAdapter()
        result = adapter.health_check()
        assert result.provider == "eastmoney"


@pytest.mark.skipif(not _LIVE_ENABLED, reason="live provider tests are opt-in; set FUND_AGENT_RUN_LIVE_PROVIDER_TESTS=1")
class TestXueqiuLive:
    def test_health_check_live_no_creds(self):
        from examples.host_data_adapters.xueqiu_adapter import XueqiuAdapter
        adapter = XueqiuAdapter()
        result = adapter.health_check()
        assert not result.ok
        assert "MISSING_CREDENTIALS" in result.errors

    def test_health_check_live_with_creds(self):
        cookie = os.getenv("XUEQIU_COOKIE")
        token = os.getenv("XUEQIU_TOKEN")
        if not cookie or not token:
            pytest.skip("XUEQIU_COOKIE and XUEQIU_TOKEN not set")
        from examples.host_data_adapters.xueqiu_adapter import XueqiuAdapter
        from src.host_data.provider_config import ProviderConfig, ProviderCredentials
        config = ProviderConfig(
            provider_name="xueqiu",
            enabled=True,
            require_credentials=True,
            credentials=ProviderCredentials(cookie=cookie, token=token),
        )
        adapter = XueqiuAdapter(config=config)
        result = adapter.health_check()
        assert result.provider == "xueqiu"
