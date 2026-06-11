#!/usr/bin/env python3
"""Automated install discovery verification for fund-agent v1.2.

Verifies that native OpenCode Agent Skills are installed, plugin files
are present (if applicable), and optionally runs runtime bridge checks.

Does NOT require OpenCode to be running.
Does NOT verify fund_agent_skills custom tool registration.
Does NOT change runtime behavior.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_SKILLS = (
    "fund-analysis",
    "decision-support",
    "news-research",
    "sentiment-analysis",
    "thesis-generation",
)
PRIMARY_SKILL = "fund-analysis"
SUPPORTING_SKILLS = tuple(s for s in CANONICAL_SKILLS if s != PRIMARY_SKILL)
MARKER_FILENAME = ".fund-agent-generated.json"
PLUGIN_FILENAME = "fund-agent.js"
PLUGIN_DIR_NAME = "plugins"
OPENCODE_DIR_NAME = ".opencode"
SKILLS_DIR_NAME = "skills"


def _check_native_skills(project: Path) -> dict[str, Any]:
    skills_dir = project / OPENCODE_DIR_NAME / SKILLS_DIR_NAME
    found: dict[str, bool] = {}
    missing: list[str] = []
    for slug in CANONICAL_SKILLS:
        skill_md = skills_dir / slug / "SKILL.md"
        found[slug] = skill_md.is_file()
        if not found[slug]:
            missing.append(slug)

    marker_path = skills_dir / MARKER_FILENAME
    marker_ok = marker_path.is_file()
    marker_data: dict[str, Any] | None = None
    if marker_ok:
        try:
            marker_data = json.loads(marker_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            marker_data = None

    primary_ok = found.get(PRIMARY_SKILL, False)
    supporting_ok = all(found.get(s, False) for s in SUPPORTING_SKILLS)

    return {
        "ok": not missing,
        "skills_dir": str(skills_dir),
        "found": found,
        "missing": missing,
        "marker_exists": marker_ok,
        "marker_data": marker_data,
        "primary_ok": primary_ok,
        "supporting_ok": supporting_ok,
    }


def _check_plugin_file(project: Path) -> dict[str, Any]:
    plugin_path = project / OPENCODE_DIR_NAME / PLUGIN_DIR_NAME / PLUGIN_FILENAME
    exists = plugin_path.is_file() or plugin_path.is_symlink()
    is_valid = False
    content_hint = ""

    if exists:
        try:
            target = plugin_path.resolve()
            if target.is_file():
                head = target.read_text(encoding="utf-8", errors="replace")[:200]
                is_valid = "fund-agent" in head.lower() or "opencode" in head.lower()
                content_hint = "contains fund-agent or opencode reference"
            else:
                content_hint = "symlink target does not resolve to a file"
        except OSError as exc:
            content_hint = f"read error: {exc}"

    return {
        "ok": True,
        "path": str(plugin_path),
        "exists": exists,
        "is_valid": is_valid,
        "content_hint": content_hint,
        "custom_tool_verifiable": False,
        "note": (
            "Plugin custom tool registration (fund_agent_skills) cannot be "
            "verified from a script. Mode A custom tools are optional and "
            "environment-dependent. Use Mode B native Agent Skills as the "
            "recommended verified path."
        ),
    }


def _check_manifest_roles(fund_agent_root: Path) -> dict[str, Any]:
    manifest_path = fund_agent_root / "skillpack" / "fund-agent.skillpack.yaml"
    if not manifest_path.is_file():
        return {
            "ok": False,
            "error": f"Manifest not found: {manifest_path}",
        }

    try:
        import yaml
    except ImportError:
        return {
            "ok": False,
            "error": "PyYAML not available; cannot parse manifest",
        }

    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Failed to parse manifest: {exc}",
        }

    primary = data.get("primary_skill", "")
    supporting = list(data.get("supporting_skills", []))
    skills = {s["name"]: s.get("role", "") for s in data.get("skills", [])}

    return {
        "ok": primary == PRIMARY_SKILL and set(supporting) == set(SUPPORTING_SKILLS),
        "primary_skill": primary,
        "supporting_skills": supporting,
        "skills_roles": skills,
    }


def _check_runtime_bridge(fund_agent_root: Path) -> dict[str, Any]:
    script_path = fund_agent_root / "scripts" / "run_skill.py"
    if not script_path.is_file():
        return {
            "ok": False,
            "error": f"run_skill.py not found: {script_path}",
        }

    results: dict[str, Any] = {}

    cmd_list = [sys.executable, str(script_path), "--list-skills", "--pretty"]
    try:
        proc = subprocess.run(
            cmd_list,
            capture_output=True,
            timeout=60,
            cwd=str(fund_agent_root),
        )
        stdout = proc.stdout.decode("utf-8", errors="replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
        try:
            data = json.loads(stdout)
            results["list_skills"] = {"ok": data.get("ok") is True, "returncode": proc.returncode}
        except json.JSONDecodeError:
            results["list_skills"] = {"ok": False, "returncode": proc.returncode, "error": "output not JSON"}
    except Exception as exc:
        results["list_skills"] = {"ok": False, "error": str(exc)}

    for skill_name in ("fund_analysis", "decision_support"):
        cmd = [sys.executable, str(script_path), "--skill", skill_name, "--explain-input", "--pretty"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                cwd=str(fund_agent_root),
            )
            stdout = proc.stdout.decode("utf-8", errors="replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
            try:
                data = json.loads(stdout)
                results[f"explain_{skill_name}"] = {"ok": data.get("ok") is True, "returncode": proc.returncode}
            except json.JSONDecodeError:
                results[f"explain_{skill_name}"] = {"ok": False, "returncode": proc.returncode, "error": "output not JSON"}
        except Exception as exc:
            results[f"explain_{skill_name}"] = {"ok": False, "error": str(exc)}

    all_ok = all(
        v.get("ok") is True
        for v in results.values()
        if isinstance(v, dict)
    )
    results["ok"] = all_ok
    return results


def _check_windows_path(project: Path, platform: str | None = None) -> str | None:
    current_platform = platform or sys.platform
    path_str = str(project).replace("\\", "/")
    if current_platform == "win32" or "mingw" in current_platform.lower():
        if path_str.startswith("/drives/c") or path_str.startswith("/mnt/c"):
            return (
                f"Warning: path '{project}' uses POSIX-style /drives/c or /mnt/c "
                "which Windows Python may misinterpret as C:\\drives\\c\\... . "
                "Prefer relative paths or C:/Users/... style paths."
            )
    return None


def run_verification(
    *,
    project: Path,
    fund_agent_root: Path,
    skip_runtime: bool = False,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    win_warning = _check_windows_path(project)
    if win_warning:
        warnings.append(win_warning)

    native_skills = _check_native_skills(project)
    if not native_skills["ok"]:
        for slug in native_skills["missing"]:
            errors.append(f"Native skill missing: {slug}")

    plugin_file = _check_plugin_file(project)

    manifest_roles = _check_manifest_roles(fund_agent_root)
    if not manifest_roles.get("ok"):
        err = manifest_roles.get("error", "Manifest role mismatch")
        errors.append(f"Manifest roles: {err}")

    runtime_bridge: dict[str, Any] = {"ok": True, "skipped": skip_runtime}
    if not skip_runtime:
        runtime_bridge = _check_runtime_bridge(fund_agent_root)
        if not runtime_bridge.get("ok"):
            errors.append("Runtime bridge checks failed")

    overall_ok = (
        native_skills["ok"]
        and manifest_roles.get("ok") is True
        and (skip_runtime or runtime_bridge.get("ok") is True)
    )

    return {
        "ok": overall_ok,
        "native_skills": native_skills,
        "plugin_file": plugin_file,
        "manifest_roles": manifest_roles,
        "runtime_bridge": runtime_bridge,
        "warnings": warnings,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_install_discovery.py",
        description=(
            "Automated install discovery verification for fund-agent. "
            "Verifies native OpenCode Agent Skills, plugin file presence, "
            "manifest roles, and optionally runtime bridge readiness. "
            "Does NOT verify fund_agent_skills custom tool registration."
        ),
    )
    parser.add_argument(
        "--project",
        default=".",
        help="Path to the target project where skills are installed (default: .).",
    )
    parser.add_argument(
        "--fund-agent-root",
        default=".",
        help="Path to the fund-agent repository root (default: .).",
    )
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Skip runtime bridge subprocess checks.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON result.",
    )
    args = parser.parse_args(argv)

    project = Path(args.project).resolve()
    fund_agent_root = Path(args.fund_agent_root).resolve()

    result = run_verification(
        project=project,
        fund_agent_root=fund_agent_root,
        skip_runtime=args.skip_runtime,
    )

    if args.json_output:
        indent = 2
        text = json.dumps(result, indent=indent, default=str)
        sys.stdout.write(text + "\n")
    else:
        status = "OK" if result["ok"] else "FAILED"
        print(f"Install discovery verification: {status}")
        print()
        ns = result["native_skills"]
        print(f"Native skills ({ns['skills_dir']}):")
        for slug, found in ns["found"].items():
            mark = "OK" if found else "MISSING"
            print(f"  {slug}: {mark}")
        print(f"  Marker file: {'OK' if ns['marker_exists'] else 'MISSING'}")
        print(f"  Primary skill: {'OK' if ns['primary_ok'] else 'MISSING'}")
        print(f"  Supporting skills: {'OK' if ns['supporting_ok'] else 'INCOMPLETE'}")

        pf = result["plugin_file"]
        print(f"\nPlugin file ({pf['path']}):")
        print(f"  Exists: {pf['exists']}")
        if pf["exists"]:
            print(f"  Valid: {pf['is_valid']}")
        print(f"  Custom tool: {pf['note']}")

        mr = result["manifest_roles"]
        print(f"\nManifest roles:")
        print(f"  Primary: {mr.get('primary_skill', 'N/A')}")
        print(f"  Supporting: {mr.get('supporting_skills', [])}")

        rb = result["runtime_bridge"]
        if rb.get("skipped"):
            print(f"\nRuntime bridge: SKIPPED (--skip-runtime)")
        else:
            print(f"\nRuntime bridge: {'OK' if rb.get('ok') else 'FAILED'}")
            for key, val in rb.items():
                if key in ("ok", "skipped"):
                    continue
                if isinstance(val, dict):
                    mark = "OK" if val.get("ok") else "FAILED"
                    print(f"  {key}: {mark}")

        if result["warnings"]:
            print(f"\nWarnings:")
            for w in result["warnings"]:
                print(f"  - {w}")

        if result["errors"]:
            print(f"\nErrors:")
            for e in result["errors"]:
                print(f"  - {e}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
