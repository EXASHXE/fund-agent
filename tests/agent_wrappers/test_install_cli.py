"""Installer CLI tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SCRIPT = REPO_ROOT / "install" / "fund-agent-agent-install.py"
UNINSTALL_SCRIPT = REPO_ROOT / "install" / "fund-agent-agent-uninstall.py"


class TestInstallCLI:
    @pytest.mark.parametrize("target", ["claude-code", "codex", "opencode", "all"])
    def test_install_dry_run(self, target):
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--target", target, "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"install --dry-run --target {target} failed: {result.stderr}"
        assert "dry-run" in result.stdout.lower()

    @pytest.mark.parametrize("target", ["claude-code", "codex", "opencode", "all"])
    def test_uninstall_dry_run(self, target):
        result = subprocess.run(
            [sys.executable, str(UNINSTALL_SCRIPT), "--target", target, "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"uninstall --dry-run --target {target} failed: {result.stderr}"

    def test_install_symlink_mode(self):
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--target", "all", "--mode", "symlink", "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "symlink" in result.stdout.lower()

    def test_install_copy_mode(self):
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--target", "all", "--mode", "copy", "--dry-run"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
