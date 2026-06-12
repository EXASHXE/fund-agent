#!/usr/bin/env python3
"""Audit: dead code detection.

Identifies candidate unused files or stale references using conservative
heuristics. Does NOT delete anything. Deterministic, no-network.

CLI:
    python scripts/audit/audit_dead_code.py --pretty
    python scripts/audit/audit_dead_code.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_PROTECTED_PREFIXES = (
    "skills/",
    "src/skills_runtime/",
    "src/skillpack/",
    "src/schemas/",
    "src/host_data/",
    "src/graph/",
    "src/tools/",
    "examples/runtime_bridge_",
    "examples/minimal_",
    "examples/personal_portfolio_regressions/",
    "examples/scenarios/",
    "tests/",
)

_PROTECTED_NAMES = {
    "__init__.py",
    "conftest.py",
    "VERSION",
    "pyproject.toml",
    "README.md",
    "CHANGELOG.md",
    "AGENTS.md",
}

_SKILL_FILES: set[str] = set()
_SKILLPACK_FILES: set[str] = set()


def _load_protected_references() -> tuple[set[str], set[str]]:
    skill_refs: set[str] = set()
    skillpack_refs: set[str] = set()

    skills_dir = ROOT / "skills"
    if skills_dir.exists():
        for f in skills_dir.rglob("*.md"):
            skill_refs.add(str(f.relative_to(ROOT)))

    skillpack_dir = ROOT / "skillpack"
    if skillpack_dir.exists():
        for f in skillpack_dir.rglob("*"):
            if f.is_file():
                skillpack_refs.add(str(f.relative_to(ROOT)))

    return skill_refs, skillpack_refs


def _find_import_references(path: Path, root: Path) -> set[str]:
    refs: set[str] = set()
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return refs

    module_path = str(path.relative_to(root)).replace("/", ".").replace("\\", ".")
    if module_path.endswith(".py"):
        module_path = module_path[:-3]

    parts = module_path.split(".")
    for i in range(len(parts)):
        partial = ".".join(parts[i:])
        refs.add(partial)

    for match in re.finditer(r"(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", content):
        refs.add(match.group(1))

    for match in re.finditer(r"['\"]([^'\"]+\.py)['\"]", content):
        refs.add(match.group(1))

    return refs


def _find_file_references(path: Path, root: Path) -> set[str]:
    refs: set[str] = set()
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return refs

    for match in re.finditer(r"['\"]([^'\"]+\.(py|md|json|yaml|yml))['\"]", content):
        ref = match.group(1)
        if not ref.startswith(("http://", "https://")):
            refs.add(ref)

    return refs


def _is_referenced(file_rel: str, all_refs: set[str]) -> bool:
    if file_rel in all_refs:
        return True
    stem = Path(file_rel).stem
    for ref in all_refs:
        if stem in ref:
            return True
    return False


def _pyproject_script_references() -> set[str]:
    refs: set[str] = set()
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return refs
    try:
        content = pyproject.read_text(encoding="utf-8")
    except OSError:
        return refs
    for match in re.finditer(r"=\s*\"([^\"]+)\"", content):
        refs.add(match.group(1))
    return refs


def audit() -> dict[str, Any]:
    global _SKILL_FILES, _SKILLPACK_FILES
    _SKILL_FILES, _SKILLPACK_FILES = _load_protected_references()

    candidates: list[dict[str, Any]] = []

    all_refs: set[str] = set()
    scan_dirs = [ROOT / "src", ROOT / "tests", ROOT / "examples", ROOT / "scripts"]
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            all_refs |= _find_import_references(py_file, ROOT)
            all_refs |= _find_file_references(py_file, ROOT)

    for md_file in (ROOT / "docs").rglob("*.md"):
        all_refs |= _find_file_references(md_file, ROOT)
    for md_file in (ROOT / "skills").rglob("*.md"):
        all_refs |= _find_file_references(md_file, ROOT)
    if (ROOT / "README.md").exists():
        all_refs |= _find_file_references(ROOT / "README.md", ROOT)

    all_refs |= _pyproject_script_references()

    for py_file in (ROOT / "src").rglob("*.py"):
        rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
        if _is_referenced(rel, all_refs):
            continue
        confidence = "LOW"
        action = "keep"
        reason = "not directly referenced by import/text scan"

        for prefix in _PROTECTED_PREFIXES:
            if rel.startswith(prefix):
                confidence = "LOW"
                action = "keep"
                reason = f"protected path ({prefix})"
                break

        if py_file.name in _PROTECTED_NAMES:
            confidence = "LOW"
            action = "keep"
            reason = "protected filename"

        candidates.append({
            "path": rel,
            "reason": reason,
            "confidence": confidence,
            "referenced_by": [],
            "recommended_action": action,
        })

    for py_file in (ROOT / "examples").rglob("*.py"):
        rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
        if _is_referenced(rel, all_refs):
            continue
        candidates.append({
            "path": rel,
            "reason": "not directly referenced by import/text scan",
            "confidence": "MEDIUM",
            "referenced_by": [],
            "recommended_action": "review",
        })

    for py_file in (ROOT / "scripts").rglob("*.py"):
        rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
        if _is_referenced(rel, all_refs):
            continue
        candidates.append({
            "path": rel,
            "reason": "not directly referenced by import/text scan",
            "confidence": "MEDIUM",
            "referenced_by": [],
            "recommended_action": "review",
        })

    candidates.sort(key=lambda x: (x["confidence"], x["path"]))

    high = [c for c in candidates if c["confidence"] == "HIGH"]
    medium = [c for c in candidates if c["confidence"] == "MEDIUM"]
    low = [c for c in candidates if c["confidence"] == "LOW"]

    return {
        "total_candidates": len(candidates),
        "high_confidence": len(high),
        "medium_confidence": len(medium),
        "low_confidence": len(low),
        "candidates": candidates,
    }


def _pretty(result: dict[str, Any]) -> str:
    lines = ["=== Dead Code Audit ===", ""]
    lines.append(f"Total candidates: {result['total_candidates']}")
    lines.append(f"  HIGH confidence: {result['high_confidence']}")
    lines.append(f"  MEDIUM confidence: {result['medium_confidence']}")
    lines.append(f"  LOW confidence: {result['low_confidence']}")
    lines.append("")

    for level in ("HIGH", "MEDIUM", "LOW"):
        items = [c for c in result["candidates"] if c["confidence"] == level]
        if items:
            lines.append(f"{level} confidence candidates:")
            for c in items:
                lines.append(f"  {c['path']}: {c['reason']} [{c['recommended_action']}]")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit dead code")
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
