"""Host acceptance doctor — deterministic local readiness check.

Metadata-only and local-only. No provider SDK imports, no network calls,
no runtime skill business logic changes. May invoke existing metadata loaders
and optionally subprocess-smoke the runtime bridge.

Output is JSON-serializable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.skillpack.loader import load_skillpack_manifest
from src.skillpack.resources import package_root, resolve_resource_path

EXPECTED_RUNTIME_SKILLS = frozenset({
    "fund_analysis",
    "news_research",
    "sentiment_analysis",
    "thesis_generation",
    "decision_support",
})

RUNTIME_TO_DOC_SLUG = {
    "fund_analysis": "fund-analysis",
    "news_research": "news-research",
    "sentiment_analysis": "sentiment-analysis",
    "thesis_generation": "thesis-generation",
    "decision_support": "decision-support",
}

REQUIRED_SKILLPACK_YAMLS = [
    "capabilities.yaml",
    "tools.yaml",
    "input-contracts.yaml",
    "artifact-contracts.yaml",
    "decision-contracts.yaml",
    "thesis-contracts.yaml",
]

REQUIRED_CONTRACT_DOCS = [
    "docs/contracts/skill-output-contract.v1.md",
    "docs/contracts/fund-analysis-input-contract.v1.md",
    "docs/contracts/fund-analysis-artifacts.v1.md",
    "docs/contracts/decision-support-contract.v1.md",
    "docs/contracts/thesis-generation-contract.v1.md",
    "docs/contracts/report-output-contract.v1.md",
]

REQUIRED_EXAMPLE_DIRS = [
    "examples/scenarios",
    "examples/decision_support",
    "examples/thesis_generation",
]

SMOKE_METADATA_COMMANDS = [
    ["--list-skills"],
    ["--skill", "fund_analysis", "--explain-input"],
    ["--skill", "decision_support", "--output-schema"],
    ["--skill", "thesis_generation", "--output-schema"],
]

SMOKE_FIXTURE_RUNS = [
    ("fund_analysis", "examples/scenarios/cn_fund_7d_redemption_fee.json"),
    ("decision_support", "examples/decision_support/single_active_buy_with_evidence.json"),
    ("thesis_generation", "examples/thesis_generation/evidence_graph_balanced_thesis.json"),
]


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


def _run_subprocess(
    cmd: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 60,
) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
        stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else (result.stdout or "")
        stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else (result.stderr or "")
        return result.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as exc:
        return -2, "", str(exc)


def run_doctor(
    *,
    manifest_path: str = "skillpack/fund-agent.skillpack.yaml",
    include_smoke: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    root = package_root()

    resolved_manifest = resolve_resource_path(manifest_path)

    # 1. Manifest resolves and loads
    manifest = None
    try:
        manifest = load_skillpack_manifest(manifest_path)
        checks.append(_check(
            "manifest.load",
            "OK",
            "Manifest loaded successfully",
            {"path": str(resolved_manifest)},
        ))
    except Exception as exc:
        checks.append(_check(
            "manifest.load",
            "FAILED",
            f"Failed to load manifest: {exc}",
            {"path": str(resolved_manifest), "exception": str(exc)},
        ))
        errors.append(f"manifest.load: {exc}")

    # 2. Manifest lists exactly the current five runtime skills
    if manifest is not None:
        manifest_ids = frozenset(s.name for s in manifest.skills)
        if manifest_ids == EXPECTED_RUNTIME_SKILLS:
            checks.append(_check(
                "manifest.runtime_skills",
                "OK",
                f"Manifest lists exactly {len(EXPECTED_RUNTIME_SKILLS)} expected runtime skills",
                {"skills": sorted(manifest_ids)},
            ))
        else:
            missing = EXPECTED_RUNTIME_SKILLS - manifest_ids
            extra = manifest_ids - EXPECTED_RUNTIME_SKILLS
            msg = f"Manifest skill mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
            checks.append(_check("manifest.runtime_skills", "FAILED", msg, {"missing": sorted(missing), "extra": sorted(extra)}))
            errors.append(msg)

    # 3. Each manifest runtime path resolves
    if manifest is not None:
        for spec in manifest.skills:
            check_id = f"runtime.resolve.{spec.name}"
            try:
                from src.skillpack.loader import resolve_runtime
                resolve_runtime(spec.runtime)
                checks.append(_check(check_id, "OK", f"Runtime path resolves: {spec.runtime}", {"runtime": spec.runtime}))
            except Exception as exc:
                checks.append(_check(check_id, "FAILED", f"Runtime path failed: {spec.runtime}: {exc}", {"runtime": spec.runtime, "exception": str(exc)}))
                errors.append(f"{check_id}: {exc}")

    # 4. Skill docs exist for every manifest skill
    if manifest is not None:
        for spec in manifest.skills:
            slug = RUNTIME_TO_DOC_SLUG.get(spec.name, spec.name)
            doc_path = root / "skills" / slug / "SKILL.md"
            check_id = f"skill_doc.exists.{spec.name}"
            if doc_path.exists():
                checks.append(_check(check_id, "OK", f"Skill doc exists: skills/{slug}/SKILL.md", {"path": str(doc_path)}))
            else:
                checks.append(_check(check_id, "FAILED", f"Skill doc missing: skills/{slug}/SKILL.md", {"path": str(doc_path)}))
                errors.append(f"Skill doc missing: skills/{slug}/SKILL.md")

    # 5. Required skillpack YAMLs exist
    for filename in REQUIRED_SKILLPACK_YAMLS:
        check_id = f"skillpack_yaml.exists.{filename}"
        yaml_path = resolve_resource_path(Path("skillpack") / filename)
        if yaml_path.exists():
            checks.append(_check(check_id, "OK", f"Skillpack YAML exists: {filename}", {"path": str(yaml_path)}))
        else:
            checks.append(_check(check_id, "FAILED", f"Skillpack YAML missing: {filename}", {"path": str(yaml_path)}))
            errors.append(f"Skillpack YAML missing: {filename}")

    # 6. Required contract docs exist
    for doc_rel in REQUIRED_CONTRACT_DOCS:
        check_id = f"contract_doc.exists.{Path(doc_rel).name}"
        doc_path = resolve_resource_path(doc_rel)
        if doc_path.exists():
            checks.append(_check(check_id, "OK", f"Contract doc exists: {doc_rel}", {"path": str(doc_path)}))
        else:
            checks.append(_check(check_id, "FAILED", f"Contract doc missing: {doc_rel}", {"path": str(doc_path)}))
            errors.append(f"Contract doc missing: {doc_rel}")

    # 7. Required example fixture directories exist
    for dir_rel in REQUIRED_EXAMPLE_DIRS:
        check_id = f"example_dir.exists.{Path(dir_rel).name}"
        dir_path = resolve_resource_path(dir_rel)
        if dir_path.is_dir():
            checks.append(_check(check_id, "OK", f"Example directory exists: {dir_rel}", {"path": str(dir_path)}))
        else:
            checks.append(_check(check_id, "FAILED", f"Example directory missing: {dir_rel}", {"path": str(dir_path)}))
            errors.append(f"Example directory missing: {dir_rel}")

    # 8. Smoke: runtime bridge metadata commands
    if include_smoke:
        script_path = root / "scripts" / "run_skill.py"
        for cmd_args in SMOKE_METADATA_COMMANDS:
            label = " ".join(cmd_args)
            check_id = f"smoke.metadata.{label}"
            cmd = [sys.executable, str(script_path)] + cmd_args + ["--pretty"]
            rc, stdout, stderr = _run_subprocess(cmd, cwd=str(root))
            if rc == 0:
                try:
                    data = json.loads(stdout)
                    if data.get("ok") is True:
                        checks.append(_check(check_id, "OK", f"Smoke metadata OK: {label}", {"returncode": rc}))
                    else:
                        checks.append(_check(check_id, "FAILED", f"Smoke metadata returned ok=false: {label}", {"returncode": rc, "ok": data.get("ok")}))
                        errors.append(f"Smoke metadata ok=false: {label}")
                except json.JSONDecodeError:
                    checks.append(_check(check_id, "FAILED", f"Smoke metadata output not JSON: {label}", {"returncode": rc}))
                    errors.append(f"Smoke metadata not JSON: {label}")
            else:
                checks.append(_check(check_id, "FAILED", f"Smoke metadata failed (rc={rc}): {label}", {"returncode": rc, "stderr": stderr[:200]}))
                errors.append(f"Smoke metadata failed: {label}")

    # 9. Smoke: fixture runs
    if include_smoke:
        script_path = root / "scripts" / "run_skill.py"
        for skill, fixture_rel in SMOKE_FIXTURE_RUNS:
            check_id = f"smoke.fixture.{skill}"
            fixture_path = resolve_resource_path(fixture_rel)
            cmd = [sys.executable, str(script_path), "--skill", skill, "--input", str(fixture_path)]
            rc, stdout, stderr = _run_subprocess(cmd, cwd=str(root))
            if rc == 0:
                try:
                    data = json.loads(stdout)
                    if data.get("ok") is True:
                        checks.append(_check(check_id, "OK", f"Smoke fixture OK: {skill}", {"returncode": rc, "fixture": fixture_rel}))
                    else:
                        checks.append(_check(check_id, "FAILED", f"Smoke fixture returned ok=false: {skill}", {"returncode": rc, "fixture": fixture_rel}))
                        errors.append(f"Smoke fixture ok=false: {skill}")
                except json.JSONDecodeError:
                    checks.append(_check(check_id, "FAILED", f"Smoke fixture output not JSON: {skill}", {"returncode": rc, "fixture": fixture_rel}))
                    errors.append(f"Smoke fixture not JSON: {skill}")
            else:
                checks.append(_check(check_id, "FAILED", f"Smoke fixture failed (rc={rc}): {skill}", {"returncode": rc, "fixture": fixture_rel, "stderr": stderr[:200]}))
                errors.append(f"Smoke fixture failed: {skill}")

    has_failed = any(c["status"] == "FAILED" for c in checks)
    if has_failed:
        status = "FAILED"
        ok = False
    elif any(c["status"] == "SKIPPED" for c in checks):
        status = "PARTIAL"
        ok = True
    else:
        status = "OK"
        ok = True

    return {
        "ok": ok,
        "status": status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "metadata": {
            "manifest_path": str(resolved_manifest),
            "package_root": str(root),
            "resource_resolution": "cwd_then_package_root",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fund-agent-doctor",
        description=(
            "fund-agent host acceptance doctor: deterministic local readiness "
            "check. No network calls, no provider SDKs, no API keys required."
        ),
    )
    parser.add_argument(
        "--manifest",
        default="skillpack/fund-agent.skillpack.yaml",
        help="Path to the skillpack manifest YAML.",
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip runtime bridge subprocess smoke tests.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output.",
    )
    args = parser.parse_args(argv)

    result = run_doctor(
        manifest_path=args.manifest,
        include_smoke=not args.no_smoke,
    )

    indent = 2 if args.pretty else None
    separators = None if args.pretty else (",", ":")
    text = json.dumps(result, indent=indent, separators=separators, default=str)
    sys.stdout.write(text + "\n")
    sys.stdout.flush()

    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
