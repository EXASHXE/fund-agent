#!/usr/bin/env python3
"""fund-agent multi-harness uninstaller.

Removes only fund-agent-owned installed files/symlinks.
Refuses to delete unrelated user files.
Supports --dry-run.
"""
from __future__ import annotations

import argparse
from pathlib import Path

# fund-agent-owned skill/agent/plugin names
CODEX_SKILL_NAMES = [
    "fund-agent-e2e",
    "fund-agent-privacy-audit",
    "fund-agent-setup-private-data",
]
OPENCODE_SKILL_NAMES = [
    "fund-agent-e2e",
    "fund-agent-privacy-audit",
    "fund-agent-setup-private-data",
]
OPENCODE_AGENT_NAMES = [
    "fund-report-e2e.md",
    "fund-data-auditor.md",
]
OPENCODE_PLUGIN_NAMES = [
    "fund-agent-privacy-protection.ts",
]

CODEX_USER_SKILLS_DIR = Path.home() / ".agents" / "skills"
OPENCODE_USER_SKILLS_DIR = Path.home() / ".config" / "opencode" / "skills"
OPENCODE_USER_AGENTS_DIR = Path.home() / ".config" / "opencode" / "agents"
OPENCODE_USER_PLUGINS_DIR = Path.home() / ".config" / "opencode" / "plugins"
CLAUDE_USER_PLUGIN_DIR = Path.home() / ".claude" / "plugins"


def _log(dry_run: bool, msg: str) -> None:
    prefix = "[dry-run] " if dry_run else ""
    print(f"{prefix}{msg}")


def _is_fund_agent_owned(path: Path) -> bool:
    """Check if a path is owned by fund-agent."""
    name = path.name
    return (
        name.startswith("fund-agent-")
        or name.startswith("fund-report-")
        or name.startswith("fund-data-")
        or name == "fund-agent"
    )


def _remove_path(path: Path, dry_run: bool) -> bool:
    if not path.exists() and not path.is_symlink():
        _log(dry_run, f"  SKIP (not found): {path}")
        return False
    if not _is_fund_agent_owned(path):
        _log(dry_run, f"  REFUSE (not fund-agent-owned): {path}")
        return False
    if dry_run:
        _log(True, f"  would remove: {path}")
        return True
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        import shutil
        shutil.rmtree(str(path))
    elif path.is_file():
        path.unlink()
    else:
        _log(dry_run, f"  SKIP (unknown type): {path}")
        return False
    _log(False, f"  removed: {path}")
    return True


def uninstall_claude_code(dry_run: bool) -> list[str]:
    _log(dry_run, "Uninstalling Claude Code...")
    removed: list[str] = []
    target = CLAUDE_USER_PLUGIN_DIR / "fund-agent"
    if (target.exists() or target.is_symlink()) and _remove_path(target, dry_run):
        removed.append(str(target))
    return removed


def uninstall_codex(dry_run: bool) -> list[str]:
    _log(dry_run, "Uninstalling Codex...")
    removed: list[str] = []
    for skill_name in CODEX_SKILL_NAMES:
        target = CODEX_USER_SKILLS_DIR / skill_name
        if _remove_path(target, dry_run):
            removed.append(str(target))
    return removed


def uninstall_opencode(dry_run: bool) -> list[str]:
    _log(dry_run, "Uninstalling OpenCode...")
    removed: list[str] = []
    for skill_name in OPENCODE_SKILL_NAMES:
        target = OPENCODE_USER_SKILLS_DIR / skill_name
        if _remove_path(target, dry_run):
            removed.append(str(target))
    for agent_name in OPENCODE_AGENT_NAMES:
        target = OPENCODE_USER_AGENTS_DIR / agent_name
        if _remove_path(target, dry_run):
            removed.append(str(target))
    for plugin_name in OPENCODE_PLUGIN_NAMES:
        target = OPENCODE_USER_PLUGINS_DIR / plugin_name
        if _remove_path(target, dry_run):
            removed.append(str(target))
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="fund-agent multi-harness uninstaller")
    parser.add_argument(
        "--target",
        choices=["claude-code", "codex", "opencode", "all"],
        default="all",
        help="Target harness (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without removing")
    args = parser.parse_args(argv)

    all_removed: list[str] = []

    if args.target in ("claude-code", "all"):
        all_removed.extend(uninstall_claude_code(args.dry_run))

    if args.target in ("codex", "all"):
        all_removed.extend(uninstall_codex(args.dry_run))

    if args.target in ("opencode", "all"):
        all_removed.extend(uninstall_opencode(args.dry_run))

    if all_removed:
        _log(args.dry_run, f"\nRemoved {len(all_removed)} items")
    else:
        _log(args.dry_run, "\nNo items to remove")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
