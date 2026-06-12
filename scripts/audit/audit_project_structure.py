#!/usr/bin/env python3
"""Audit: project structure report.

Reports current repository structure, identifies large/complex/ambiguous
areas. Deterministic, no-network, no file modifications.

CLI:
    python scripts/audit/audit_project_structure.py --pretty
    python scripts/audit/audit_project_structure.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_TOP_LEVEL_DIRS = [
    "src", "examples", "tests", "docs", "scripts", "config",
    "skillpack", "skills", "tools", "legacy",
]

_SRC_PACKAGE_AREAS = [
    "src/graph",
    "src/host_data",
    "src/schemas",
    "src/skillpack",
    "src/skills_runtime",
    "src/tools",
]

_EXAMPLES_AREAS = [
    "examples/host_data_adapters",
    "examples/host_integration",
    "examples/personal_portfolio_regressions",
    "examples/scenarios",
    "examples/decision_support",
    "examples/e2e_advisory_workflows",
    "examples/thesis_generation",
    "examples/user_flows",
    "examples/reference_workflows",
]

_TESTS_AREAS = [
    "tests/architecture",
    "tests/contracts",
    "tests/docs",
    "tests/end_to_end",
    "tests/evidence",
    "tests/golden",
    "tests/host_data",
    "tests/install",
    "tests/integration",
    "tests/personal_regression",
    "tests/reporting",
    "tests/runtime_bridge",
    "tests/scripts",
    "tests/skillpack",
    "tests/skills_runtime",
    "tests/workflow",
]

_DOCS_AREAS = [
    "docs/contracts",
    "docs/design",
    "docs/host-integrations",
    "docs/install",
    "docs/archive",
    "docs/workflows",
]

_LARGE_FILE_THRESHOLD = 500
_MANY_RESPONSIBILITY_THRESHOLD = 800


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in open(path, encoding="utf-8", errors="replace"))
    except (OSError, UnicodeDecodeError):
        return 0


def _list_py_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.py") if p.is_file())


def _dir_has_readme(directory: Path) -> bool:
    return any(
        (directory / name).exists()
        for name in ("README.md", "README.rst", "README.txt")
    )


def audit() -> dict[str, Any]:
    result: dict[str, Any] = {}

    top_dirs = []
    for d in _TOP_LEVEL_DIRS:
        p = ROOT / d
        top_dirs.append({"name": d, "exists": p.exists(), "is_dir": p.is_dir()})
    result["top_level_directories"] = top_dirs

    src_areas = []
    for area in _SRC_PACKAGE_AREAS:
        p = ROOT / area
        py_files = _list_py_files(p)
        total_lines = sum(_count_lines(f) for f in py_files)
        src_areas.append({
            "name": area,
            "exists": p.exists(),
            "python_files": len(py_files),
            "total_lines": total_lines,
        })
    result["src_package_areas"] = src_areas

    examples_areas = []
    for area in _EXAMPLES_AREAS:
        p = ROOT / area
        files = list(p.rglob("*")) if p.exists() else []
        examples_areas.append({
            "name": area,
            "exists": p.exists(),
            "file_count": len([f for f in files if f.is_file()]),
        })
    result["examples_areas"] = examples_areas

    tests_areas = []
    for area in _TESTS_AREAS:
        p = ROOT / area
        py_files = _list_py_files(p)
        tests_areas.append({
            "name": area,
            "exists": p.exists(),
            "test_files": len(py_files),
        })
    result["tests_areas"] = tests_areas

    docs_areas = []
    for area in _DOCS_AREAS:
        p = ROOT / area
        md_files = list(p.rglob("*.md")) if p.exists() else []
        docs_areas.append({
            "name": area,
            "exists": p.exists(),
            "doc_files": len(md_files),
        })
    result["docs_areas"] = docs_areas

    scripts_files = _list_py_files(ROOT / "scripts")
    result["scripts_area"] = {
        "python_files": len(scripts_files),
        "files": [str(f.relative_to(ROOT)) for f in scripts_files],
    }

    large_files = []
    for py_file in (ROOT / "src").rglob("*.py"):
        lines = _count_lines(py_file)
        if lines >= _LARGE_FILE_THRESHOLD:
            large_files.append({
                "path": str(py_file.relative_to(ROOT)),
                "lines": lines,
            })
    large_files.sort(key=lambda x: x["lines"], reverse=True)
    result["large_files"] = large_files

    many_responsibility = []
    for py_file in (ROOT / "src").rglob("*.py"):
        lines = _count_lines(py_file)
        if lines >= _MANY_RESPONSIBILITY_THRESHOLD:
            many_responsibility.append({
                "path": str(py_file.relative_to(ROOT)),
                "lines": lines,
                "recommendation": "consider splitting into focused modules",
            })
    many_responsibility.sort(key=lambda x: x["lines"], reverse=True)
    result["files_with_many_responsibilities"] = many_responsibility

    missing_readme = []
    for d in _SRC_PACKAGE_AREAS + _EXAMPLES_AREAS + _TESTS_AREAS:
        p = ROOT / d
        if p.exists() and p.is_dir() and not _dir_has_readme(p):
            missing_readme.append(d)
    result["directories_missing_readme"] = missing_readme

    ambiguous = []
    for py_file in (ROOT / "src").rglob("*.py"):
        name = py_file.stem.lower()
        if name in ("utils", "helpers", "misc", "common", "core", "base"):
            if name != "base":
                ambiguous.append({
                    "path": str(py_file.relative_to(ROOT)),
                    "reason": f"ambiguous name '{name}'",
                })
    result["ambiguous_file_names"] = ambiguous

    return result


def _pretty(result: dict[str, Any]) -> str:
    lines = ["=== Project Structure Audit ===", ""]

    lines.append("Top-level directories:")
    for d in result["top_level_directories"]:
        status = "exists" if d["exists"] else "MISSING"
        lines.append(f"  {d['name']}: {status}")
    lines.append("")

    lines.append("src/ package areas:")
    for a in result["src_package_areas"]:
        if a["exists"]:
            lines.append(f"  {a['name']}: {a['python_files']} py files, {a['total_lines']} lines")
        else:
            lines.append(f"  {a['name']}: MISSING")
    lines.append("")

    lines.append("Large files (>=500 lines):")
    for f in result["large_files"]:
        lines.append(f"  {f['path']}: {f['lines']} lines")
    if not result["large_files"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("Files with many responsibilities (>=800 lines):")
    for f in result["files_with_many_responsibilities"]:
        lines.append(f"  {f['path']}: {f['lines']} lines - {f['recommendation']}")
    if not result["files_with_many_responsibilities"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("Directories missing README.md:")
    for d in result["directories_missing_readme"]:
        lines.append(f"  {d}")
    if not result["directories_missing_readme"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("Ambiguous file names:")
    for f in result["ambiguous_file_names"]:
        lines.append(f"  {f['path']}: {f['reason']}")
    if not result["ambiguous_file_names"]:
        lines.append("  (none)")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit project structure")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty text output")
    args = parser.parse_args()

    result = audit()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_pretty(result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
