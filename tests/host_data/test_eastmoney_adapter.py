"""Tests for Eastmoney adapter — mocked, no real network."""

from __future__ import annotations

import pytest

from src.host_data.provider_config import ProviderConfig, ProviderCredentials
from src.host_data.provider_contracts import ProviderCapability
from src.host_data.provider_result import ProviderResult


def _make_adapter_with_cookie(cookie="test-cookie-val", require_credentials=False):
    from examples.host_data_adapters.eastmoney_adapter import EastmoneyAdapter

    config = ProviderConfig(
        provider_name="eastmoney",
        enabled=False,
        priority=20,
        require_credentials=require_credentials,
        credentials=ProviderCredentials(
            cookie=cookie,
            user_agent="TestAgent/1.0",
        ),
    )
    return EastmoneyAdapter(config=config)


def _make_adapter_no_cookie(require_credentials=False):
    from examples.host_data_adapters.eastmoney_adapter import EastmoneyAdapter

    config = ProviderConfig(
        provider_name="eastmoney",
        enabled=False,
        priority=20,
        require_credentials=require_credentials,
        credentials=ProviderCredentials(user_agent="TestAgent/1.0"),
    )
    return EastmoneyAdapter(config=config)


class TestEastmoneyHealthCheck:
    def test_health_check_ok(self):
        adapter = _make_adapter_with_cookie()
        result = adapter.health_check()
        assert result.ok
        assert result.provider == "eastmoney"

    def test_health_check_no_cookie_still_ok(self):
        adapter = _make_adapter_no_cookie()
        result = adapter.health_check()
        assert result.ok


class TestEastmoneyCredentials:
    def test_credential_assessment(self):
        adapter = _make_adapter_with_cookie()
        result = adapter.assess_credentials_requirement()
        assert result.ok
        assert result.data["works_without_credentials"] == "unknown"
        assert result.data["requires_credentials"] == "unknown"
        assert result.data["cookie_env"] == "EASTMONEY_COOKIE"

    def test_credential_trace_redacts_cookie(self):
        adapter = _make_adapter_with_cookie(cookie="super-secret-cookie-value")
        trace = adapter._credential_trace()
        assert trace["cookie"] == "<redacted>"
        assert "super-secret" not in str(trace)

    def test_missing_cookie_when_required(self):
        adapter = _make_adapter_no_cookie(require_credentials=True)
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert not result.ok
        assert "MISSING_CREDENTIALS" in result.errors

    def test_cookie_included_in_headers(self):
        adapter = _make_adapter_with_cookie(cookie="my-cookie")
        headers = adapter._make_headers()
        assert headers["Cookie"] == "my-cookie"

    def test_no_cookie_not_in_headers(self):
        adapter = _make_adapter_no_cookie()
        headers = adapter._make_headers()
        assert "Cookie" not in headers


class TestEastmoneyNotImplemented:
    def test_fund_nav_history_not_implemented(self):
        adapter = _make_adapter_with_cookie()
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors

    def test_fund_profile_not_implemented(self):
        adapter = _make_adapter_with_cookie()
        result = adapter.get_fund_profile("000001")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors

    def test_stock_quote_not_implemented(self):
        adapter = _make_adapter_with_cookie()
        result = adapter.get_stock_quote("SH000001")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors


class TestEastmoneyBlockedDetection:
    def test_detect_captcha(self):
        adapter = _make_adapter_with_cookie()
        indicator = adapter._detect_blocked("请输入验证码继续访问")
        assert indicator is not None

    def test_detect_login_required(self):
        adapter = _make_adapter_with_cookie()
        indicator = adapter._detect_blocked("请先登录")
        assert indicator is not None

    def test_no_block_detected(self):
        adapter = _make_adapter_with_cookie()
        indicator = adapter._detect_blocked("normal response data")
        assert indicator is None

    def test_detect_rate_limited(self):
        adapter = _make_adapter_with_cookie()
        indicator = adapter._detect_rate_limited("请求过于频繁")
        assert indicator is not None

    def test_no_rate_limit_detected(self):
        adapter = _make_adapter_with_cookie()
        indicator = adapter._detect_rate_limited("normal response data")
        assert indicator is None


class TestEastmoneyProvenance:
    def test_provenance_present(self):
        adapter = _make_adapter_with_cookie()
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert result.provenance.get("source") == "eastmoney"
        assert "endpoint_name" in result.provenance
        assert "url_host" in result.provenance

    def test_credentials_not_in_provenance(self):
        adapter = _make_adapter_with_cookie(cookie="secret-cookie")
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        prov_str = str(result.provenance)
        assert "secret-cookie" not in prov_str
