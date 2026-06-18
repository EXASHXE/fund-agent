"""OpenCode plugin committed test — verify plugin file is tracked or claims removed."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_FILE = REPO_ROOT / ".opencode" / "plugins" / "fund-agent-privacy-protection.ts"


class TestOpenCodePluginCommitted:
    """Verify promised OpenCode plugin file exists in git-tracked files."""

    def test_plugin_file_exists(self):
        """The OpenCode privacy protection plugin file must exist."""
        assert PLUGIN_FILE.exists(), (
            ".opencode/plugins/fund-agent-privacy-protection.ts must exist"
        )

    def test_plugin_file_is_git_tracked(self):
        """The plugin file must be tracked by git (not ignored)."""
        result = subprocess.run(
            ["git", "ls-files", str(PLUGIN_FILE.relative_to(REPO_ROOT))],
            capture_output=True, text=True, timeout=15,
            cwd=str(REPO_ROOT),
        )
        assert result.stdout.strip(), (
            ".opencode/plugins/fund-agent-privacy-protection.ts must be git-tracked. "
            "Add unignore rule in .gitignore and git add -f the file."
        )

    def test_plugin_file_has_substance(self):
        """The plugin file must contain meaningful code, not be empty."""
        content = PLUGIN_FILE.read_text(encoding="utf-8")
        assert len(content) > 100, "Plugin file must contain meaningful code"
        assert "PROTECTED_PATTERNS" in content or "privacy" in content.lower(), (
            "Plugin file must contain privacy protection logic"
        )

    def test_gitignore_unignores_plugin(self):
        """The .gitignore must have an unignore rule for the plugin file."""
        gitignore = REPO_ROOT / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        assert "!.opencode/plugins/fund-agent-privacy-protection.ts" in content, (
            ".gitignore must have unignore rule for the plugin file"
        )

    def test_no_private_plugin_artifacts_tracked(self):
        """No private plugin artifacts (node_modules, package.json) should be tracked."""
        result = subprocess.run(
            ["git", "ls-files", ".opencode/"],
            capture_output=True, text=True, timeout=15,
            cwd=str(REPO_ROOT),
        )
        tracked = result.stdout.strip().splitlines()
        for f in tracked:
            assert "node_modules" not in f, f"Should not track node_modules: {f}"
            assert "package.json" not in f or "fund-agent-privacy-protection" in f, (
                f"Should not track .opencode/package.json: {f}"
            )
