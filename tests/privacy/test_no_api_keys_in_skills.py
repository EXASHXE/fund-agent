"""Skill files contain no real API key examples."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Patterns that indicate real (non-placeholder) API keys
REAL_KEY_PATTERNS = [
    re.compile(r'(?:api[_-]?key|apikey)\s*[=:]\s*["\'][A-Za-z0-9_\-]{20,}["\']', re.IGNORECASE),
    re.compile(r'(?:token|secret)\s*[=:]\s*["\'][A-Za-z0-9_\-]{30,}["\']', re.IGNORECASE),
    re.compile(r'Authorization\s*:\s*(?:Bearer|Basic)\s+[A-Za-z0-9_\-=+/]{20,}', re.IGNORECASE),
]

SKILL_DIRS = [
    REPO_ROOT / "skills",
    REPO_ROOT / ".agents" / "skills",
    REPO_ROOT / ".opencode" / "skills",
]


def _collect_skill_files() -> list[Path]:
    files = []
    for d in SKILL_DIRS:
        if d.exists():
            files.extend(d.rglob("SKILL.md"))
    return files


@pytest.mark.parametrize("skill_file", _collect_skill_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_skill_no_real_api_keys(skill_file):
    content = skill_file.read_text(encoding="utf-8")
    for pat in REAL_KEY_PATTERNS:
        matches = pat.findall(content)
        # Allow placeholder patterns like "your-api-key" or "REPLACE"
        real_matches = [m for m in matches if not any(
            placeholder in m.lower()
            for placeholder in ["your", "replace", "example", "placeholder", "xxx", "todo"]
        )]
        assert not real_matches, f"Real key pattern in {skill_file}: {real_matches}"
