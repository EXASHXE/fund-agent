#!/usr/bin/env python3
"""Run all audit scripts and write artifacts.

Deterministic, no-network, no file modifications outside artifacts/.

CLI:
    python scripts/audit/run_all_audits.py --pretty
    python scripts/audit/run_all_audits.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

AUDIT_DIR = ROOT / "artifacts" / "audit"


def _run_audit(module_name: str) -> dict[str, Any]:
    import importlib
    mod = importlib.import_module(module_name)
    return mod.audit()


def run_all() -> dict[str, Any]:
    results: dict[str, Any] = {}

    structure = _run_audit("scripts.audit.audit_project_structure")
    results["project_structure"] = structure

    dead_code = _run_audit("scripts.audit.audit_dead_code")
    results["dead_code"] = dead_code

    public_api = _run_audit("scripts.audit.audit_public_api")
    results["public_api"] = public_api

    docs_links = _run_audit("scripts.audit.audit_docs_links")
    results["docs_links"] = docs_links

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    (AUDIT_DIR / "project_structure.json").write_text(
        json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (AUDIT_DIR / "dead_code.json").write_text(
        json.dumps(dead_code, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (AUDIT_DIR / "public_api.json").write_text(
        json.dumps(public_api, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (AUDIT_DIR / "docs_links.json").write_text(
        json.dumps(docs_links, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    summary_lines = [
        "# Audit Summary",
        "",
        f"- Project structure areas: {len(structure.get('src_package_areas', []))} src areas",
        f"- Dead code candidates: {dead_code.get('total_candidates', 0)} "
        f"(HIGH: {dead_code.get('high_confidence', 0)}, "
        f"MEDIUM: {dead_code.get('medium_confidence', 0)}, "
        f"LOW: {dead_code.get('low_confidence', 0)})",
        f"- Deep imports in tests: {len(public_api.get('deep_imports_in_tests', []))}",
        f"- Deep imports in examples: {len(public_api.get('deep_imports_in_examples', []))}",
        f"- Facade recommendations: {len(public_api.get('facade_recommendations', []))}",
        f"- Broken doc links: {docs_links.get('summary', {}).get('broken_links', 0)}",
        f"- Overclaims: {docs_links.get('summary', {}).get('overclaims', 0)}",
        f"- Missing boundaries: {docs_links.get('summary', {}).get('missing_boundaries', 0)}",
    ]
    summary_text = "\n".join(summary_lines)
    (AUDIT_DIR / "summary.md").write_text(summary_text, encoding="utf-8")

    results["_artifacts_dir"] = str(AUDIT_DIR)
    return results


def _pretty(results: dict[str, Any]) -> str:
    lines = ["=== All Audits ===", ""]

    structure = results.get("project_structure", {})
    lines.append(f"Project structure: {len(structure.get('src_package_areas', []))} src areas")
    lines.append(f"  Large files: {len(structure.get('large_files', []))}")
    lines.append(f"  Missing READMEs: {len(structure.get('directories_missing_readme', []))}")
    lines.append("")

    dead = results.get("dead_code", {})
    lines.append(f"Dead code: {dead.get('total_candidates', 0)} candidates")
    lines.append(f"  HIGH: {dead.get('high_confidence', 0)}")
    lines.append(f"  MEDIUM: {dead.get('medium_confidence', 0)}")
    lines.append(f"  LOW: {dead.get('low_confidence', 0)}")
    lines.append("")

    api = results.get("public_api", {})
    lines.append(f"Public API: {len(api.get('console_scripts', []))} console scripts")
    lines.append(f"  Deep test imports: {len(api.get('deep_imports_in_tests', []))}")
    lines.append(f"  Deep example imports: {len(api.get('deep_imports_in_examples', []))}")
    lines.append(f"  Facade recommendations: {len(api.get('facade_recommendations', []))}")
    lines.append("")

    docs = results.get("docs_links", {})
    summary = docs.get("summary", {})
    lines.append(f"Docs: {summary.get('broken_links', 0)} broken links, "
                 f"{summary.get('overclaims', 0)} overclaims, "
                 f"{summary.get('missing_boundaries', 0)} missing boundaries")
    lines.append("")
    lines.append(f"Artifacts written to: {results.get('_artifacts_dir', 'N/A')}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all audits")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty text output")
    args = parser.parse_args()

    results = run_all()

    if args.json:
        cleaned = {k: v for k, v in results.items() if not k.startswith("_")}
        print(json.dumps(cleaned, indent=2, ensure_ascii=False))
    else:
        print(_pretty(results))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
