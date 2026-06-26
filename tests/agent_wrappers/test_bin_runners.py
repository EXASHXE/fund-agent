"""bin/ runner tests."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BIN_DIR = REPO_ROOT / "bin"


class TestBinRunners:
    def test_e2e_help_exits_zero(self):
        result = subprocess.run(
            ["bash", str(BIN_DIR / "fund-agent-e2e"), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"e2e --help failed: {result.stderr}"

    def test_e2e_dry_run(self):
        result = subprocess.run(
            ["bash", str(BIN_DIR / "fund-agent-e2e"), "--dry-run",
             "--allow-noncanonical-test-run"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"e2e --dry-run failed: {result.stderr}"
        assert "dry-run" in result.stdout.lower() or "would run" in result.stdout.lower()

    def test_e2e_script_syntax_valid(self):
        content = (BIN_DIR / "fund-agent-e2e").read_text(encoding="utf-8")
        assert "set -euo pipefail" in content
        assert "scripts/fund_agent_e2e.py" in content
        assert "build_transaction_ledger.py" not in content

    def test_privacy_check_script_syntax_valid(self):
        content = (BIN_DIR / "fund-agent-privacy-check").read_text(encoding="utf-8")
        assert "privacy_audit" in content

    def test_privacy_check_runs(self):
        result = subprocess.run(
            ["bash", str(BIN_DIR / "fund-agent-privacy-check")],
            capture_output=True, text=True, timeout=60,
        )
        # Should pass or fail gracefully, not crash
        assert result.returncode in (0, 1), f"privacy-check crashed: {result.stderr}"

    def test_privacy_audit_py_syntax(self):
        path = REPO_ROOT / "scripts" / "privacy_audit.py"
        ast.parse(path.read_text(encoding="utf-8"))

    def test_windows_cmd_wrappers_exist(self):
        assert (BIN_DIR / "fund-agent-e2e.cmd").exists()
        assert (BIN_DIR / "fund-agent-privacy-check.cmd").exists()
