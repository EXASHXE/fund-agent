""".gitignore covers required private patterns."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

REQUIRED_PATTERNS = [
    "private_data/",
    "*.private.json",
    "*.private.yaml",
    "*.private.csv",
    ".env",
]


def _read_gitignore() -> set[str]:
    gitignore = REPO_ROOT / ".gitignore"
    if not gitignore.exists():
        return set()
    content = gitignore.read_text(encoding="utf-8")
    return {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}


class TestGitignoreCoversPrivate:
    @pytest.mark.parametrize("pattern", REQUIRED_PATTERNS)
    def test_gitignore_includes_pattern(self, pattern):
        entries = _read_gitignore()
        # Check exact match or prefix match (e.g., ".env" should match ".env.*")
        found = pattern in entries or any(
            e.startswith(pattern.rstrip("/").rstrip("*"))
            for e in entries
        )
        assert found, f".gitignore missing pattern: {pattern}"
