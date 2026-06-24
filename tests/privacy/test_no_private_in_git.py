"""No private files tracked by git."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.parametrize("path_prefix", [
    "private_data/",
    "local_data/",
    "local_reports/",
    "eval_workspace/",
])
def test_private_dir_not_tracked(path_prefix):
    result = subprocess.run(
        ["git", "ls-files", path_prefix],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
    )
    assert result.stdout.strip() == "", f"Tracked files under {path_prefix}: {result.stdout.strip()}"


@pytest.mark.parametrize("pattern", [
    "*.private.json",
    "*.private.yaml",
    "*.private.csv",
    ".env",
    ".env.*",
    "*.secret",
])
def test_private_pattern_not_tracked(pattern):
    result = subprocess.run(
        ["git", "ls-files", pattern],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
    )
    # .env.example is OK
    violations = [f for f in result.stdout.strip().splitlines() if f and not f.endswith(".example")]
    assert not violations, f"Private files tracked: {violations}"
