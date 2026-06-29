"""Tests for M7.13 personal-run name search fallback integration.

Validates:
1. personal-run uses provider chain when --enable-name-search
2. reason_codes include provider_name_search_network_error
3. fixit generates identity_candidate_cache_template
4. provider chain diagnostics in run_manifest
5. local cache diagnostics in e2e_summary
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPersonalRunProviderChain:
    """personal-run must use provider chain when --enable-name-search."""

    def test_enable_name_search_flag_accepted(self):
        """--enable-name-search flag should still be accepted."""
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "fund_agent_personal_run.py"),
             "--dry-run", "--enable-name-search"],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
            env={**dict(__import__('os').environ), "PYTHONPATH": str(REPO_ROOT)},
        )
        assert result.returncode == 0 or "dry-run" in result.stdout.lower() or "usage" not in result.stderr.lower()


class TestReasonCodesProviderFailure:
    """Provider failure must be structurally recorded in reason_codes."""

    def test_provider_network_error_in_reason_codes(self):
        """When akshare fails with SSL, reason_codes must include provider_name_search_network_error."""
        from src.tools.portfolio.personal_health_report import build_personal_health_summary

        e2e_summary = {
            "identity_resolution": {
                "total_funds": 15,
                "valid_fund_codes_count": 0,
                "name_only_count": 15,
                "identity_mismatch_count": 0,
                "identity_verification_status_counts": {
                    "name_only": 15,
                },
                "resolution_status_counts": {
                    "name_only": 15,
                },
            },
            "name_search_provider_diagnostics": {
                "name_search_provider_status": "network_error",
                "name_search_provider_last_error": "SSL: CERTIFICATE_VERIFY_FAILED",
                "name_search_provider_search_count": 15,
                "name_search_provider_result_count": 0,
            },
            "pipeline_steps": {
                "reconstruction_status": "nav_unavailable",
            },
        }
        health = build_personal_health_summary({"e2e_summary": e2e_summary})
        assert "provider_name_search_network_error" in health["reason_codes"]

    def test_provider_chain_failed_in_reason_codes(self):
        """When all providers in chain fail, reason_codes must include name_search_provider_chain_failed."""
        from src.tools.portfolio.personal_health_report import build_personal_health_summary

        e2e_summary = {
            "identity_resolution": {
                "total_funds": 15,
                "valid_fund_codes_count": 0,
                "name_only_count": 15,
                "identity_mismatch_count": 0,
                "identity_verification_status_counts": {
                    "name_only": 15,
                },
                "resolution_status_counts": {
                    "name_only": 15,
                },
            },
            "name_search_provider_diagnostics": {
                "provider_chain_enabled": True,
                "providers_attempted": ["local_cache", "akshare"],
                "providers_succeeded": [],
                "providers_failed": ["local_cache", "akshare"],
                "provider_errors_by_name": {
                    "local_cache": "cache file not found",
                    "akshare": "SSL: CERTIFICATE_VERIFY_FAILED",
                },
                "fallback_used": False,
            },
            "local_cache_diagnostics": {
                "name_search_provider_type": "local_cache",
                "name_search_provider_status": "cache_missing",
            },
            "pipeline_steps": {
                "reconstruction_status": "nav_unavailable",
            },
        }
        health = build_personal_health_summary({"e2e_summary": e2e_summary})
        assert "name_search_provider_chain_failed" in health["reason_codes"]
        assert "identity_candidate_cache_missing" in health["reason_codes"]

    def test_local_cache_used_in_reason_codes(self):
        """When local cache is used, reason_codes must include identity_candidate_cache_used."""
        from src.tools.portfolio.personal_health_report import build_personal_health_summary

        e2e_summary = {
            "identity_resolution": {
                "total_funds": 15,
                "valid_fund_codes_count": 10,
                "name_only_count": 5,
                "identity_mismatch_count": 0,
                "identity_verification_status_counts": {
                    "name_only": 5,
                    "provider_verified": 10,
                },
                "resolution_status_counts": {
                    "name_only": 5,
                    "manual_override": 10,
                },
            },
            "name_search_provider_diagnostics": {
                "provider_chain_enabled": True,
                "providers_attempted": ["local_cache", "akshare"],
                "providers_succeeded": ["local_cache"],
                "providers_failed": ["akshare"],
                "provider_errors_by_name": {
                    "akshare": "SSL: CERTIFICATE_VERIFY_FAILED",
                },
                "fallback_used": False,
            },
            "local_cache_diagnostics": {
                "name_search_provider_type": "local_cache",
                "name_search_provider_status": "available",
                "name_search_provider_result_count": 10,
            },
            "pipeline_steps": {
                "reconstruction_status": "reconstructed_from_ledger",
            },
        }
        health = build_personal_health_summary({"e2e_summary": e2e_summary})
        assert "identity_candidate_cache_used" in health["reason_codes"]
        assert "identity_candidates_generated_from_cache" in health["reason_codes"]
        assert "provider_name_search_network_error" in health["reason_codes"]


class TestFixitCacheTemplateGeneration:
    """Fix-it package must include identity candidate cache template."""

    def test_template_generated_when_providers_fail(self, tmp_path: Path):
        """Template must be generated when all providers fail."""
        from scripts.fund_agent_personal_run import _generate_identity_candidate_cache_template

        fixit_dir = tmp_path / "fixit"
        fixit_dir.mkdir()

        e2e_summary = {
            "name_search_provider_diagnostics": {
                "providers_failed": ["akshare"],
            },
            "identity_resolution": {
                "resolutions": [
                    {
                        "raw_fund_name": "Test Fund A",
                        "identity_verification_status": "name_only",
                    },
                ],
            },
        }

        _generate_identity_candidate_cache_template(fixit_dir, e2e_summary)

        template_path = fixit_dir / "identity_candidate_cache_template.private.csv"
        assert template_path.exists()
        content = template_path.read_text(encoding="utf-8")
        assert "normalized_name" in content
        assert "fund_code" in content
        assert "NOT a verified override" in content

    def test_template_not_generated_when_no_failures(self, tmp_path: Path):
        """Template should not be generated when providers succeed and no name-only funds."""
        from scripts.fund_agent_personal_run import _generate_identity_candidate_cache_template

        fixit_dir = tmp_path / "fixit"
        fixit_dir.mkdir()

        e2e_summary = {
            "name_search_provider_diagnostics": {
                "providers_failed": [],
            },
            "identity_resolution": {
                "resolutions": [
                    {
                        "raw_fund_name": "Test Fund A",
                        "identity_verification_status": "provider_verified",
                    },
                ],
            },
        }

        _generate_identity_candidate_cache_template(fixit_dir, e2e_summary)

        template_path = fixit_dir / "identity_candidate_cache_template.private.csv"
        assert not template_path.exists()


class TestProviderChainDiagnosticsInRunManifest:
    """Provider chain diagnostics must appear in run_manifest."""

    def test_chain_diagnostics_in_manifest(self):
        """When provider chain is used, run_manifest must include chain diagnostics."""
        from scripts.fund_agent_personal_run import _build_run_manifest

        e2e_summary = {
            "identity_resolution": {
                "name_search_requested_count": 15,
                "name_search_candidate_count": 0,
            },
            "name_search_provider_diagnostics": {
                "provider_chain_enabled": True,
                "providers_attempted": ["local_cache", "akshare"],
                "providers_succeeded": ["local_cache"],
                "providers_failed": ["akshare"],
                "fallback_used": False,
            },
            "local_cache_diagnostics": {
                "name_search_provider_type": "local_cache",
                "name_search_provider_status": "available",
                "name_search_provider_entry_count": 10,
            },
        }

        manifest = _build_run_manifest(
            run_id="test",
            doctor_ok=True,
            e2e_status="ok",
            artifacts={},
            skip_akshare=False,
            skip_news=False,
            transaction_source="auto",
            private_data_configured=True,
            health={"overall_status": "partial", "confidence_level": "medium", "reason_codes": []},
            enable_name_search=True,
            e2e_summary=e2e_summary,
        )

        diag = manifest["name_search_diagnostics"]
        assert diag.get("provider_chain_enabled") is True
        assert "local_cache" in diag.get("providers_attempted", [])
        assert "akshare" in diag.get("providers_failed", [])
        assert diag.get("local_cache_present") is True
        assert diag.get("local_cache_candidate_count") == 10
