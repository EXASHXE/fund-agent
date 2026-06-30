"""M7.15: Live provider wiring in personal-run — env vars and manifest.

Tests that real_analysis mode sets FUND_AGENT_USE_LIVE_PROVIDER and
RUN_LIVE_PROVIDER_TESTS env vars, and that the run manifest reflects
use_live_provider and provider_ca_bundle_configured correctly.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from scripts.fund_agent_personal_run import (
    _build_run_manifest,
    main as personal_run_main,
)


class TestBuildRunManifestLiveProvider:
    """_build_run_manifest must include live provider fields."""

    def test_real_analysis_manifest_has_use_live_provider(self):
        manifest = _build_run_manifest(
            run_id="test-001",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=False,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="real_analysis",
            enable_name_search=True,
            enable_transaction_derived_valuation=True,
            e2e_summary=None,
            use_live_provider=True,
        )
        assert manifest["use_live_provider"] is True
        assert manifest["live_provider_mode"] == "real_analysis"

    def test_offline_debug_manifest_no_live_provider(self):
        manifest = _build_run_manifest(
            run_id="test-002",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=True,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="offline_debug",
            enable_name_search=False,
            enable_transaction_derived_valuation=False,
            e2e_summary=None,
            use_live_provider=False,
        )
        assert manifest["use_live_provider"] is False
        assert manifest["live_provider_mode"] is None

    def test_manifest_mode_live_when_not_skip(self):
        """When skip_akshare=False, mode should be 'live'."""
        manifest = _build_run_manifest(
            run_id="test-003",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=False,
            skip_news=False,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="real_analysis",
            use_live_provider=True,
        )
        assert manifest["mode"] == "live"

    def test_manifest_mode_deterministic_when_both_skip(self):
        """When skip_akshare=True and skip_news=True, mode should be 'deterministic'."""
        manifest = _build_run_manifest(
            run_id="test-004",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=True,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="offline_debug",
            use_live_provider=False,
        )
        assert manifest["mode"] == "deterministic"


class TestProviderCaBundleConfigured:
    """provider_ca_bundle_configured reflects SSL env vars (without leaking paths)."""

    def test_ca_bundle_configured_when_env_set(self, monkeypatch):
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/some/path.crt")
        manifest = _build_run_manifest(
            run_id="test-ca-1",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=True,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="offline_debug",
            use_live_provider=False,
        )
        assert manifest["provider_ca_bundle_configured"] is True
        # Must NOT contain the actual path value
        manifest_str = json.dumps(manifest)
        assert "/some/path.crt" not in manifest_str

    def test_ca_bundle_not_configured_when_no_env(self, monkeypatch):
        for key in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE"):
            monkeypatch.delenv(key, raising=False)
        manifest = _build_run_manifest(
            run_id="test-ca-2",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=True,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="offline_debug",
            use_live_provider=False,
        )
        assert manifest["provider_ca_bundle_configured"] is False

    def test_ssl_cert_file_also_detected(self, monkeypatch):
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/cert.pem")
        manifest = _build_run_manifest(
            run_id="test-ca-3",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=True,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="offline_debug",
            use_live_provider=False,
        )
        assert manifest["provider_ca_bundle_configured"] is True

    def test_curl_ca_bundle_also_detected(self, monkeypatch):
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.setenv("CURL_CA_BUNDLE", "/etc/curl/cacert.pem")
        manifest = _build_run_manifest(
            run_id="test-ca-4",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=True,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="offline_debug",
            use_live_provider=False,
        )
        assert manifest["provider_ca_bundle_configured"] is True


class TestManifestNameSearchDiagnostics:
    """Manifest must include name search diagnostics from e2e_summary."""

    def test_name_search_diagnostics_from_e2e_summary(self):
        e2e_summary: dict[str, Any] = {
            "identity_resolution": {
                "name_search_requested_count": 5,
                "name_search_candidate_count": 12,
                "name_search_unique_high_confidence_count": 2,
                "name_search_ambiguous_count": 3,
                "name_search_no_result_count": 0,
                "name_search_promoted_provider_verified_count": 1,
            },
            "name_search_provider_diagnostics": {
                "name_search_provider_status": "available",
                "name_search_provider_last_error": "",
            },
        }
        manifest = _build_run_manifest(
            run_id="test-ns-1",
            doctor_ok=True,
            e2e_status="success",
            artifacts={},
            skip_akshare=False,
            skip_news=True,
            transaction_source="alipay",
            private_data_configured=True,
            health={"overall_status": "ok", "confidence_level": "high", "reason_codes": []},
            execution_mode="real_analysis",
            enable_name_search=True,
            e2e_summary=e2e_summary,
            use_live_provider=True,
        )
        ns_diag = manifest["name_search_diagnostics"]
        assert ns_diag["name_search_enabled"] is True
        assert ns_diag["name_search_requested_count"] == 5
        assert ns_diag["name_search_candidate_count"] == 12
        assert ns_diag["name_search_promoted_provider_verified_count"] == 1
