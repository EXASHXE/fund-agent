#!/usr/bin/env python3
"""Audit: docs links and claims.

Finds stale docs, broken local links, outdated claims, and references
to deprecated directions. Deterministic, no-network.

CLI:
    python scripts/audit/audit_docs_links.py --pretty
    python scripts/audit/audit_docs_links.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_OVERCLAIM_PATTERNS = [
    (r"(?i)automatic\s+trading", "overclaim: automatic trading"),
    (r"(?i)executes?\s+orders", "overclaim: executes orders"),
    (r"(?i)guaranteed?\s+real-?time\s+data", "overclaim: guaranteed real-time data"),
    (r"(?i)eastmoney\s+fully\s+supported", "overclaim: Eastmoney fully supported"),
    (r"(?i)xueqiu\s+fully\s+supported", "overclaim: Xueqiu fully supported"),
    (r"(?i)no\s+api\s+key\s+required\s+for\s+(?:eastmoney|xueqiu)", "overclaim: no API key required for provider with unknown status"),
    (r"(?i)research_?os\s+(?:runtime|loop|server|daemon)", "stale: research_os runtime reference"),
    (r"(?i)langgraph", "stale: LangGraph reference"),
    (r"(?i)planner\s+loop", "stale: planner loop reference"),
]

_MISSING_BOUNDARY_PATTERNS = [
    ("no-network", r"(?i)no.?(?:network|network\s+calls)"),
    ("no-broker", r"(?i)no.?(?:broker|order\s+execution)"),
]

_SCAN_DIRS = [
    ROOT / "docs",
    ROOT / "skills",
    ROOT / "examples",
    ROOT,
]

_SCAN_EXTENSIONS = {".md", ".py", ".yaml", ".yml", ".json"}


def _find_md_files() -> list[Path]:
    files: list[Path] = []
    for d in _SCAN_DIRS:
        if not d.exists():
            continue
        if d == ROOT:
            for name in ("README.md", "AGENTS.md", "CHANGELOG.md"):
                p = ROOT / name
                if p.exists():
                    files.append(p)
        else:
            for f in d.rglob("*.md"):
                files.append(f)
    return sorted(files)


def _find_local_links(content: str, source: Path) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for match in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", content):
        label = match.group(1)
        href = match.group(2)
        if href.startswith(("http://", "https://", "#", "mailto:")):
            continue
        links.append({"label": label, "href": href, "source": str(source.relative_to(ROOT))})
    return links


def _resolve_link(source: Path, href: str) -> Path | None:
    if href.startswith("/"):
        target = ROOT / href.lstrip("/")
    else:
        target = source.parent / href

    target = target.resolve()

    try:
        target.relative_to(ROOT)
    except ValueError:
        return None

    return target if target.exists() else None


def _check_overclaims(content: str, source: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for pattern, description in _OVERCLAIM_PATTERNS:
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count("\n") + 1
            issues.append({
                "path": str(source.relative_to(ROOT)),
                "issue": description,
                "severity": "HIGH",
                "line": line_num,
                "text": match.group(0),
                "suggested_fix": "remove or qualify the claim",
            })
    return issues


def _check_missing_boundaries(content: str, source: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if source.suffix != ".md":
        return issues
    rel = str(source.relative_to(ROOT))
    is_core_doc = rel.startswith("docs/") or rel == "README.md"
    if not is_core_doc:
        return issues

    for boundary_name, pattern in _MISSING_BOUNDARY_PATTERNS:
        if not re.search(pattern, content):
            issues.append({
                "path": rel,
                "issue": f"missing {boundary_name} boundary mention",
                "severity": "LOW",
                "line": None,
                "text": None,
                "suggested_fix": f"add {boundary_name} boundary statement",
            })
    return issues


def audit() -> dict[str, Any]:
    result: dict[str, Any] = {"broken_links": [], "overclaims": [], "missing_boundaries": []}

    md_files = _find_md_files()

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        links = _find_local_links(content, md_file)
        for link in links:
            resolved = _resolve_link(md_file, link["href"])
            if resolved is None:
                result["broken_links"].append({
                    "path": link["source"],
                    "href": link["href"],
                    "label": link["label"],
                    "severity": "MEDIUM",
                    "suggested_fix": "update or remove the link",
                })

        result["overclaims"].extend(_check_overclaims(content, md_file))
        result["missing_boundaries"].extend(_check_missing_boundaries(content, md_file))

    result["summary"] = {
        "files_scanned": len(md_files),
        "broken_links": len(result["broken_links"]),
        "overclaims": len(result["overclaims"]),
        "missing_boundaries": len(result["missing_boundaries"]),
    }

    return result


def _pretty(result: dict[str, Any]) -> str:
    lines = ["=== Docs Links & Claims Audit ===", ""]
    lines.append(f"Files scanned: {result['summary']['files_scanned']}")
    lines.append(f"Broken links: {result['summary']['broken_links']}")
    lines.append(f"Overclaims: {result['summary']['overclaims']}")
    lines.append(f"Missing boundaries: {result['summary']['missing_boundaries']}")
    lines.append("")

    if result["broken_links"]:
        lines.append("Broken links:")
        for bl in result["broken_links"]:
            lines.append(f"  {bl['path']}: [{bl['label']}]({bl['href']}) [{bl['severity']}]")
        lines.append("")

    if result["overclaims"]:
        lines.append("Overclaims:")
        for oc in result["overclaims"]:
            loc = f":{oc['line']}" if oc.get("line") else ""
            lines.append(f"  {oc['path']}{loc}: {oc['issue']} [{oc['severity']}]")
            if oc.get("text"):
                lines.append(f"    text: {oc['text']}")
        lines.append("")

    if result["missing_boundaries"]:
        lines.append("Missing boundaries:")
        for mb in result["missing_boundaries"]:
            lines.append(f"  {mb['path']}: {mb['issue']} [{mb['severity']}]")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit docs links and claims")
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
