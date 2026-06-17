"""Installer temp HOME integration tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SCRIPT = REPO_ROOT / "install" / "fund-agent-agent-install.py"
UNINSTALL_SCRIPT = REPO_ROOT / "install" / "fund-agent-agent-uninstall.py"


class TestInstallerTempHome:
    @pytest.mark.parametrize("target", ["claude-code", "codex", "opencode", "all"])
    def test_dry_run_all_targets(self, target):
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--target", target, "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"dry-run failed for {target}: {result.stderr}"

    def test_install_to_temp_codex(self, tmp_path):
        """Install Codex skills to a temp directory via --mode copy."""
        codex_dir = tmp_path / ".agents" / "skills"
        codex_dir.mkdir(parents=True)
        # Simulate by running installer with overridden HOME
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--target", "codex", "--mode", "copy", "--force"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT), env=env,
        )
        assert result.returncode == 0, f"install codex failed: {result.stderr}"

    def test_uninstall_dry_run_no_real_changes(self):
        result = subprocess.run(
            [sys.executable, str(UNINSTALL_SCRIPT), "--target", "all", "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0

    def test_installer_does_not_copy_private_data(self):
        """Installer output must not reference private_data/ or local_reports/."""
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--target", "all", "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert "private_data" not in result.stdout, "Installer references private_data/"
        assert "local_reports" not in result.stdout, "Installer references local_reports/"
        assert "eval_workspace" not in result.stdout, "Installer references eval_workspace/"

    def test_uninstall_refuses_unrelated_files(self, tmp_path):
        """Create a non-fund-agent file and verify uninstall skips it."""
        codex_dir = tmp_path / ".agents" / "skills"
        unrelated = codex_dir / "other-skill"
        unrelated.mkdir(parents=True)
        (unrelated / "SKILL.md").write_text("name: other", encoding="utf-8")

        env = os.environ.copy()
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)
        result = subprocess.run(
            [sys.executable, str(UNINSTALL_SCRIPT), "--target", "codex"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT), env=env,
        )
        assert result.returncode == 0
        assert unrelated.exists(), "Uninstall removed unrelated file"
