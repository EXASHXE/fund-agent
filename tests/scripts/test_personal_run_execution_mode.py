"""Tests for personal-run execution mode (--execution-mode).

All test data is synthetic — no real fund names, amounts, or transaction IDs.
M7.7: Validates execution_mode behavior for canonical runtime enforcement.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from scripts.fund_agent_personal_run import main as personal_run_main


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_private_data(tmp_path: Path) -> Path:
    """Create a minimal private_data directory with synthetic data."""
    pd = tmp_path / "private_data"
    pd.mkdir()
    portfolio_input = {
        "schema_version": "portfolio_input.v1",
        "holdings": [],
        "transactions": [
            {
                "date": "2024-01-15",
                "fund_code": "000001",
                "fund_name": "Synthetic Fund A",
                "action": "buy",
                "amount": 1000.0,
            }
        ],
    }
    (pd / "portfolio_input.private.json").write_text(
        json.dumps(portfolio_input, ensure_ascii=False), encoding="utf-8"
    )
    return pd


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    od = tmp_path / "local_reports"
    od.mkdir()
    return od


def _fake_e2e_return_0(argv, *, env_overrides=None):
    """Stub e2e_main that returns 0 without running the pipeline."""
    # Write a minimal e2e_summary to the run_dir
    run_dir_idx = argv.index("--output-dir")
    run_dir = Path(argv[run_dir_idx + 1])
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": "test-001",
        "status": "partial",
        "warnings": [],
        "errors": [],
        "steps_completed": ["resolve_fund_identities"],
        "personal_health_report": {
            "schema_version": "personal_health_report.v1",
            "overall_status": "partial",
            "confidence_level": "medium",
            "reason_codes": ["partial_nav_coverage"],
        },
    }
    (run_dir / "e2e_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    return 0


# ── Test: execution_mode defaults ─────────────────────────────────────


class TestExecutionModeDefaults:
    def test_default_execution_mode_is_real_analysis(self):
        """--execution-mode defaults to real_analysis."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--execution-mode", choices=["real_analysis", "offline_debug"], default="real_analysis")
        args = parser.parse_args([])
        assert args.execution_mode == "real_analysis"

    def test_real_analysis_defaults_no_skip_akshare(self, tmp_private_data: Path, output_dir: Path):
        """real_analysis mode sets skip_akshare=False (live NAV)."""
        with patch("scripts.fund_agent_personal_run.e2e_main", side_effect=_fake_e2e_return_0) as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--execution-mode", "real_analysis",
                    "--skip-news",
                ])

                # e2e should have been called WITHOUT --skip-akshare
                call_argv = mock_e2e.call_args[0][0]
                assert "--skip-akshare" not in call_argv

    def test_offline_debug_allows_skip_akshare(self, tmp_private_data: Path, output_dir: Path):
        """offline_debug mode sets skip_akshare=True (deterministic)."""
        with patch("scripts.fund_agent_personal_run.e2e_main", side_effect=_fake_e2e_return_0) as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--execution-mode", "offline_debug",
                    "--skip-news",
                ])

                # e2e should have been called WITH --skip-akshare
                call_argv = mock_e2e.call_args[0][0]
                assert "--skip-akshare" in call_argv


class TestRealAnalysisRejectsSkipAkshare:
    def test_real_analysis_rejects_explicit_skip_akshare(self, tmp_private_data: Path, output_dir: Path, capsys):
        """real_analysis + --skip-akshare should fail fast."""
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--execution-mode", "real_analysis",
            "--skip-akshare",
            "--skip-news",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not allowed" in captured.err.lower() or "real_analysis" in captured.err


class TestExecutionModeInManifest:
    def test_manifest_includes_execution_mode(self, tmp_private_data: Path, output_dir: Path):
        """run_manifest.json includes execution_mode field."""
        with patch("scripts.fund_agent_personal_run.e2e_main", side_effect=_fake_e2e_return_0):
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--execution-mode", "real_analysis",
                    "--skip-news",
                ])

                run_dirs = list(output_dir.iterdir())
                assert len(run_dirs) >= 1
                manifest_path = run_dirs[0] / "run_manifest.json"
                assert manifest_path.exists()
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                assert manifest.get("execution_mode") == "real_analysis"
                assert manifest.get("canonical_entrypoint") is True
                assert manifest.get("invoked_script") == "fund_agent_personal_run"

    def test_manifest_offline_debug_mode(self, tmp_private_data: Path, output_dir: Path):
        """run_manifest.json shows offline_debug mode."""
        with patch("scripts.fund_agent_personal_run.e2e_main", side_effect=_fake_e2e_return_0):
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--execution-mode", "offline_debug",
                    "--skip-news",
                ])

                run_dirs = list(output_dir.iterdir())
                assert len(run_dirs) >= 1
                manifest_path = run_dirs[0] / "run_manifest.json"
                assert manifest_path.exists()
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                assert manifest.get("execution_mode") == "offline_debug"
                assert manifest.get("flags", {}).get("skip_akshare") is True


class TestCanonicalProvenance:
    def test_personal_run_sets_canonical_provenance_for_e2e(self, tmp_private_data: Path, output_dir: Path):
        """personal-run passes --invoked-by-personal-run to e2e."""
        with patch("scripts.fund_agent_personal_run.e2e_main", side_effect=_fake_e2e_return_0) as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--execution-mode", "real_analysis",
                    "--skip-news",
                ])

                call_argv = mock_e2e.call_args[0][0]
                assert "--invoked-by-personal-run" in call_argv

    def test_personal_run_sets_canonical_env_var(self, tmp_private_data: Path, output_dir: Path):
        """personal-run passes FUND_AGENT_CANONICAL_PERSONAL_RUN=1 to e2e."""
        with patch("scripts.fund_agent_personal_run.e2e_main", side_effect=_fake_e2e_return_0) as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--execution-mode", "real_analysis",
                    "--skip-news",
                ])

                # Check env_overrides kwarg
                call_kwargs = mock_e2e.call_args[1]
                assert call_kwargs.get("env_overrides", {}).get("FUND_AGENT_CANONICAL_PERSONAL_RUN") == "1"
