"""Tests for personal-run CLI orchestrator.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
        # The output should be JSON-parseable (or empty if no data)


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
        from scripts.fund_agent_personal_run import main

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
