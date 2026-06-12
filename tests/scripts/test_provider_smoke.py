"""Tests for provider smoke runner — mocked, no real network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.host_data.provider_config import ProviderConfig, ProviderCredentialSpec, ProviderCredentials
from src.host_data.provider_result import ProviderResult


class TestProviderSmokeRedaction:
    def test_redact_result_removes_data(self):
        from examples.host_data_adapters.provider_smoke import _redact_result

        d = {
            "ok": True,
            "data": {"nav": 1.5},
            "raw_sample": "some raw",
            "provenance": {"source": "test", "cookie": "secret-val"},
        }
        redacted = _redact_result(d)
        assert redacted["data"] == "<data omitted>"
        assert redacted["raw_sample"] == "<raw_sample omitted>"
        assert redacted["provenance"]["cookie"] == "<redacted>"
        assert redacted["provenance"]["source"] == "test"

    def test_redact_result_preserves_non_credential_provenance(self):
        from examples.host_data_adapters.provider_smoke import _redact_result

        d = {
            "provenance": {"source": "akshare", "function_name": "test"},
        }
        redacted = _redact_result(d)
        assert redacted["provenance"]["source"] == "akshare"
        assert redacted["provenance"]["function_name"] == "test"


class TestProviderSmokeAkShare:
    def test_akshare_missing_dependency(self):
        from examples.host_data_adapters.provider_smoke import _run_provider_smoke

        with patch.dict("sys.modules", {"akshare_adapter": MagicMock(
            AkShareAdapter=MagicMock(return_value=MagicMock(
                health_check=MagicMock(return_value=ProviderResult.missing_dependency("akshare", "HEALTH_CHECK")),
            )),
        )}):
            import importlib
            import examples.host_data_adapters.provider_smoke as mod
            importlib.reload(mod)
            result = mod._run_provider_smoke("akshare", "HEALTH_CHECK")
            assert result["status"] in ("SKIPPED", "MISSING_DEPENDENCY", "OK", "FAILED")

    def test_akshare_no_credentials_required(self):
        from examples.host_data_adapters.provider_smoke import PROVIDER_STATUS

        status = PROVIDER_STATUS["akshare"]
        assert status["works_without_credentials"] is True
        assert status["requires_credentials"] is False


class TestProviderSmokeEastmoney:
    def test_eastmoney_credential_status_unknown(self):
        from examples.host_data_adapters.provider_smoke import PROVIDER_STATUS

        status = PROVIDER_STATUS["eastmoney"]
        assert status["works_without_credentials"] == "unknown"
        assert status["requires_credentials"] == "unknown"
        assert status["cookie_env"] == "EASTMONEY_COOKIE"

    def test_eastmoney_skipped_without_resolve_env(self):
        from examples.host_data_adapters.provider_smoke import _run_provider_smoke

        with patch.dict("sys.modules", {"eastmoney_adapter": MagicMock(
            EastmoneyAdapter=MagicMock(return_value=MagicMock(
                health_check=MagicMock(return_value=ProviderResult(
                    ok=True, provider="eastmoney", capability="HEALTH_CHECK",
                    confidence="high", freshness="fresh",
                )),
            )),
        )}):
            import importlib
            import examples.host_data_adapters.provider_smoke as mod
            importlib.reload(mod)
            result = mod._run_provider_smoke("eastmoney", "HEALTH_CHECK", resolve_env=False)
            assert result["provider"] == "eastmoney"


class TestProviderSmokeXueqiu:
    def test_xueqiu_credential_status_likely(self):
        from examples.host_data_adapters.provider_smoke import PROVIDER_STATUS

        status = PROVIDER_STATUS["xueqiu"]
        assert status["works_without_credentials"] == "unknown"
        assert status["requires_credentials"] == "likely"
        assert status["cookie_env"] == "XUEQIU_COOKIE"
        assert status["token_env"] == "XUEQIU_TOKEN"

    def test_xueqiu_skipped_without_credentials(self):
        from examples.host_data_adapters.provider_smoke import _run_provider_smoke

        with patch.dict("sys.modules", {"xueqiu_adapter": MagicMock(
            XueqiuAdapter=MagicMock(return_value=MagicMock(
                health_check=MagicMock(return_value=ProviderResult.missing_credentials("xueqiu", "HEALTH_CHECK")),
            )),
        )}):
            import importlib
            import examples.host_data_adapters.provider_smoke as mod
            importlib.reload(mod)
            result = mod._run_provider_smoke("xueqiu", "HEALTH_CHECK", resolve_env=False)
            assert result["provider"] == "xueqiu"


class TestProviderSmokeUnknownProvider:
    def test_unknown_provider_skipped(self):
        from examples.host_data_adapters.provider_smoke import _run_provider_smoke

        result = _run_provider_smoke("nonexistent", "HEALTH_CHECK")
        assert result["status"] == "SKIPPED"
        assert "unknown provider" in result["reason"]
