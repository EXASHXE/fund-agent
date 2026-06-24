"""Pipeline wiring tests — verify runner uses actual snapshot filenames and KG inputs."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASH_RUNNER = REPO_ROOT / "bin" / "fund-agent-e2e"
PY_RUNNER = REPO_ROOT / "scripts" / "fund_agent_e2e.py"


class TestBashDelegation:
    """The POSIX launcher must not duplicate Python orchestration logic."""

    def test_bash_runner_delegates_to_python_orchestrator(self):
        content = BASH_RUNNER.read_text(encoding="utf-8")
        assert "scripts/fund_agent_e2e.py" in content
        assert '"$@"' in content

    def test_bash_runner_has_no_pipeline_business_logic(self):
        content = BASH_RUNNER.read_text(encoding="utf-8")
        assert "build_transaction_ledger.py" not in content
        assert "build_fund_data_snapshot.py" not in content
        assert "analyze-portfolio" not in content


class TestSnapshotFilenames:
    """Verify the canonical Python runner uses actual snapshot filenames."""

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

    def test_python_runner_regen_planned_with_nav(self):
        content = PY_RUNNER.read_text(encoding="utf-8")
        assert "--nav-snapshot" in content, (
            "Python runner must pass --nav-snapshot when regenerating planned transactions"
        )
        # Should have "Regenerate" or "NAV-aware" step
        assert "Regenerate" in content or "NAV" in content, (
            "Python runner must have a NAV-aware planned transaction regeneration step"
        )
