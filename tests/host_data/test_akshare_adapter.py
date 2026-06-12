"""Tests for AkShare adapter — mocked, no real network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.host_data.provider_config import ProviderConfig, ProviderCredentials
from src.host_data.provider_contracts import ProviderCapability
from src.host_data.provider_result import ProviderResult


def _make_adapter_with_mock_akshare(df_mock=None):
    from examples.host_data_adapters.akshare_adapter import AkShareAdapter

    adapter = AkShareAdapter()
    mock_ak = MagicMock()
    if df_mock is not None:
        mock_ak.fund_open_fund_info_em.return_value = df_mock
    adapter._akshare = mock_ak
    return adapter


class TestAkShareHealthCheck:
    def test_health_check_ok_with_akshare(self):
        adapter = _make_adapter_with_mock_akshare()
        result = adapter.health_check()
        assert result.ok
        assert result.provider == "akshare"
        assert result.capability == "HEALTH_CHECK"

    def test_health_check_missing_dependency(self):
        from examples.host_data_adapters.akshare_adapter import AkShareAdapter

        adapter = AkShareAdapter()
        adapter._akshare = None
        result = adapter.health_check()
        assert not result.ok
        assert "MISSING_DEPENDENCY" in result.errors


class TestAkShareFundNavHistory:
    def test_success_response(self):
        mock_df = MagicMock()
        mock_df.columns = ["净值日期", "单位净值", "日增长率"]
        mock_df.to_dict.return_value = [{"净值日期": "2024-01-01", "单位净值": 1.5}]

        adapter = _make_adapter_with_mock_akshare(df_mock=mock_df)
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert result.ok
        assert result.fund_code == "000001"
        assert result.provider == "akshare"
        assert result.capability == ProviderCapability.FUND_NAV_HISTORY
        assert result.provenance["function_name"] == "fund_open_fund_info_em"
        assert result.provenance["source"] == "akshare"

    def test_missing_dependency(self):
        from examples.host_data_adapters.akshare_adapter import AkShareAdapter

        adapter = AkShareAdapter()
        adapter._akshare = None
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert not result.ok
        assert "MISSING_DEPENDENCY" in result.errors

    def test_unexpected_columns(self):
        mock_df = MagicMock()
        mock_df.columns = ["wrong_col1", "wrong_col2"]
        mock_df.to_dict.return_value = []

        adapter = _make_adapter_with_mock_akshare(df_mock=mock_df)
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert not result.ok
        assert "UNEXPECTED_COLUMNS" in result.errors

    def test_exception_returns_error(self):
        mock_ak = MagicMock()
        mock_ak.fund_open_fund_info_em.side_effect = RuntimeError("network error")

        from examples.host_data_adapters.akshare_adapter import AkShareAdapter

        adapter = AkShareAdapter()
        adapter._akshare = mock_ak
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert not result.ok
        assert "network error" in str(result.errors)


class TestAkShareNotImplemented:
    def test_fund_profile_not_implemented(self):
        adapter = _make_adapter_with_mock_akshare()
        result = adapter.get_fund_profile("000001")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors

    def test_fund_holdings_not_implemented(self):
        adapter = _make_adapter_with_mock_akshare()
        result = adapter.get_fund_holdings("000001")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors

    def test_index_history_not_implemented(self):
        adapter = _make_adapter_with_mock_akshare()
        result = adapter.get_index_history("SH000001", "20240101", "20241231")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors

    def test_stock_history_not_implemented(self):
        adapter = _make_adapter_with_mock_akshare()
        result = adapter.get_stock_history("SH000001", "20240101", "20241231")
        assert not result.ok
        assert "NOT_IMPLEMENTED" in result.errors


class TestAkShareCredentials:
    def test_no_credentials_required(self):
        from examples.host_data_adapters.akshare_adapter import AkShareAdapter

        adapter = AkShareAdapter()
        cred_result = adapter.assess_credentials_requirement()
        assert cred_result.ok
        assert cred_result.data["works_without_credentials"] is True
        assert cred_result.data["requires_credentials"] is False

    def test_provenance_present(self):
        adapter = _make_adapter_with_mock_akshare()
        result = adapter.get_fund_nav_history("000001", "20240101", "20241231")
        assert "provenance" in result.to_dict()
        assert result.provenance.get("source") == "akshare"

    def test_fee_schedule_not_supported(self):
        adapter = _make_adapter_with_mock_akshare()
        result = adapter.get_fee_schedule("000001")
        assert not result.ok
        assert "NOT_SUPPORTED" in result.errors
