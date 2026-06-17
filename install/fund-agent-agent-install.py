#!/usr/bin/env python3
"""fund-agent multi-harness installer.

Supports:
  --target claude-code|codex|opencode|all
  --mode symlink|copy
  --repo-root <path>
  --dry-run
  --force
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

VERSION = "0.10.5"

# Skill files to install per harness
CLAUDE_SKILL_DIRS = [
    "e2e-report",
    "setup-private-data",
    "audit-privacy",
]
CLAUDE_AGENT_FILES = [
    "fund-report-e2e.md",
    "fund-data-auditor.md",
]
CODEX_SKILL_DIRS = [
    "fund-agent-e2e",
    "fund-agent-privacy-audit",
    "fund-agent-setup-private-data",
]
OPENCODE_SKILL_DIRS = [
    "fund-agent-e2e",
    "fund-agent-privacy-audit",
    "fund-agent-setup-private-data",
]
OPENCODE_AGENT_FILES = [
    "fund-report-e2e.md",
    "fund-data-auditor.md",
]
OPENCODE_PLUGIN_FILES = [
    "fund-agent-privacy-protection.ts",
]

# Target paths per harness
CLAUDE_USER_PLUGIN_DIR = Path.home() / ".claude" / "plugins"
CODEX_USER_SKILLS_DIR = Path.home() / ".agents" / "skills"
OPENCODE_USER_SKILLS_DIR = Path.home() / ".config" / "opencode" / "skills"
OPENCODE_USER_AGENTS_DIR = Path.home() / ".config" / "opencode" / "agents"
OPENCODE_USER_PLUGINS_DIR = Path.home() / ".config" / "opencode" / "plugins"


def _log(dry_run: bool, msg: str) -> None:
    prefix = "[dry-run] " if dry_run else ""
    print(f"{prefix}{msg}")


def _install_file(src: Path, dst: Path, mode: str, dry_run: bool, force: bool) -> bool:
    if dst.exists() and not force:
        _log(dry_run, f"  SKIP (exists): {dst}")
        return False
    if dry_run:
        _log(True, f"  would {mode}: {src} -> {dst}")
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        os.symlink(str(src.resolve()), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
    _log(False, f"  {mode}: {src} -> {dst}")
    return True


def _install_skill_dir(src_dir: Path, dst_dir: Path, mode: str, dry_run: bool, force: bool) -> bool:
    """Install a skill directory (SKILL.md and references/)."""
    installed = False
    skill_md = src_dir / "SKILL.md"
    if not skill_md.exists():
        _log(dry_run, f"  SKIP (no SKILL.md): {src_dir}")
        return False
    installed |= _install_file(skill_md, dst_dir / "SKILL.md", mode, dry_run, force)
    refs_dir = src_dir / "references"
    if refs_dir.is_dir():
        for ref_file in refs_dir.iterdir():
            if ref_file.is_file():
                installed |= _install_file(ref_file, dst_dir / "references" / ref_file.name, mode, dry_run, force)
    return installed


def install_claude_code(repo_root: Path, mode: str, dry_run: bool, force: bool) -> list[str]:
    _log(dry_run, "Installing for Claude Code...")
    installed: list[str] = []

    # Validate plugin structure
    plugin_json = repo_root / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        _log(dry_run, f"  WARNING: {plugin_json} not found")
        return installed

    # Claude Code uses --plugin-dir, not file-level install.
    # Print the invocation command.
    _log(dry_run, f"  Claude Code install command: claude --plugin-dir {repo_root}")

    # Optionally symlink to user plugin dir if it exists
    if CLAUDE_USER_PLUGIN_DIR.exists():
        target = CLAUDE_USER_PLUGIN_DIR / "fund-agent"
        if mode == "symlink":
            _install_file(repo_root, target, "symlink", dry_run, force)
        installed.append(str(target))

    return installed


def install_codex(repo_root: Path, mode: str, dry_run: bool, force: bool) -> list[str]:
    _log(dry_run, "Installing for Codex...")
    installed: list[str] = []

    for skill_name in CODEX_SKILL_DIRS:
        src = repo_root / ".agents" / "skills" / skill_name
        dst = CODEX_USER_SKILLS_DIR / skill_name
        if src.is_dir():
            _install_skill_dir(src, dst, mode, dry_run, force)
            installed.append(str(dst))

    return installed


def install_opencode(repo_root: Path, mode: str, dry_run: bool, force: bool) -> list[str]:
    _log(dry_run, "Installing for OpenCode...")
    installed: list[str] = []

    for skill_name in OPENCODE_SKILL_DIRS:
        src = repo_root / ".opencode" / "skills" / skill_name
        dst = OPENCODE_USER_SKILLS_DIR / skill_name
        if src.is_dir():
            _install_skill_dir(src, dst, mode, dry_run, force)
            installed.append(str(dst))

    for agent_file in OPENCODE_AGENT_FILES:
        src = repo_root / ".opencode" / "agents" / agent_file
        dst = OPENCODE_USER_AGENTS_DIR / agent_file
        if src.exists():
            _install_file(src, dst, mode, dry_run, force)
            installed.append(str(dst))

    for plugin_file in OPENCODE_PLUGIN_FILES:
        src = repo_root / ".opencode" / "plugins" / plugin_file
        dst = OPENCODE_USER_PLUGINS_DIR / plugin_file
        if src.exists():
            _install_file(src, dst, mode, dry_run, force)
            installed.append(str(dst))

    return installed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="fund-agent multi-harness installer")
    parser.add_argument(
        "--target",
        choices=["claude-code", "codex", "opencode", "all"],
        default="all",
        help="Target harness (default: all)",
    )
    parser.add_argument(
        "--mode",
        choices=["symlink", "copy"],
        default="symlink",
        help="Install mode (default: symlink)",
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help="Repository root path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent.parent

    all_installed: list[str] = []

    if args.target in ("claude-code", "all"):
        all_installed.extend(install_claude_code(repo_root, args.mode, args.dry_run, args.force))

    if args.target in ("codex", "all"):
        all_installed.extend(install_codex(repo_root, args.mode, args.dry_run, args.force))

    if args.target in ("opencode", "all"):
        all_installed.extend(install_opencode(repo_root, args.mode, args.dry_run, args.force))

    if all_installed:
        _log(args.dry_run, f"\nInstalled {len(all_installed)} items")
    else:
        _log(args.dry_run, "\nNo items installed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
