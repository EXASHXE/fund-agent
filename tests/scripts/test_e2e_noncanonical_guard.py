"""Tests for e2e non-canonical personal analysis guard.

M7.7: Validates that scripts/fund_agent_e2e.py blocks direct invocation
for personal/private-data analysis without canonical provenance.

All test data is synthetic — no real fund names, amounts, or transaction IDs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from scripts.fund_agent_e2e import main as e2e_main


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tmp_private_data(tmp_path: Path) -> Path:
    """Create a minimal private_data directory with synthetic data."""
    pd = tmp_path / "private_data"
    pd.mkdir()
    # Create a minimal Alipay CSV (synthetic)
    (pd / "alipay_record_synthetic.csv").write_text(
        "synthetic,test,data\n", encoding="utf-8"
    )
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
    od = tmp_path / "output"
    od.mkdir()
    return od


# ── Test: direct e2e with private data fails without provenance ───────


class TestDirectE2EPrivateDataGuard:
    def test_direct_e2e_private_data_fails_without_provenance(
        self, tmp_private_data: Path, output_dir: Path, capsys
    ):
        """Direct e2e with --private-data-dir private_data fails fast."""
        rc = e2e_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--transaction-source", "auto",
            "--skip-akshare",
            "--skip-news",
            "--dry-run",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "non_canonical_personal_analysis_entrypoint" in captured.err

    def test_direct_e2e_private_data_error_message_points_to_personal_run(
        self, tmp_private_data: Path, output_dir: Path, capsys
    ):
        """Error message suggests using bin/fund-agent-personal-run."""
        rc = e2e_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--transaction-source", "auto",
            "--skip-akshare",
            "--skip-news",
            "--dry-run",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "fund-agent-personal-run" in captured.err

    def test_direct_e2e_with_canonical_env_succeeds(
        self, tmp_private_data: Path, output_dir: Path
    ):
        """With FUND_AGENT_CANONICAL_PERSONAL_RUN=1, e2e proceeds."""
        # Set the canonical env var
        old = os.environ.get("FUND_AGENT_CANONICAL_PERSONAL_RUN")
        try:
            os.environ["FUND_AGENT_CANONICAL_PERSONAL_RUN"] = "1"
            rc = e2e_main([
                "--private-data-dir", str(tmp_private_data),
                "--output-dir", str(output_dir),
                "--output-report", str(output_dir / "report.md"),
                "--transaction-source", "auto",
                "--skip-akshare",
                "--skip-news",
                "--dry-run",
            ])
            # Should not be blocked by the guard
            assert rc == 0
        finally:
            if old is None:
                os.environ.pop("FUND_AGENT_CANONICAL_PERSONAL_RUN", None)
            else:
                os.environ["FUND_AGENT_CANONICAL_PERSONAL_RUN"] = old

    def test_direct_e2e_with_invoked_by_personal_run_arg_succeeds(
        self, tmp_private_data: Path, output_dir: Path
    ):
        """With --invoked-by-personal-run, e2e proceeds."""
        rc = e2e_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--output-report", str(output_dir / "report.md"),
            "--transaction-source", "auto",
            "--skip-akshare",
            "--skip-news",
            "--dry-run",
            "--invoked-by-personal-run",
        ])
        # Should not be blocked by the guard
        assert rc == 0


class TestNoncanonicalTestRunBypass:
    def test_direct_e2e_synthetic_tests_can_use_allow_noncanonical_test_run(
        self, tmp_private_data: Path, output_dir: Path
    ):
        """--allow-noncanonical-test-run bypasses the guard for tests."""
        rc = e2e_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--output-report", str(output_dir / "report.md"),
            "--transaction-source", "auto",
            "--skip-akshare",
            "--skip-news",
            "--dry-run",
            "--allow-noncanonical-test-run",
        ])
        # Should not be blocked
        assert rc == 0


class TestLegacyFlatReportPathForbidden:
    def test_e2e_private_data_flat_report_path_forbidden(
        self, tmp_private_data: Path, tmp_path: Path, capsys
    ):
        """local_reports/real_portfolio_report.md is forbidden for personal data."""
        # Create local_reports dir
        local_reports = tmp_path / "local_reports"
        local_reports.mkdir()

        rc = e2e_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(tmp_path / "output"),
            "--output-report", str(local_reports / "real_portfolio_report.md"),
            "--transaction-source", "auto",
            "--skip-akshare",
            "--skip-news",
            "--dry-run",
            "--allow-noncanonical-test-run",
        ])
        # Should fail because of the legacy flat path
        assert rc == 1
        captured = capsys.readouterr()
        assert "forbidden" in captured.err.lower() or "real_portfolio_report" in captured.err

    def test_e2e_private_data_without_output_report_fails(
        self, tmp_private_data: Path, output_dir: Path, capsys
    ):
        """No --output-report with private data fails fast."""
        rc = e2e_main([
            "--private-data-dir", str(tmp_private_data),
            "--output-dir", str(output_dir),
            "--transaction-source", "auto",
            "--skip-akshare",
            "--skip-news",
            "--dry-run",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        # Should be blocked by either the non-canonical guard or the missing output-report check
        assert "non_canonical" in captured.err or "output-report" in captured.err.lower() or "required" in captured.err.lower()


class TestPersonalRunIdDetection:
    def test_personal_run_id_triggers_guard(self, tmp_path: Path, capsys):
        """run_id starting with 'personal-' is a personal analysis signal."""
        # Use a non-private_data dir but with personal- run_id
        pd = tmp_path / "some_data"
        pd.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        rc = e2e_main([
            "--private-data-dir", str(pd),
            "--output-dir", str(output),
            "--run-id", "personal-test",
            "--transaction-source", "alipay",
            "--skip-akshare",
            "--skip-news",
            "--dry-run",
        ])
        # Should be blocked (2+ signals: personal- run_id + alipay txn source)
        assert rc == 1
        captured = capsys.readouterr()
        assert "non_canonical_personal_analysis_entrypoint" in captured.err
