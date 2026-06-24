"""Privacy guard tests for agent wrappers."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPrivacyGuard:
    def test_no_private_files_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "private_data/", "local_data/", "local_reports/", "eval_workspace/"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
        )
        assert result.stdout.strip() == "", f"Private directories tracked: {result.stdout.strip()}"

    def test_no_private_extensions_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "*.private.json", "*.private.yaml", "*.private.csv", ".env", ".env.*", "*.secret"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
        )
        assert result.stdout.strip() == "", f"Private extensions tracked: {result.stdout.strip()}"

    def test_skill_files_no_real_api_keys(self):
        skill_dirs = [
            REPO_ROOT / "skills",
            REPO_ROOT / ".agents" / "skills",
            REPO_ROOT / ".opencode" / "skills",
        ]
        import re
        key_pattern = re.compile(r'(?:api[_-]?key|apikey)\s*[=:]\s*["\'][A-Za-z0-9]{20,}["\']', re.IGNORECASE)
        for skill_dir in skill_dirs:
            if not skill_dir.exists():
                continue
            for skill_md in skill_dir.rglob("SKILL.md"):
                content = skill_md.read_text(encoding="utf-8")
                matches = key_pattern.findall(content)
                assert not matches, f"Real API key pattern in {skill_md}: {matches}"
