"""Tests for Xueqiu adapter — mocked, no real network."""

from __future__ import annotations

import pytest

from src.host_data.provider_config import ProviderConfig, ProviderCredentials
from src.host_data.provider_contracts import ProviderCapability
from src.host_data.provider_result import ProviderResult


def _make_adapter_with_creds(cookie="test-cookie", token="test-token"):
    from examples.host_data_adapters.xueqiu_adapter import XueqiuAdapter

    config = ProviderConfig(
        provider_name="xueqiu",
        enabled=False,
        priority=30,
        require_credentials=True,
        credentials=ProviderCredentials(
            cookie=cookie,
            token=token,
            user_agent="TestAgent/1.0",
        ),
    )
    return XueqiuAdapter(config=config)


def _make_adapter_no_creds():
    from examples.host_data_adapters.xueqiu_adapter import XueqiuAdapter

    config = ProviderConfig(
        provider_name="xueqiu",
        enabled=False,
        priority=30,
        require_credentials=True,
        credentials=ProviderCredentials(user_agent="TestAgent/1.0"),
    )
    return XueqiuAdapter(config=config)


class TestXueqiuHealthCheck:
    def test_health_check_missing_credentials(self):
        adapter = _make_adapter_no_creds()
        result = adapter.health_check()
        assert not result.ok
        assert "MISSING_CREDENTIALS" in result.errors

    def test_health_check_ok_with_credentials(self):
        adapter = _make_adapter_with_creds()
        result = adapter.health_check()
        assert result.ok


class TestXueqiuCredentials:
    def test_credential_assessment(self):
        adapter = _make_adapter_with_creds()
        result = adapter.assess_credentials_requirement()
        assert result.ok
        assert result.data["works_without_credentials"] == "unknown"
        assert result.data["requires_credentials"] == "likely"
        assert result.data["cookie_env"] == "XUEQIU_COOKIE"
        assert result.data["token_env"] == "XUEQIU_TOKEN"
        assert result.data["enabled_by_default"] is False

    def test_credential_trace_redacts(self):
        adapter = _make_adapter_with_creds(cookie="super-secret-cookie", token="super-secret-token")
        trace = adapter._credential_trace()
        assert "super-secret" not in str(trace)
        assert trace["cookie"] != "super-secret-cookie"
        assert trace["token"] != "super-secret-token"

    def test_missing_credentials_returns_missing(self):
        adapter = _make_adapter_no_creds()
        result = adapter.get_stock_quote("SH000001")
        assert not result.ok
        assert "MISSING_CREDENTIALS" in result.errors

    def test_missing_cookie_only_returns_missing(self):
        config = ProviderConfig(
            provider_name="xueqiu",
            enabled=False,
            require_credentials=True,
            credentials=ProviderCredentials(
                token="test-token",
                user_agent="TestAgent/1.0",
            ),
        )
        from examples.host_data_adapters.xueqiu_adapter import XueqiuAdapter
        adapter = XueqiuAdapter(config=config)
        result = adapter.get_stock_quote("SH000001")
        assert not result.ok
        assert "MISSING_CREDENTIALS" in result.errors


class TestXueqiuNotImplemented:
    def test_stock_quote_not_implemented(self):
        adapter = _make_adapter_with_creds()
        result = adapter.get_stock_quote("SH000001")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors

    def test_stock_history_not_implemented(self):
        adapter = _make_adapter_with_creds()
        result = adapter.get_stock_history("SH000001", "20240101", "20241231")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors

    def test_social_sentiment_not_implemented(self):
        adapter = _make_adapter_with_creds()
        result = adapter.get_social_sentiment("fund")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors


class TestXueqiuResponseDetection:
    def test_detect_auth_required(self):
        adapter = _make_adapter_with_creds()
        result = adapter._detect_response_issue("请先登录后继续访问")
        assert result is not None
        assert "PROVIDER_AUTH_REQUIRED" in result.errors

    def test_detect_rate_limited(self):
        adapter = _make_adapter_with_creds()
        result = adapter._detect_response_issue("请求过于频繁，请稍后再试")
        assert result is not None
        assert "PROVIDER_RATE_LIMITED" in result.errors

    def test_detect_blocked(self):
        adapter = _make_adapter_with_creds()
        result = adapter._detect_response_issue("access denied")
        assert result is not None
        assert "PROVIDER_BLOCKED" in result.errors

    def test_no_issue_detected(self):
        adapter = _make_adapter_with_creds()
        result = adapter._detect_response_issue("normal response data")
        assert result is None


class TestXueqiuHeaders:
    def test_cookie_in_headers_when_present(self):
        adapter = _make_adapter_with_creds(cookie="my-cookie")
        headers = adapter._make_headers()
        assert headers["Cookie"] == "my-cookie"

    def test_no_cookie_in_headers_when_absent(self):
        adapter = _make_adapter_no_creds()
        headers = adapter._make_headers()
        assert "Cookie" not in headers


class TestXueqiuProvenance:
    def test_provenance_present(self):
        adapter = _make_adapter_with_creds()
        result = adapter.get_stock_quote("SH000001")
        assert result.provenance.get("source") == "xueqiu"
        assert result.provenance.get("credentials_present") is True

    def test_credentials_not_in_provenance(self):
        adapter = _make_adapter_with_creds(cookie="secret-cookie", token="secret-token")
        result = adapter.get_stock_quote("SH000001")
        prov_str = str(result.provenance)
        assert "secret-cookie" not in prov_str
        assert "secret-token" not in prov_str


class TestXueqiuDisabledByDefault:
    def test_default_config_disabled(self):
        from examples.host_data_adapters.xueqiu_adapter import XueqiuAdapter

        adapter = XueqiuAdapter()
        assert adapter._config.enabled is False

    def test_default_config_require_credentials(self):
        from examples.host_data_adapters.xueqiu_adapter import XueqiuAdapter

        adapter = XueqiuAdapter()
        assert adapter._config.require_credentials is True
