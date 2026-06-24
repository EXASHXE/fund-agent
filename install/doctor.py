#!/usr/bin/env python3
"""fund-agent multi-harness doctor.

Checks wrapper structure, installed paths, executable bits, python
availability, optional env var presence (without printing values),
and that no private files are tracked by git.  Prints invocation
examples for each harness.

Wraps ``src.skillpack.doctor`` as the base check, then adds
harness-specific checks.

Supports:
  --target claude-code|codex|opencode|all
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE_PLUGIN_DIR = REPO_ROOT / ".claude-plugin"
CLAUDE_SKILLS_DIR = REPO_ROOT / "skills"
CLAUDE_AGENTS_DIR = REPO_ROOT / "agents"

CODEX_PLUGIN_DIR = REPO_ROOT / ".codex-plugin"
CODEX_SKILLS_DIR = REPO_ROOT / ".agents" / "skills"

OPENCODE_DIR = REPO_ROOT / ".opencode"
OPENCODE_SKILLS_DIR = OPENCODE_DIR / "skills"
OPENCODE_AGENTS_DIR = OPENCODE_DIR / "agents"
OPENCODE_PLUGINS_DIR = OPENCODE_DIR / "plugins"

BIN_DIR = REPO_ROOT / "bin"

CLAUDE_USER_PLUGIN_DIR = Path.home() / ".claude" / "plugins"
CODEX_USER_SKILLS_DIR = Path.home() / ".agents" / "skills"
OPENCODE_USER_SKILLS_DIR = Path.home() / ".config" / "opencode" / "skills"
OPENCODE_USER_AGENTS_DIR = Path.home() / ".config" / "opencode" / "agents"
OPENCODE_USER_PLUGINS_DIR = Path.home() / ".config" / "opencode" / "plugins"

CLAUDE_SKILL_NAMES = ["e2e-report", "setup-private-data", "audit-privacy"]
CLAUDE_AGENT_NAMES = ["fund-report-e2e.md", "fund-data-auditor.md"]
CODEX_SKILL_NAMES = ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"]
OPENCODE_SKILL_NAMES = ["fund-agent-e2e", "fund-agent-privacy-audit", "fund-agent-setup-private-data"]
OPENCODE_AGENT_NAMES = ["fund-report-e2e.md", "fund-data-auditor.md"]
OPENCODE_PLUGIN_NAMES = ["fund-agent-privacy-protection.ts"]

OPTIONAL_ENV_VARS = [
    "AKSHARE_API_KEY",
    "NEWS_API_KEY",
    "PROVIDER_API_KEY",
]

PRIVATE_GIT_PATHS = [
    "private_data/",
    "local_data/",
    "local_reports/",
    "eval_workspace/",
]

PRIVATE_GIT_PATTERNS = [
    "*.private.json",
    "*.private.yaml",
    "*.private.csv",
    ".env",
    ".env.*",
    "*.secret",
]


# ── Helpers ────────────────────────────────────────────────────────

def _check(check_id: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": status, "message": message, "details": details or {}}


def _git_ls_files(patterns: list[str]) -> list[str]:
    """Return git-tracked files matching any of *patterns*."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--"] + patterns,
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            return [line for line in result.stdout.strip().splitlines() if line]
    except Exception:
        pass
    return []


def _check_python() -> dict[str, Any]:
    python = shutil.which("python") or shutil.which("python3")
    if python:
        ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return _check("python.available", "OK", f"Python found: {python}", {"path": python, "version": ver})
    return _check("python.available", "FAILED", "Python not found on PATH")


def _check_executable(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        return _check(f"bin.{label}", "FAILED", f"Not found: {path}")
    if os.access(str(path), os.X_OK):
        return _check(f"bin.{label}", "OK", f"Executable: {path}")
    return _check(f"bin.{label}", "WARNING", f"Exists but not executable: {path}")


def _check_env_vars() -> list[dict[str, Any]]:
    checks = []
    for var in OPTIONAL_ENV_VARS:
        present = var in os.environ
        status = "OK" if present else "INFO"
        msg = f"{var} is set" if present else f"{var} is not set (optional)"
        checks.append(_check(f"env.{var}", status, msg))
    return checks


def _check_no_private_tracked() -> dict[str, Any]:
    tracked = _git_ls_files(PRIVATE_GIT_PATHS + PRIVATE_GIT_PATTERNS)
    if tracked:
        return _check("privacy.no_tracked_private", "FAILED",
                       f"{len(tracked)} private path(s) tracked by git",
                       {"files": tracked[:20]})
    return _check("privacy.no_tracked_private", "OK", "No private files tracked by git")


# ── Harness-specific checks ───────────────────────────────────────

def check_claude_code() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    # Plugin structure
    pj = CLAUDE_PLUGIN_DIR / "plugin.json"
    if pj.exists():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            checks.append(_check("claude.plugin_json", "OK", "plugin.json valid",
                                  {"name": data.get("name"), "version": data.get("version")}))
        except Exception as exc:
            checks.append(_check("claude.plugin_json", "FAILED", f"plugin.json invalid: {exc}"))
    else:
        checks.append(_check("claude.plugin_json", "FAILED", f"plugin.json not found: {pj}"))

    # Skills
    for name in CLAUDE_SKILL_NAMES:
        skill_md = CLAUDE_SKILLS_DIR / name / "SKILL.md"
        if skill_md.exists():
            checks.append(_check(f"claude.skill.{name}", "OK", f"Skill exists: {name}/SKILL.md"))
        else:
            checks.append(_check(f"claude.skill.{name}", "FAILED", f"Skill missing: {skill_md}"))

    # Agents
    for name in CLAUDE_AGENT_NAMES:
        agent_md = CLAUDE_AGENTS_DIR / name
        if agent_md.exists():
            checks.append(_check(f"claude.agent.{name}", "OK", f"Agent exists: {name}"))
        else:
            checks.append(_check(f"claude.agent.{name}", "FAILED", f"Agent missing: {agent_md}"))

    # User-level install hint
    checks.append(_check("claude.install_hint", "INFO",
                          "Install with: claude --plugin-dir <repo-root>",
                          {"command": f"claude --plugin-dir {REPO_ROOT}"}))

    return checks


def check_codex() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    # Plugin manifest
    pj = CODEX_PLUGIN_DIR / "plugin.json"
    if pj.exists():
        checks.append(_check("codex.plugin_json", "OK", ".codex-plugin/plugin.json exists"))
    else:
        checks.append(_check("codex.plugin_json", "FAILED", f"plugin.json not found: {pj}"))

    # Skills
    for name in CODEX_SKILL_NAMES:
        skill_md = CODEX_SKILLS_DIR / name / "SKILL.md"
        if skill_md.exists():
            checks.append(_check(f"codex.skill.{name}", "OK", f"Skill exists: {name}/SKILL.md"))
        else:
            checks.append(_check(f"codex.skill.{name}", "FAILED", f"Skill missing: {skill_md}"))

    # User-level install status
    for name in CODEX_SKILL_NAMES:
        dst = CODEX_USER_SKILLS_DIR / name
        if dst.exists() or dst.is_symlink():
            checks.append(_check(f"codex.installed.{name}", "OK", f"Installed: {dst}"))
        else:
            checks.append(_check(f"codex.installed.{name}", "INFO", f"Not installed: {dst}"))

    return checks


def check_opencode() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    # Skills
    for name in OPENCODE_SKILL_NAMES:
        skill_md = OPENCODE_SKILLS_DIR / name / "SKILL.md"
        if skill_md.exists():
            checks.append(_check(f"opencode.skill.{name}", "OK", f"Skill exists: {name}/SKILL.md"))
        else:
            checks.append(_check(f"opencode.skill.{name}", "FAILED", f"Skill missing: {skill_md}"))

    # Agents
    for name in OPENCODE_AGENT_NAMES:
        agent_md = OPENCODE_AGENTS_DIR / name
        if agent_md.exists():
            checks.append(_check(f"opencode.agent.{name}", "OK", f"Agent exists: {name}"))
        else:
            checks.append(_check(f"opencode.agent.{name}", "FAILED", f"Agent missing: {agent_md}"))

    # Plugin
    for name in OPENCODE_PLUGIN_NAMES:
        plugin_ts = OPENCODE_PLUGINS_DIR / name
        if plugin_ts.exists():
            checks.append(_check(f"opencode.plugin.{name}", "OK", f"Plugin exists: {name}"))
        else:
            checks.append(_check(f"opencode.plugin.{name}", "FAILED", f"Plugin missing: {plugin_ts}"))

    # INSTALL.md
    install_md = OPENCODE_DIR / "INSTALL.md"
    if install_md.exists():
        checks.append(_check("opencode.install_md", "OK", "INSTALL.md exists"))
    else:
        checks.append(_check("opencode.install_md", "FAILED", f"INSTALL.md missing: {install_md}"))

    # User-level install status
    for name in OPENCODE_SKILL_NAMES:
        dst = OPENCODE_USER_SKILLS_DIR / name
        if dst.exists() or dst.is_symlink():
            checks.append(_check(f"opencode.installed.skill.{name}", "OK", f"Installed: {dst}"))
        else:
            checks.append(_check(f"opencode.installed.skill.{name}", "INFO", f"Not installed: {dst}"))

    for name in OPENCODE_AGENT_NAMES:
        dst = OPENCODE_USER_AGENTS_DIR / name
        if dst.exists() or dst.is_symlink():
            checks.append(_check(f"opencode.installed.agent.{name}", "OK", f"Installed: {dst}"))
        else:
            checks.append(_check(f"opencode.installed.agent.{name}", "INFO", f"Not installed: {dst}"))

    for name in OPENCODE_PLUGIN_NAMES:
        dst = OPENCODE_USER_PLUGINS_DIR / name
        if dst.exists() or dst.is_symlink():
            checks.append(_check(f"opencode.installed.plugin.{name}", "OK", f"Installed: {dst}"))
        else:
            checks.append(_check(f"opencode.installed.plugin.{name}", "INFO", f"Not installed: {dst}"))

    return checks


# ── Main ───────────────────────────────────────────────────────────

def run_doctor(target: str = "all") -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    # General checks
    checks.append(_check_python())

    # Bin runners
    checks.append(_check_executable(BIN_DIR / "fund-agent-e2e", "fund-agent-e2e"))
    checks.append(_check_executable(BIN_DIR / "fund-agent-privacy-check", "fund-agent-privacy-check"))

    # Env vars
    checks.extend(_check_env_vars())

    # Privacy
    checks.append(_check_no_private_tracked())

    # Harness-specific checks
    if target in ("claude-code", "all"):
        checks.extend(check_claude_code())
    if target in ("codex", "all"):
        checks.extend(check_codex())
    if target in ("opencode", "all"):
        checks.extend(check_opencode())

    # Base skillpack doctor
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from src.skillpack.doctor import run_doctor as _base_doctor
        base_result = _base_doctor(include_smoke=False)
        for c in base_result.get("checks", []):
            checks.append({**c, "id": f"skillpack.{c['id']}"})
        if not base_result.get("ok"):
            errors.append("Base skillpack doctor reported failures")
    except Exception as exc:
        checks.append(_check("skillpack.doctor", "FAILED", f"Base doctor error: {exc}"))
        errors.append(f"Base doctor error: {exc}")

    # Invocation examples
    examples = [
        "Claude Code:  /fund-agent:e2e-report --as-of YYYY-MM-DD",
        "Codex:        $fund-agent-e2e",
        "OpenCode:     fund-agent-e2e  or  @fund-report-e2e",
        "Install:      python install/fund-agent-agent-install.py --target all --mode symlink",
        "Doctor:       python install/fund-agent-agent-doctor.py --target all",
        "Uninstall:    python install/fund-agent-agent-uninstall.py --target all --dry-run",
    ]

    # Summary
    failed = [c for c in checks if c["status"] == "FAILED"]
    warnings = [c for c in checks if c["status"] == "WARNING"]
    ok = len(failed) == 0

    return {
        "ok": ok,
        "status": "OK" if ok else "FAILED",
        "checks": checks,
        "errors": [f"{c['id']}: {c['message']}" for c in failed] + errors,
        "warnings": [f"{c['id']}: {c['message']}" for c in warnings],
        "invocation_examples": examples,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fund-agent-agent-doctor",
        description="fund-agent multi-harness doctor: checks structure, paths, and readiness.",
    )
    parser.add_argument(
        "--target",
        choices=["claude-code", "codex", "opencode", "all"],
        default="all",
        help="Target harness (default: all)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    args = parser.parse_args(argv)

    result = run_doctor(target=args.target)

    indent = 2 if args.pretty else None
    separators = None if args.pretty else (",", ":")
    text = json.dumps(result, indent=indent, separators=separators, default=str)
    sys.stdout.write(text + "\n")
    sys.stdout.flush()

    # Also print invocation examples to stderr for human readability
    sys.stderr.write("\nInvocation examples:\n")
    for ex in result.get("invocation_examples", []):
        sys.stderr.write(f"  {ex}\n")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
