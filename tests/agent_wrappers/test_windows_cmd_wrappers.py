"""Windows .cmd wrapper tests — verify .cmd wrappers delegate to real E2E runner."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CMD_E2E = REPO_ROOT / "bin" / "fund-agent-e2e.cmd"
CMD_PRIVACY = REPO_ROOT / "bin" / "fund-agent-privacy-check.cmd"
PY_RUNNER = REPO_ROOT / "scripts" / "fund_agent_e2e.py"


class TestWindowsCmdWrappers:
    """Verify .cmd wrappers point to real E2E runner."""

    def test_e2e_cmd_exists(self):
        assert CMD_E2E.exists(), "bin/fund-agent-e2e.cmd must exist"

    def test_e2e_cmd_calls_python_orchestrator(self):
        """E2E .cmd must call the shared Python orchestrator, not analyze-portfolio directly."""
        content = CMD_E2E.read_text(encoding="utf-8")
        # Must NOT directly call analyze-portfolio with wrong args
        assert "fund_agent_e2e.py" in content, (
            ".cmd wrapper must call scripts/fund_agent_e2e.py"
        )
        # Must NOT have the old pattern of directly calling analyze-portfolio
        assert "analyze-portfolio %*" not in content, (
            ".cmd wrapper must not directly forward all args to analyze-portfolio"
        )

    def test_e2e_cmd_forwards_args(self):
        """E2E .cmd must forward all arguments to the Python orchestrator."""
        content = CMD_E2E.read_text(encoding="utf-8")
        assert "%*" in content, ".cmd wrapper must forward all args with %*"

    def test_e2e_cmd_checks_python(self):
        """E2E .cmd must check that python is available."""
        content = CMD_E2E.read_text(encoding="utf-8")
        assert "python" in content.lower(), ".cmd wrapper must reference python"

    def test_privacy_cmd_exists(self):
        assert CMD_PRIVACY.exists(), "bin/fund-agent-privacy-check.cmd must exist"

    def test_python_orchestrator_exists(self):
        """The shared Python orchestrator must exist."""
        assert PY_RUNNER.exists(), "scripts/fund_agent_e2e.py must exist"

    def test_python_orchestrator_has_all_args(self):
        """Python orchestrator must support all required CLI args."""
        content = PY_RUNNER.read_text(encoding="utf-8")
        required_args = [
            "--as-of",
            "--skip-news",
            "--skip-akshare",
            "--dry-run",
            "--output-report",
            "--run-id",
            "--private-data-dir",
            "--output-dir",
        ]
        for arg in required_args:
            assert arg in content, f"Python orchestrator must support {arg}"

    def test_python_orchestrator_uses_correct_snapshot_names(self):
        """Python orchestrator must use actual snapshot filenames."""
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "nav_snapshot.private.json" in content
        assert "fee_schedule_snapshot.private.json" in content
        assert "fund_profile_snapshot.private.json" in content
