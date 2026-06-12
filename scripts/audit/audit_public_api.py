#!/usr/bin/env python3
"""Audit: public API surface.

Identifies current public entrypoints and unstable deep import paths.
Recommends facade targets. Deterministic, no-network.

CLI:
    python scripts/audit/audit_public_api.py --pretty
    python scripts/audit/audit_public_api.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_FACADE_TARGETS = {
    "fund_agent.workflow": [
        "src.skills_runtime.workflow",
        "src.tools.workflow",
    ],
    "fund_agent.regression": [
        "tests.helpers.personal_regression_runner",
    ],
    "fund_agent.quality": [
        "src.tools.workflow.advisory_quality_gate",
    ],
    "fund_agent.providers": [
        "src.host_data",
    ],
    "fund_agent.reporting": [
        "src.tools.workflow.final_report",
        "src.tools.portfolio.report_composer",
    ],
    "fund_agent.runtime": [
        "src.skills_runtime.fund_analysis",
        "src.skills_runtime.decision_support",
        "src.skillpack.run_skill",
    ],
}

_DEEP_IMPORT_PREFIXES = [
    "src.skills_runtime.workflow.",
    "src.tools.workflow.",
    "src.tools.portfolio.",
    "src.tools.evidence.",
    "src.host_data.",
    "src.skills_runtime.fund_analysis.",
    "src.skills_runtime.decision_support.",
]


def _console_scripts() -> list[dict[str, str]]:
    scripts: list[dict[str, str]] = []
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return scripts
    content = pyproject.read_text(encoding="utf-8")
    in_scripts = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_scripts = True
            continue
        if in_scripts and stripped.startswith("["):
            break
        if in_scripts and "=" in stripped:
            name, _, value = stripped.partition("=")
            scripts.append({
                "name": name.strip(),
                "module": value.strip().strip('"').strip("'"),
            })
    return scripts


def _script_commands() -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    scripts_dir = ROOT / "scripts"
    if not scripts_dir.exists():
        return commands
    for py_file in sorted(scripts_dir.rglob("*.py")):
        commands.append({
            "name": str(py_file.relative_to(ROOT)),
            "path": str(py_file.relative_to(ROOT)),
        })
    return commands


def _skillpack_entrypoints() -> list[dict[str, str]]:
    entrypoints: list[dict[str, str]] = []
    manifest = ROOT / "skillpack" / "fund-agent.skillpack.yaml"
    if not manifest.exists():
        return entrypoints
    content = manifest.read_text(encoding="utf-8")
    for match in re.finditer(r"runtime:\s*['\"]?([^'\"\n]+)['\"]?", content):
        entrypoints.append({
            "runtime": match.group(1).strip(),
            "source": "skillpack/fund-agent.skillpack.yaml",
        })
    return entrypoints


def _deep_imports_in_tests() -> list[dict[str, str]]:
    deep: list[dict[str, str]] = []
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return deep
    for py_file in tests_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r"(?:from|import)\s+(src\.[a-zA-Z0-9_.]+)", content):
            import_path = match.group(1)
            for prefix in _DEEP_IMPORT_PREFIXES:
                if import_path.startswith(prefix) and import_path != prefix.rstrip("."):
                    deep.append({
                        "import_path": import_path,
                        "used_in": str(py_file.relative_to(ROOT)),
                    })
                    break
    return deep


def _deep_imports_in_examples() -> list[dict[str, str]]:
    deep: list[dict[str, str]] = []
    examples_dir = ROOT / "examples"
    if not examples_dir.exists():
        return deep
    for py_file in examples_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r"(?:from|import)\s+(src\.[a-zA-Z0-9_.]+)", content):
            import_path = match.group(1)
            for prefix in _DEEP_IMPORT_PREFIXES:
                if import_path.startswith(prefix) and import_path != prefix.rstrip("."):
                    deep.append({
                        "import_path": import_path,
                        "used_in": str(py_file.relative_to(ROOT)),
                    })
                    break
    return deep


def audit() -> dict[str, Any]:
    result: dict[str, Any] = {}

    result["console_scripts"] = _console_scripts()
    result["script_commands"] = _script_commands()
    result["skillpack_entrypoints"] = _skillpack_entrypoints()

    test_deep = _deep_imports_in_tests()
    example_deep = _deep_imports_in_examples()
    result["deep_imports_in_tests"] = test_deep
    result["deep_imports_in_examples"] = example_deep

    facade_recommendations = []
    for facade, sources in _FACADE_TARGETS.items():
        matching_test = [
            d for d in test_deep
            if any(d["import_path"].startswith(s) for s in sources)
        ]
        matching_example = [
            d for d in example_deep
            if any(d["import_path"].startswith(s) for s in sources)
        ]
        facade_recommendations.append({
            "facade": facade,
            "wraps": sources,
            "deep_imports_in_tests": len(matching_test),
            "deep_imports_in_examples": len(matching_example),
        })
    result["facade_recommendations"] = facade_recommendations

    return result


def _pretty(result: dict[str, Any]) -> str:
    lines = ["=== Public API Audit ===", ""]

    lines.append("Console scripts:")
    for s in result["console_scripts"]:
        lines.append(f"  {s['name']} -> {s['module']}")
    lines.append("")

    lines.append("Skillpack entrypoints:")
    for e in result["skillpack_entrypoints"]:
        lines.append(f"  {e['runtime']} ({e['source']})")
    lines.append("")

    lines.append("Deep imports in tests:")
    for d in result["deep_imports_in_tests"]:
        lines.append(f"  {d['import_path']} (from {d['used_in']})")
    lines.append("")

    lines.append("Deep imports in examples:")
    for d in result["deep_imports_in_examples"]:
        lines.append(f"  {d['import_path']} (from {d['used_in']})")
    lines.append("")

    lines.append("Facade recommendations:")
    for r in result["facade_recommendations"]:
        lines.append(
            f"  {r['facade']}: wraps {r['wraps']} "
            f"(test refs: {r['deep_imports_in_tests']}, example refs: {r['deep_imports_in_examples']})"
        )
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit public API")
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
