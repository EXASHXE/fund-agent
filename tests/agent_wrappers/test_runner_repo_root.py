"""Shared runner repo root detection and dry-run tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BIN_E2E = REPO_ROOT / "bin" / "fund-agent-e2e"
BIN_PRIV = REPO_ROOT / "bin" / "fund-agent-privacy-check"


class TestRunnerRepoRoot:
    def test_e2e_dry_run_from_repo_root(self):
        result = subprocess.run(
            ["bash", str(BIN_E2E), "--dry-run", "--as-of", "2026-06-17"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"e2e dry-run failed: {result.stderr}"
        assert "dry-run" in result.stdout.lower() or "would run" in result.stdout.lower()

    def test_e2e_dry_run_from_subdirectory(self):
        sub = REPO_ROOT / "bin"
        result = subprocess.run(
            ["bash", str(BIN_E2E), "--dry-run", "--as-of", "2026-06-17"],
            capture_output=True, text=True, timeout=30, cwd=str(sub),
        )
        assert result.returncode == 0, f"e2e dry-run from subdir failed: {result.stderr}"

    def test_e2e_dry_run_no_private_data_printed(self):
        result = subprocess.run(
            ["bash", str(BIN_E2E), "--dry-run", "--as-of", "2026-06-17"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        # Should not print file contents — paths are OK
        assert "api_key=" not in result.stdout.lower()
        assert "token=" not in result.stdout.lower() or "redacted" in result.stdout.lower()

    def test_privacy_check_runs(self):
        result = subprocess.run(
            ["bash", str(BIN_PRIV)],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        assert result.returncode in (0, 1), f"privacy-check crashed: {result.stderr}"

    def test_e2e_help_works(self):
        result = subprocess.run(
            ["bash", str(BIN_E2E), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "--as-of" in result.stdout
        assert "--dry-run" in result.stdout

    def test_e2e_reports_output_paths(self):
        result = subprocess.run(
            ["bash", str(BIN_E2E), "--dry-run", "--as-of", "2026-06-17"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert "report" in result.stdout.lower() or "summary" in result.stdout.lower()
