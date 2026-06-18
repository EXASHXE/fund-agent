"""No stale round3 runtime references — wrappers/runner must not use stale artifacts."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Files that are runtime paths (not docs/tests with negative guards)
RUNTIME_PATHS = [
    REPO_ROOT / "bin" / "fund-agent-e2e",
    REPO_ROOT / "bin" / "fund-agent-e2e.cmd",
    REPO_ROOT / "scripts" / "fund_agent_e2e.py",
    REPO_ROOT / "src" / "fund_agent" / "cli.py",
    REPO_ROOT / "fund_agent" / "cli.py",
]

# Skill files that are agent-facing instructions
SKILL_FILES = list(REPO_ROOT.glob("skills/*/SKILL.md")) + list(REPO_ROOT.glob(".opencode/skills/*/SKILL.md"))


class TestNoStaleRound3RuntimeRefs:
    """Wrappers, agents, skills, and runner must not reference stale round3 envelope."""

    def test_bash_runner_no_round3(self):
        content = (REPO_ROOT / "bin" / "fund-agent-e2e").read_text(encoding="utf-8")
        assert "round3_" not in content, "Bash runner must not reference round3_"
        assert "fund_analysis_input_envelope" not in content, (
            "Bash runner must not reference fund_analysis_input_envelope"
        )

    def test_python_runner_no_round3(self):
        content = (REPO_ROOT / "scripts" / "fund_agent_e2e.py").read_text(encoding="utf-8")
        assert "round3_" not in content, "Python runner must not reference round3_"
        assert "fund_analysis_input_envelope" not in content, (
            "Python runner must not reference fund_analysis_input_envelope"
        )

    def test_cli_no_round3(self):
        content = (REPO_ROOT / "src" / "fund_agent" / "cli.py").read_text(encoding="utf-8")
        assert "round3_" not in content, "CLI must not reference round3_"
        assert "fund_analysis_input_envelope" not in content, (
            "CLI must not reference fund_analysis_input_envelope"
        )

    def test_cmd_wrapper_no_round3(self):
        content = (REPO_ROOT / "bin" / "fund-agent-e2e.cmd").read_text(encoding="utf-8")
        assert "round3_" not in content, ".cmd wrapper must not reference round3_"

    @pytest.mark.parametrize("skill_file", SKILL_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
    def test_skill_files_no_round3_runtime(self, skill_file: Path):
        """Skill files must not instruct use of stale round3 envelope as runtime path."""
        content = skill_file.read_text(encoding="utf-8")
        # Allow negative guards (e.g., "do not use round3")
        lines_with_round3 = [
            line for line in content.splitlines()
            if "round3_" in line.lower() or "fund_analysis_input_envelope" in line.lower()
        ]
        for line in lines_with_round3:
            # If it's a negative guard, that's OK
            lower = line.lower()
            is_negative = any(w in lower for w in ["do not", "don't", "must not", "never", "avoid", "deprecated", "stale", "no longer"])
            assert is_negative, (
                f"{skill_file.relative_to(REPO_ROOT)} references round3/fund_analysis_input_envelope "
                f"without a negative guard: {line.strip()}"
            )
