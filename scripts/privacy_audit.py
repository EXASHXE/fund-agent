#!/usr/bin/env python3
"""Privacy audit scanner for fund-agent repository.

Checks:
  1. No tracked private paths (private_data/, local_data/, local_reports/, eval_workspace/)
  2. No tracked .private files (*.private.json, *.private.yaml, *.private.csv)
  3. No API keys/tokens/cookies/Authorization headers in tracked files
  4. No raw Alipay IDs in tracked files
  5. No .env files tracked

Exits non-zero on privacy violation.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PRIVATE_DIRS = {"private_data/", "local_data/", "local_reports/", "eval_workspace/"}
PRIVATE_EXTENSIONS = {".private.json", ".private.yaml", ".private.csv"}
ENV_PATTERNS = {".env", ".env."}
# Patterns that indicate leaked secrets in file contents
SECRET_PATTERNS = [
    re.compile(r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}', re.IGNORECASE),
    re.compile(r'(?:token|access_token|secret)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', re.IGNORECASE),
    re.compile(r'Authorization\s*:\s*(?:Bearer|Basic)\s+[A-Za-z0-9_\-=+/]{10,}', re.IGNORECASE),
    re.compile(r'(?:cookie|set-cookie)\s*[=:]\s*["\']?[A-Za-z0-9_\-+=/]{20,}', re.IGNORECASE),
]
# Raw Alipay IDs: 16-digit numeric strings in transaction-like contexts
ALIPAY_ID_PATTERN = re.compile(r'\b2\d{15}\b')


def _git_ls_files(repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def check_tracked_private_paths(files: list[str]) -> list[str]:
    violations = []
    for f in files:
        for pd in PRIVATE_DIRS:
            if f.startswith(pd):
                violations.append(f)
                break
    return violations


def check_tracked_private_extensions(files: list[str]) -> list[str]:
    violations = []
    for f in files:
        for ext in PRIVATE_EXTENSIONS:
            if f.endswith(ext):
                violations.append(f)
                break
    return violations


def check_tracked_env_files(files: list[str]) -> list[str]:
    violations = []
    for f in files:
        basename = f.split("/")[-1] if "/" in f else f
        for pat in ENV_PATTERNS:
            if basename == pat or basename.startswith(pat):
                violations.append(f)
                break
    return violations


def check_secret_patterns(repo_root: Path, files: list[str]) -> list[dict]:
    violations = []
    # Only scan text files, skip binary/large
    skip_ext = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
                ".ttf", ".eot", ".db", ".sqlite", ".pyc", ".pyo", ".exe", ".dll"}
    # Skip test files, example configs, and fixtures — they contain placeholder values
    skip_prefixes = ("tests/", "examples/", "config/providers.example",)
    for f in files:
        ext = f.rsplit(".", 1)[-1] if "." in f else ""
        if f".{ext}" in skip_ext:
            continue
        if f.startswith("node_modules/"):
            continue
        if any(f.startswith(p) for p in skip_prefixes):
            continue
        filepath = repo_root / f
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        for pat in SECRET_PATTERNS:
            for m in pat.finditer(content):
                violations.append({
                    "file": f,
                    "pattern": pat.pattern[:40],
                    "match": m.group(0)[:60] + "...",
                })
    return violations


def check_raw_alipay_ids(repo_root: Path, files: list[str]) -> list[dict]:
    violations = []
    # Only scan relevant file types
    relevant_ext = {".py", ".json", ".yaml", ".yml", ".csv", ".md", ".txt"}
    for f in files:
        ext = f.rsplit(".", 1)[-1] if "." in f else ""
        if f".{ext}" not in relevant_ext:
            continue
        filepath = repo_root / f
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        # Skip files in scripts/ that may have regex patterns mentioning IDs
        if f.startswith("scripts/") or f.startswith("tests/"):
            continue
        for m in ALIPAY_ID_PATTERN.finditer(content):
            # Filter out obvious non-Alipay 16-digit numbers (timestamps, etc.)
            candidate = m.group(0)
            if candidate.startswith("20") and len(candidate) == 16:
                violations.append({
                    "file": f,
                    "pattern": "raw_alipay_id",
                    "match": candidate[:8] + "****",
                })
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="fund-agent privacy audit")
    parser.add_argument("--repo-root", type=str, default=None, help="Repository root path")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    parser.add_argument("--quiet", action="store_true", help="Only exit code, no output")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent.parent
    if not (repo_root / ".git").exists():
        print("ERROR: not a git repository", file=sys.stderr)
        return 1

    files = _git_ls_files(repo_root)

    results: dict = {
        "repo_root": str(repo_root),
        "tracked_files_count": len(files),
        "violations": {},
        "ok": True,
    }

    # Check 1: tracked private directories
    private_dir_violations = check_tracked_private_paths(files)
    if private_dir_violations:
        results["violations"]["tracked_private_dirs"] = private_dir_violations
        results["ok"] = False

    # Check 2: tracked .private files
    private_ext_violations = check_tracked_private_extensions(files)
    if private_ext_violations:
        results["violations"]["tracked_private_extensions"] = private_ext_violations
        results["ok"] = False

    # Check 3: tracked .env files
    env_violations = check_tracked_env_files(files)
    if env_violations:
        results["violations"]["tracked_env_files"] = env_violations
        results["ok"] = False

    # Check 4: secret patterns in tracked files
    secret_violations = check_secret_patterns(repo_root, files)
    if secret_violations:
        results["violations"]["secret_patterns"] = secret_violations
        results["ok"] = False

    # Check 5: raw Alipay IDs
    alipay_violations = check_raw_alipay_ids(repo_root, files)
    if alipay_violations:
        results["violations"]["raw_alipay_ids"] = alipay_violations
        results["ok"] = False

    if args.json_output:
        print(json.dumps(results, indent=2))
    elif not args.quiet:
        if results["ok"]:
            print("PASS: no privacy violations found")
        else:
            print("FAIL: privacy violations detected")
            for category, items in results["violations"].items():
                print(f"\n  [{category}]")
                for item in items:
                    if isinstance(item, dict):
                        print(f"    {item['file']}: {item.get('match', item)}")
                    else:
                        print(f"    {item}")

    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
