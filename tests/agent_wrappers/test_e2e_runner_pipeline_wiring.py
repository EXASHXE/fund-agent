"""Pipeline wiring tests — verify runner uses actual snapshot filenames and KG inputs."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASH_RUNNER = REPO_ROOT / "bin" / "fund-agent-e2e"
PY_RUNNER = REPO_ROOT / "scripts" / "fund_agent_e2e.py"


class TestSnapshotFilenames:
    """Verify runner references actual snapshot output filenames."""

    def test_bash_runner_uses_nav_snapshot_private(self):
        """Bash runner must look for nav_snapshot.private.json, not nav_snapshot.json."""
        content = BASH_RUNNER.read_text(encoding="utf-8")
        assert "nav_snapshot.private.json" in content, (
            "Bash runner must reference nav_snapshot.private.json"
        )
        # Should NOT reference the old incorrect name
        assert '"$FUND_SNAPSHOT_DIR/nav_snapshot.json"' not in content, (
            "Bash runner should not reference old nav_snapshot.json path"
        )

    def test_bash_runner_uses_fee_schedule_snapshot_private(self):
        """Bash runner must look for fee_schedule_snapshot.private.json, not fee_snapshot.json."""
        content = BASH_RUNNER.read_text(encoding="utf-8")
        assert "fee_schedule_snapshot.private.json" in content, (
            "Bash runner must reference fee_schedule_snapshot.private.json"
        )
        assert '"$FUND_SNAPSHOT_DIR/fee_snapshot.json"' not in content, (
            "Bash runner should not reference old fee_snapshot.json path"
        )

    def test_bash_runner_uses_fund_profile_snapshot_private(self):
        """Bash runner must reference fund_profile_snapshot.private.json."""
        content = BASH_RUNNER.read_text(encoding="utf-8")
        assert "fund_profile_snapshot.private.json" in content, (
            "Bash runner must reference fund_profile_snapshot.private.json"
        )

    def test_python_runner_uses_nav_snapshot_private(self):
        """Python runner must look for nav_snapshot.private.json."""
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "nav_snapshot.private.json" in content, (
            "Python runner must reference nav_snapshot.private.json"
        )

    def test_python_runner_uses_fee_schedule_snapshot_private(self):
        """Python runner must look for fee_schedule_snapshot.private.json."""
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "fee_schedule_snapshot.private.json" in content, (
            "Python runner must reference fee_schedule_snapshot.private.json"
        )

    def test_python_runner_uses_fund_profile_snapshot_private(self):
        """Python runner must reference fund_profile_snapshot.private.json."""
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "fund_profile_snapshot.private.json" in content, (
            "Python runner must reference fund_profile_snapshot.private.json"
        )


class TestKGBuilderInputs:
    """Verify runner passes fund_profile_snapshot and confirmed_portfolio to KG builder."""

    def test_bash_runner_passes_fund_profile_snapshot_to_kg(self):
        content = BASH_RUNNER.read_text(encoding="utf-8")
        assert "--fund-profile-snapshot" in content, (
            "Bash runner must pass --fund-profile-snapshot to KG builder"
        )

    def test_bash_runner_passes_confirmed_portfolio_to_kg(self):
        content = BASH_RUNNER.read_text(encoding="utf-8")
        assert "--confirmed-portfolio" in content, (
            "Bash runner must pass --confirmed-portfolio to KG builder"
        )

    def test_python_runner_passes_fund_profile_snapshot_to_kg(self):
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "--fund-profile-snapshot" in content, (
            "Python runner must pass --fund-profile-snapshot to KG builder"
        )

    def test_python_runner_passes_confirmed_portfolio_to_kg(self):
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "--confirmed-portfolio" in content, (
            "Python runner must pass --confirmed-portfolio to KG builder"
        )


class TestNavAwarePlannedTransactions:
    """Verify runner regenerates planned transactions with NAV for rule_confirmed."""

    def test_bash_runner_regen_planned_with_nav(self):
        content = BASH_RUNNER.read_text(encoding="utf-8")
        # Should have generate_planned_transactions.py with --nav-snapshot
        # (command may span multiple lines, so check both appear in the file)
        assert "generate_planned_transactions.py" in content, (
            "Bash runner must call generate_planned_transactions.py"
        )
        assert "--nav-snapshot" in content, (
            "Bash runner must pass --nav-snapshot to generate_planned_transactions.py"
        )
        # Must have a "Regenerate" step indicating two-phase generation
        assert "Regenerate" in content or "regenerate" in content.lower(), (
            "Bash runner must have a regenerate step for NAV-aware planned transactions"
        )

    def test_python_runner_regen_planned_with_nav(self):
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "--nav-snapshot" in content, (
            "Python runner must pass --nav-snapshot when regenerating planned transactions"
        )
        # Should have "Regenerate" or "NAV-aware" step
        assert "Regenerate" in content or "NAV" in content, (
            "Python runner must have a NAV-aware planned transaction regeneration step"
        )
