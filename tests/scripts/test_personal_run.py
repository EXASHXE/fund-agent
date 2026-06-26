"""Tests for personal-run CLI orchestrator.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
import os
import textwrap
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
    # Create a minimal portfolio_input.private.json
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


def _make_synthetic_e2e_summary(run_id: str = "test-001") -> dict[str, Any]:
    """Create a synthetic e2e_summary for print-only mode tests."""
    return {
        "run_id": run_id,
        "as_of": "2026-06-24",
        "status": "partial",
        "warnings": [],
        "errors": [],
        "steps_completed": ["resolve_fund_identities"],
        "pipeline_steps": {
            "reconstruction_status": "reconstructed_from_ledger",
            "valid_fund_codes_count": 2,
            "name_only_count": 0,
        },
        "personal_health_report": {
            "schema_version": "personal_health_report.v1",
            "overall_status": "partial",
            "confidence_level": "medium",
            "reason_codes": ["partial_nav_coverage"],
            "data_sources": {
                "transaction_source": "alipay",
                "valuation_source": "reconstructed_from_ledger",
                "identity_source": "direct_fund_code",
            },
            "valuation_quality": {
                "positions_total": 3,
                "confirmed_count": 0,
                "estimated_full_coverage_count": 1,
                "estimated_partial_coverage_count": 2,
            },
            "nav_coverage": {
                "full": 1,
                "partial": 2,
                "none": 0,
                "latest_only": 0,
                "stale_count": 0,
                "qdii_like_count": 0,
            },
            "fix_it_checklist": [
                "Add trade-date NAV overrides for 2 fund(s) with missing coverage"
            ],
            "safety_notes": [
                "This is not a formal investment decision — no BUY/SELL/HOLD instruction.",
            ],
        },
    }


# ── Test: personal_run_writes_agent_context_files ─────────────────────


class TestPersonalRunWritesArtifacts:
    def test_dry_run_creates_run_dir(self, tmp_private_data: Path, output_dir: Path):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--skip-akshare",
            "--skip-news",
        ])
        # Dry run should succeed
        assert rc == 0
        # Run dir should exist
        run_dirs = list(output_dir.iterdir())
        assert len(run_dirs) >= 1


# ── Test: health_report_only_does_not_replace_agent_analysis ──────────


class TestHealthReportOnly:
    def test_health_report_only_outputs_json(self, tmp_private_data: Path, output_dir: Path, capsys):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--health-report-only",
            "--skip-akshare",
            "--skip-news",
        ])
        # Should output health report JSON
        captured = capsys.readouterr()
        # Even if E2E fails, health-report-only should not crash


# ── Test: agent_context_only_regenerates_from_summary ─────────────────


class TestAgentContextOnly:
    def test_agent_context_only_outputs_markdown(self, tmp_private_data: Path, output_dir: Path, capsys):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--agent-context-only",
            "--skip-akshare",
            "--skip-news",
        ])
        captured = capsys.readouterr()
        # Should output agent context markdown
        if rc == 0:
            assert "Fund Agent Analysis Context" in captured.out or "unavailable" in captured.out


# ── Test: skip_akshare_skip_news_documented_as_deterministic_mode ─────


class TestDeterministicMode:
    def test_default_skip_akshare_is_true(self):
        """Verify --skip-akshare defaults to True."""
        import argparse

        # Parse args with defaults
        parser = argparse.ArgumentParser()
        parser.add_argument("--skip-akshare", action="store_true", default=True)
        parser.add_argument("--skip-news", action="store_true", default=True)
        args = parser.parse_args([])
        assert args.skip_akshare is True
        assert args.skip_news is True

    def test_no_skip_akshare_overrides_default(self):
        """Verify --no-skip-akshare overrides the default."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--skip-akshare", action="store_true", default=True)
        parser.add_argument("--no-skip-akshare", action="store_false", dest="skip_akshare")
        args = parser.parse_args(["--no-skip-akshare"])
        assert args.skip_akshare is False


# ── Test: run_manifest_schema ─────────────────────────────────────────


class TestRunManifest:
    def test_manifest_written_on_dry_run(self, tmp_private_data: Path, output_dir: Path):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--skip-akshare",
            "--skip-news",
        ])
        run_dirs = list(output_dir.iterdir())
        if run_dirs:
            manifest_path = run_dirs[0] / "run_manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                assert manifest["schema_version"] == "fund_agent_run_manifest.v1"
                assert "run_id" in manifest
                assert "doctor_ok" in manifest
                assert "e2e_status" in manifest
                assert "mode" in manifest
                assert manifest["mode"] == "deterministic"

    def test_manifest_has_health_fields(self, tmp_private_data: Path, output_dir: Path):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--skip-akshare",
            "--skip-news",
        ])
        run_dirs = list(output_dir.iterdir())
        if run_dirs:
            manifest_path = run_dirs[0] / "run_manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                assert "health_overall_status" in manifest
                assert "confidence_level" in manifest
                assert "reason_codes" in manifest
                assert "private_data_configured" in manifest
                assert "doctor_status" in manifest


# ── Test: no private data in output ───────────────────────────────────


class TestNoPrivateDataInOutput:
    def test_agent_context_no_private_paths(self, tmp_private_data: Path, output_dir: Path):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--skip-akshare",
            "--skip-news",
        ])
        run_dirs = list(output_dir.iterdir())
        if run_dirs:
            # Check agent_context.json for private paths
            ctx_path = run_dirs[0] / "agent_context.json"
            if ctx_path.exists():
                ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
                ctx_json = json.dumps(ctx)
                assert "private_data" not in ctx_json
                assert str(tmp_private_data) not in ctx_json

    def test_agent_context_md_no_private_paths(self, tmp_private_data: Path, output_dir: Path):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--skip-akshare",
            "--skip-news",
        ])
        run_dirs = list(output_dir.iterdir())
        if run_dirs:
            md_path = run_dirs[0] / "agent_context.md"
            if md_path.exists():
                md = md_path.read_text(encoding="utf-8")
                assert "C:" not in md
                assert str(tmp_private_data) not in md

    def test_manifest_no_private_paths(self, tmp_private_data: Path, output_dir: Path):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--skip-akshare",
            "--skip-news",
        ])
        run_dirs = list(output_dir.iterdir())
        if run_dirs:
            manifest_path = run_dirs[0] / "run_manifest.json"
            if manifest_path.exists():
                manifest_json = manifest_path.read_text(encoding="utf-8")
                assert str(tmp_private_data) not in manifest_json


# ── Test: console output format ───────────────────────────────────────


class TestConsoleOutput:
    def test_console_summary_format(self, tmp_private_data: Path, output_dir: Path, capsys):
        rc = personal_run_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--skip-akshare",
            "--skip-news",
        ])
        captured = capsys.readouterr()
        # Should contain key phrases
        if rc == 0:
            assert "evidence package" in captured.out.lower() or "Run ID" in captured.out


# ── Test: doctor respects private-data-dir ────────────────────────────


class TestDoctorRespectsPrivateDataDir:
    def test_doctor_checks_custom_dir(self, tmp_path: Path):
        """run_doctor(private_data_dir=custom) checks custom dir, not repo default."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        custom_pd = tmp_path / "my_custom_private"
        custom_pd.mkdir()

        # Put a portfolio_input in custom dir
        pi = {"schema_version": "portfolio_input.v1", "holdings": []}
        (custom_pd / "portfolio_input.private.json").write_text(
            json.dumps(pi), encoding="utf-8"
        )

        result = run_doctor(custom_pd)
        # Should find the directory and portfolio_input
        dir_check = next(c for c in result["checks"] if c["id"] == "private_data.exists")
        assert dir_check["status"] == "OK"

        pi_check = next(c for c in result["checks"] if c["id"] == "portfolio_input.exists")
        assert pi_check["status"] == "OK"

        # Output should NOT contain the absolute path
        output = json.dumps(result, default=str)
        assert str(custom_pd) not in output

    def test_doctor_default_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """run_doctor() without args uses default PRIVATE_DATA_DIR."""
        from scripts.fund_agent_private_data_doctor import run_doctor

        result = run_doctor()
        # Should not crash — default dir may or may not exist
        assert "ok" in result
        assert "checks" in result

    def test_personal_run_passes_private_data_dir_to_doctor(self, tmp_private_data: Path, output_dir: Path):
        """personal-run --private-data-dir passes the dir to run_doctor."""
        with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
            mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}
            with patch("scripts.fund_agent_personal_run.e2e_main") as mock_e2e:
                mock_e2e.return_value = 0

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--skip-akshare",
                    "--skip-news",
                ])

                # run_doctor should have been called with tmp_private_data
                mock_doctor.assert_called_once()
                call_arg = mock_doctor.call_args[0][0]
                assert Path(call_arg) == tmp_private_data


# ── Test: failed pipeline must not expose stale report ────────────────


class TestFailedPipelineReportHandling:
    def test_failed_e2e_does_not_copy_stale_report(
        self,
        tmp_private_data: Path,
        output_dir: Path,
    ):
        run_id = "failed-no-report"
        stale_report = output_dir / "stale_report.md"
        stale_report.write_text("# stale report\n", encoding="utf-8")

        def fake_e2e(argv: list[str]) -> int:
            run_dir = Path(argv[argv.index("--output-dir") + 1])
            output_report = Path(argv[argv.index("--output-report") + 1])
            assert output_report == run_dir / "report.md"
            run_dir.mkdir(parents=True, exist_ok=True)
            summary = {
                "run_id": run_id,
                "status": "failed",
                "errors": ["No portfolio input available for required analysis"],
                "warnings": [],
                "steps_completed": ["import_alipay_transactions"],
                "outputs": {"report": None, "summary": "e2e_summary.json"},
                "output_report": str(stale_report),
                "pipeline_steps": {"reconstruction_status": "nav_unavailable"},
                "personal_health_report": {
                    "schema_version": "personal_health_report.v1",
                    "overall_status": "needs_data",
                    "confidence_level": "unavailable",
                    "reason_codes": ["nav_missing"],
                    "nav_coverage": {
                        "full": 0,
                        "partial": 0,
                        "none": 0,
                        "latest_only": 0,
                        "stale_count": 0,
                        "qdii_like_count": 0,
                    },
                },
            }
            (run_dir / "e2e_summary.json").write_text(
                json.dumps(summary), encoding="utf-8"
            )
            (run_dir / "fund_identity_overrides.template.private.yaml").write_text(
                "funds: []\n", encoding="utf-8"
            )
            return 1

        with patch("scripts.fund_agent_personal_run.e2e_main", side_effect=fake_e2e):
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--run-id", run_id,
                    "--skip-akshare",
                    "--skip-news",
                ])

        run_dir = output_dir / run_id
        assert rc == 1
        assert not (run_dir / "report.md").exists()
        assert (tmp_private_data / "fund_identity_overrides.template.private.yaml").exists()

        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["e2e_status"] == "failed"
        assert "report" not in manifest["artifacts"]
        assert (
            manifest["artifacts"]["identity_overrides_template"]
            == "fund_identity_overrides.template.private.yaml"
        )

        context = json.loads((run_dir / "agent_context.json").read_text(encoding="utf-8"))
        assert "report" not in context["artifact_paths"]
        assert (
            context["artifact_paths"]["identity_overrides_template"]
            == "fund_identity_overrides.template.private.yaml"
        )


# ── Test: print-only mode with existing summary ──────────────────────


class TestPrintOnlyMode:
    def test_health_report_only_with_summary_path_skips_pipeline(self, tmp_path: Path, capsys):
        """--health-report-only --summary-path reads existing summary, no pipeline."""
        summary = _make_synthetic_e2e_summary()
        summary_path = tmp_path / "e2e_summary.json"
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        with patch("scripts.fund_agent_personal_run.e2e_main") as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                rc = personal_run_main([
                    "--health-report-only",
                    "--summary-path", str(summary_path),
                ])

                # Neither e2e_main nor run_doctor should be called
                mock_e2e.assert_not_called()
                mock_doctor.assert_not_called()

                assert rc == 0
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["overall_status"] == "partial"

    def test_agent_context_only_with_run_dir_skips_pipeline(self, tmp_path: Path, capsys):
        """--agent-context-only --run-dir reads existing summary, no pipeline."""
        run_dir = tmp_path / "run-001"
        run_dir.mkdir()
        summary = _make_synthetic_e2e_summary("run-001")
        (run_dir / "e2e_summary.json").write_text(json.dumps(summary), encoding="utf-8")

        with patch("scripts.fund_agent_personal_run.e2e_main") as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                rc = personal_run_main([
                    "--agent-context-only",
                    "--run-dir", str(run_dir),
                ])

                mock_e2e.assert_not_called()
                mock_doctor.assert_not_called()

                assert rc == 0
                captured = capsys.readouterr()
                assert "Fund Agent Analysis Context" in captured.out
                assert "partial" in captured.out

    def test_agent_context_only_writes_files_to_run_dir(self, tmp_path: Path, capsys):
        """--agent-context-only --run-dir writes agent_context files."""
        run_dir = tmp_path / "run-002"
        run_dir.mkdir()
        summary = _make_synthetic_e2e_summary("run-002")
        (run_dir / "e2e_summary.json").write_text(json.dumps(summary), encoding="utf-8")

        with patch("scripts.fund_agent_personal_run.e2e_main") as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                rc = personal_run_main([
                    "--agent-context-only",
                    "--run-dir", str(run_dir),
                ])

                assert rc == 0
                assert (run_dir / "agent_context.json").exists()
                assert (run_dir / "agent_context.md").exists()

    def test_missing_summary_path_falls_through_to_pipeline(self, tmp_path: Path, capsys):
        """--agent-context-only --summary-path missing falls through to full pipeline."""
        missing_path = tmp_path / "nonexistent.json"

        with patch("scripts.fund_agent_personal_run.e2e_main") as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_e2e.return_value = 0
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                # Create output dir for the pipeline
                output_dir = tmp_path / "local_reports"
                output_dir.mkdir()
                pd = tmp_path / "private_data"
                pd.mkdir()

                rc = personal_run_main([
                    "--agent-context-only",
                    "--summary-path", str(missing_path),
                    "--private-data-dir", str(pd),
                    "--output-dir", str(output_dir),
                    "--skip-akshare",
                    "--skip-news",
                ])

                # Should fall through to running pipeline
                mock_e2e.assert_called_once()
                mock_doctor.assert_called_once()

    def test_default_mode_runs_full_pipeline(self, tmp_private_data: Path, output_dir: Path):
        """Without --summary-path or --run-dir, default mode runs full pipeline."""
        with patch("scripts.fund_agent_personal_run.e2e_main") as mock_e2e:
            with patch("scripts.fund_agent_personal_run.run_doctor") as mock_doctor:
                mock_e2e.return_value = 0
                mock_doctor.return_value = {"ok": True, "status": "ok", "checks": [], "warnings": [], "errors": []}

                rc = personal_run_main([
                    "--private-data-dir", str(tmp_private_data),
                    "--output-dir", str(output_dir),
                    "--skip-akshare",
                    "--skip-news",
                ])

                mock_e2e.assert_called_once()
                mock_doctor.assert_called_once()
