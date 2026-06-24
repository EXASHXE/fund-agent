#!/usr/bin/env python3
"""Private data setup doctor — checks private_data/ readiness without exposing sensitive content.

Checks existence, parseability, and schema validity of:
  - Alipay CSV files (count only, no content)
  - fund_identity_overrides.private.yaml
  - nav_overrides.private.json
  - portfolio_input.private.json
  - gitignore coverage for local_reports/ and eval_workspace/

Output is JSON-serializable with counts only. No real fund names, amounts,
transaction IDs, raw CSV rows, or API keys are ever included.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DATA_DIR = REPO_ROOT / "private_data"

FUND_CODE_RE = re.compile(r"^\d{6}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check(
    check_id: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "details": details or {},
    }


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


def _check_private_data_dir() -> dict[str, Any]:
    if PRIVATE_DATA_DIR.is_dir():
        return _check("private_data.exists", "OK", "private_data/ directory exists")
    return _check("private_data.exists", "WARNING", "private_data/ directory not found")


def _check_alipay_csv() -> dict[str, Any]:
    csv_files = list(PRIVATE_DATA_DIR.glob("*.csv")) if PRIVATE_DATA_DIR.is_dir() else []
    count = len(csv_files)
    if count > 0:
        return _check(
            "alipay_csv.exists",
            "OK",
            f"Found {count} CSV file(s) in private_data/",
            {"count": count},
        )
    return _check("alipay_csv.exists", "WARNING", "No CSV files found in private_data/")


def _check_identity_overrides() -> dict[str, Any]:
    yaml_path = PRIVATE_DATA_DIR / "fund_identity_overrides.private.yaml"
    if not yaml_path.exists():
        return _check("identity_overrides.exists", "WARNING", "fund_identity_overrides.private.yaml not found")

    # Parse YAML
    try:
        import yaml
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except ImportError:
        return _check("identity_overrides.parse", "FAILED", "PyYAML not installed — cannot parse overrides")
    except Exception as exc:
        return _check("identity_overrides.parse", "FAILED", f"YAML parse error: {exc}")

    if not isinstance(data, dict) or "funds" not in data:
        return _check("identity_overrides.schema", "FAILED", "Missing top-level 'funds' key")

    funds = data["funds"]
    if not isinstance(funds, list):
        return _check("identity_overrides.schema", "FAILED", "'funds' must be a list")

    total = len(funds)
    invalid_codes: list[int] = []
    missing_raw_name: list[int] = []

    for i, entry in enumerate(funds):
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("fund_code", ""))
        if code and not FUND_CODE_RE.match(code):
            invalid_codes.append(i)
        if not entry.get("raw_name"):
            missing_raw_name.append(i)

    details: dict[str, Any] = {"total_entries": total}
    status = "OK"
    message = f"Identity overrides valid: {total} entries"

    if invalid_codes:
        details["invalid_code_indices"] = invalid_codes
        details["invalid_code_count"] = len(invalid_codes)
        status = "WARNING"
        message = f"{len(invalid_codes)} entry/entries have invalid fund_code (not 6 digits)"
    if missing_raw_name:
        details["missing_raw_name_indices"] = missing_raw_name
        details["missing_raw_name_count"] = len(missing_raw_name)
        if status != "WARNING":
            status = "WARNING"
        message += f"; {len(missing_raw_name)} entry/entries missing raw_name"

    return _check("identity_overrides.schema", status, message, details)


def _check_nav_overrides() -> dict[str, Any]:
    json_path = PRIVATE_DATA_DIR / "nav_overrides.private.json"
    if not json_path.exists():
        return _check("nav_overrides.exists", "WARNING", "nav_overrides.private.json not found")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _check("nav_overrides.parse", "FAILED", f"JSON parse error: {exc}")

    if not isinstance(data, dict):
        return _check("nav_overrides.schema", "FAILED", "Top-level value must be an object")

    total_funds = len(data)
    invalid_codes: list[str] = []
    invalid_dates: list[str] = []
    invalid_navs: list[str] = []

    for code, nav_map in data.items():
        if not FUND_CODE_RE.match(str(code)):
            invalid_codes.append(str(code))
        if not isinstance(nav_map, dict):
            continue
        for date_str, nav_val in nav_map.items():
            if not DATE_RE.match(str(date_str)):
                invalid_dates.append(f"{code}:{date_str}")
            if not isinstance(nav_val, (int, float)) or nav_val <= 0:
                invalid_navs.append(f"{code}:{date_str}")

    details: dict[str, Any] = {"total_funds": total_funds}
    status = "OK"
    message = f"NAV overrides valid: {total_funds} fund(s)"

    if invalid_codes:
        details["invalid_code_count"] = len(invalid_codes)
        status = "WARNING"
        message = f"{len(invalid_codes)} fund code(s) are not 6-digit"
    if invalid_dates:
        details["invalid_date_count"] = len(invalid_dates)
        if status != "WARNING":
            status = "WARNING"
        message += f"; {len(invalid_dates)} date(s) not in YYYY-MM-DD format"
    if invalid_navs:
        details["invalid_nav_count"] = len(invalid_navs)
        status = "WARNING"
        message += f"; {len(invalid_navs)} NAV value(s) not positive"

    return _check("nav_overrides.schema", status, message, details)


def _check_portfolio_input() -> dict[str, Any]:
    json_path = PRIVATE_DATA_DIR / "portfolio_input.private.json"
    if not json_path.exists():
        return _check("portfolio_input.exists", "INFO", "portfolio_input.private.json not found (optional)")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _check("portfolio_input.parse", "FAILED", f"JSON parse error: {exc}")
    if not isinstance(data, dict):
        return _check("portfolio_input.schema", "FAILED", "Top-level value must be an object")
    return _check("portfolio_input.exists", "OK", "portfolio_input.private.json exists and is valid JSON")


def _check_gitignore_coverage() -> dict[str, Any]:
    gitignore_path = REPO_ROOT / ".gitignore"
    if not gitignore_path.exists():
        return _check("gitignore.exists", "WARNING", ".gitignore not found")

    content = gitignore_path.read_text(encoding="utf-8")
    required_patterns = ["local_reports/", "eval_workspace/"]
    missing = [p for p in required_patterns if p not in content]
    if missing:
        return _check(
            "gitignore.coverage",
            "WARNING",
            f"Missing gitignore patterns: {missing}",
            {"missing": missing},
        )
    return _check("gitignore.coverage", "OK", "local_reports/ and eval_workspace/ are gitignored")


def _check_no_private_tracked() -> dict[str, Any]:
    private_paths = [
        "private_data/",
        "local_data/",
        "local_reports/",
        "eval_workspace/",
    ]
    private_patterns = [
        "*.private.json",
        "*.private.yaml",
        "*.private.csv",
        ".env",
        ".env.*",
        "*.secret",
    ]
    tracked = _git_ls_files(private_paths + private_patterns)
    if tracked:
        return _check(
            "privacy.no_tracked_private",
            "FAILED",
            f"{len(tracked)} private path(s) tracked by git",
            {"count": len(tracked)},
        )
    return _check("privacy.no_tracked_private", "OK", "No private files tracked by git")


def run_doctor() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    checks.append(_check_private_data_dir())
    checks.append(_check_alipay_csv())
    checks.append(_check_identity_overrides())
    checks.append(_check_nav_overrides())
    checks.append(_check_portfolio_input())
    checks.append(_check_gitignore_coverage())
    checks.append(_check_no_private_tracked())

    for c in checks:
        if c["status"] == "FAILED":
            errors.append(f"{c['id']}: {c['message']}")
        elif c["status"] == "WARNING":
            warnings.append(f"{c['id']}: {c['message']}")

    has_failed = any(c["status"] == "FAILED" for c in checks)
    has_warning = any(c["status"] == "WARNING" for c in checks)

    if has_failed:
        status = "error"
    elif has_warning:
        status = "warning"
    else:
        status = "ok"

    return {
        "ok": not has_failed,
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fund-agent-private-data-doctor",
        description=(
            "Private data setup doctor: checks private_data/ readiness "
            "without exposing sensitive content. Counts only."
        ),
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output.",
    )
    args = parser.parse_args(argv)

    result = run_doctor()

    indent = 2 if args.pretty else None
    separators = None if args.pretty else (",", ":")
    text = json.dumps(result, indent=indent, separators=separators, default=str)
    sys.stdout.write(text + "\n")
    sys.stdout.flush()

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
