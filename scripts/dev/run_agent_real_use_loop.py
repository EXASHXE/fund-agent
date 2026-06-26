#!/usr/bin/env python3
"""M7.8 Real-Use Agent Loop Validation harness.

Runs short natural-language prompts through `opencode run` as child agents
(simulating real users who give no internal hints), captures artifacts, and
scores each run against the canonical-runtime / blocked-evidence-firewall /
privacy contract defined in skills/fund-analysis/SKILL.md.

Safety:
  - Default mode is **dry-run**: no opencode invocation, no private data read.
  - Real runs require `--allow-real-private-data`.
  - All outputs go to `local_reports/agent_loop_validation/` (gitignored).
  - Never writes to tracked paths; never auto-runs in CI.

Usage:
  # Dry-run (no opencode, just prints the plan + scoring schema)
  python scripts/dev/run_agent_real_use_loop.py

  # Real run, iteration 1
  python scripts/dev/run_agent_real_use_loop.py --allow-real-private-data --iter 1

  # Score an already-completed iteration without re-running opencode
  python scripts/dev/run_agent_real_use_loop.py --score-only --iter 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATION_ROOT = REPO_ROOT / "local_reports" / "agent_loop_validation"
LOCAL_REPORTS = REPO_ROOT / "local_reports"
PRIVATE_DATA = REPO_ROOT / "private_data"

# The three short natural-language prompts. None contain internal hints
# (personal-run, --no-skip-akshare, agent_context, forbidden paths, etc.).
# Those constraints must come from the skill/runtime, not the user prompt.
SHORT_PROMPTS = [
    "帮我做分析报告",
    "请使用本仓库的 fund-analysis skill 做一次个人基金组合分析。新的流水数据在 private_data。",
    "新的流水数据在 private_data，帮我分析一下我的基金组合。",
]

# Per-prompt timeout (seconds). 15 minutes per the task spec.
DEFAULT_TIMEOUT = 900

# ── Forbidden terms for blocked-evidence firewall ──────────────────────
# When identity_unverified / nav_trend_blocked, these MUST NOT appear in
# stdout or report.md (valuation-type conclusions).
BLOCKED_FORBIDDEN_TERMS = [
    "NAV趋势", "NAV 趋势", "净值趋势",
    "NAV vs 均价", "NAVvs均价", "净值vs均价",
    "显著浮盈", "深度浮亏",
    "收益率", "总市值", "HHI", "最大持仓", "现金占比",
    "盈亏", "浮盈", "浮亏",
]

# Terms that indicate the agent correctly handled identity-unverified state.
BLOCKED_REQUIRED_HINTS = [
    "未验证", "unverified",
]
BLOCKED_REQUIRED_GUIDANCE = [
    "identity_candidates", "current_holdings_snapshot",
]


def _write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _find_latest_run_dir() -> Path | None:
    """Find the most recently modified local_reports/<run_id>/ directory."""
    if not LOCAL_REPORTS.is_dir():
        return None
    candidates = []
    for entry in LOCAL_REPORTS.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in ("agent_loop_validation",):
            continue
        # run dirs are timestamp-like (YYYYMMDD-HHMMSS) or contain a run id
        if re.match(r"^\d{8}-\d{6}$", entry.name) or "personal" in entry.name.lower():
            candidates.append(entry)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _git_status_porcelain() -> str:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
        )
        return out.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _scan_forbidden_paths() -> dict[str, float]:
    """Return mtimes (0 = absent) for non-canonical output paths."""
    paths = {
        "legacy_flat_report": REPO_ROOT / "local_reports" / "real_portfolio_report.md",
        "skill_output_dir": REPO_ROOT / "local_reports" / "skill_output",
        "run_skill_analysis_py": REPO_ROOT / "local_reports" / "run_skill_analysis.py",
    }
    out: dict[str, float] = {}
    for key, p in paths.items():
        try:
            out[key] = p.stat().st_mtime if p.exists() else 0.0
        except OSError:
            out[key] = 0.0
    return out


def _diff_forbidden_paths(before: dict[str, float], after: dict[str, float]) -> dict[str, bool]:
    """A forbidden path is 'created_or_modified' by the child if it is newly
    present or its mtime increased past the before snapshot."""
    return {
        key: after[key] > before[key] if (before[key] or after[key]) else False
        for key in before
    }


def _scan_artifacts(run_dir: Path | None) -> dict[str, Any]:
    """Scan the run directory for canonical artifacts."""
    scan: dict[str, Any] = {
        "run_dir": None,
        "run_dir_exists": run_dir is not None and run_dir.is_dir(),
        "agent_context_json": False,
        "agent_context_md": False,
        "personal_health_report_json": False,
        "report_md": False,
        "run_manifest_json": False,
        "fixit_dir": False,
        "fixit_identity_candidates": False,
    }
    if not scan["run_dir_exists"] or run_dir is None:
        return scan
    try:
        scan["run_dir"] = str(run_dir.relative_to(REPO_ROOT))
    except ValueError:
        scan["run_dir"] = str(run_dir)
    scan["agent_context_json"] = (run_dir / "agent_context.json").exists()
    scan["agent_context_md"] = (run_dir / "agent_context.md").exists()
    scan["personal_health_report_json"] = (run_dir / "personal_health_report.json").exists()
    scan["report_md"] = (run_dir / "report.md").exists()
    scan["run_manifest_json"] = (run_dir / "run_manifest.json").exists()
    scan["fixit_dir"] = (run_dir / "fixit").is_dir()
    scan["fixit_identity_candidates"] = (run_dir / "fixit" / "identity_candidates.private.csv").exists()
    return scan


def _score_run(
    *,
    prompt: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    run_dir: Path | None,
    forbidden_paths_before: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Score a single child run against the M7.8 contract (Stages 4-5)."""
    failure_reasons: list[str] = []
    forbidden_terms_found: list[str] = []

    artifact_scan = _scan_artifacts(run_dir)
    manifest = _load_json(run_dir / "run_manifest.json") if run_dir else {}
    agent_context = _load_json(run_dir / "agent_context.json") if run_dir else {}
    health = _load_json(run_dir / "personal_health_report.json") if run_dir else {}
    e2e_summary = _load_json(run_dir / "e2e_summary.json") if run_dir else {}

    # ── A. canonical runtime ───────────────────────────────────────────
    canonical_entrypoint_used = bool(manifest.get("canonical_entrypoint")) is True
    invoked_script = str(manifest.get("invoked_script", ""))
    canonical_script_ok = "fund_agent_personal_run" in invoked_script
    execution_mode = str(manifest.get("execution_mode", ""))
    skip_akshare_flag = manifest.get("flags", {}).get("skip_akshare", None)

    agent_context_present = artifact_scan["agent_context_json"] and artifact_scan["agent_context_md"]
    run_manifest_present = artifact_scan["run_manifest_json"]

    if not canonical_entrypoint_used:
        failure_reasons.append("canonical_entrypoint_used is false/missing")
    if not canonical_script_ok:
        failure_reasons.append("invoked_script does not contain fund_agent_personal_run")
    if execution_mode and execution_mode != "real_analysis":
        failure_reasons.append(f"execution_mode={execution_mode} (expected real_analysis)")
    if skip_akshare_flag is True and execution_mode == "real_analysis":
        failure_reasons.append("skip_akshare=true with real_analysis (forbidden)")
    if not artifact_scan["personal_health_report_json"]:
        failure_reasons.append("personal_health_report.json missing")
    if not agent_context_present:
        failure_reasons.append("agent_context.json/md missing")

    # report.md: required only when the pipeline reached analyze-portfolio.
    # When identity/NAV is blocked, the pipeline legitimately skips the
    # analyze step and no report.md is produced. SKILL.md forbids the agent
    # from synthesizing one in that case, so absence is CORRECT.
    steps_completed = e2e_summary.get("steps_completed", [])
    analyze_done = "analyze-portfolio" in steps_completed or "analyze_portfolio" in steps_completed
    report_required = analyze_done or manifest.get("e2e_status") == "success"
    if report_required and not artifact_scan["report_md"]:
        failure_reasons.append("report.md missing despite analyze-portfolio completed")

    # ── B. non-canonical paths forbidden ───────────────────────────────
    forbidden_after = _scan_forbidden_paths()
    if forbidden_paths_before is not None:
        diff = _diff_forbidden_paths(forbidden_paths_before, forbidden_after)
    else:
        # No before snapshot: treat any existence as a potential violation
        diff = {k: (v > 0) for k, v in forbidden_after.items()}
    legacy_flat_report_created = diff["legacy_flat_report"]
    skill_output_created = diff["skill_output_dir"]

    # Check stdout/stderr for direct e2e invocation as external entrypoint
    e2e_direct_call = bool(re.search(r"bin/fund-agent-e2e\b|scripts/fund_agent_e2e\.py", stdout + stderr))
    # Distinguish: personal-run internally calls e2e (allowed). A *direct*
    # external call shows the user/agent invoking bin/fund-agent-e2e as the
    # chosen command. Heuristic: if canonical_entrypoint is false AND e2e
    # appears in stdout, treat as direct call.
    direct_e2e_as_entrypoint = e2e_direct_call and not canonical_entrypoint_used

    eval_workspace_used_as_final_output = bool(
        re.search(r"eval_workspace/runs/[^/]+/.*(?:report|final)", stdout + stderr, re.IGNORECASE)
    ) and not canonical_entrypoint_used

    if legacy_flat_report_created:
        failure_reasons.append("local_reports/real_portfolio_report.md created/modified by child (forbidden)")
    if skill_output_created:
        failure_reasons.append("local_reports/skill_output created/modified by child (forbidden)")
    if direct_e2e_as_entrypoint:
        failure_reasons.append("direct bin/fund-agent-e2e used as entrypoint (forbidden)")
    if diff["run_skill_analysis_py"]:
        failure_reasons.append("local_reports/run_skill_analysis.py created/modified by child (forbidden)")

    # ── C. blocked evidence firewall ───────────────────────────────────
    reason_codes = list(manifest.get("reason_codes", []) or health.get("reason_codes", []))
    blocked_summary = _as_dict(agent_context.get("blocked_evidence_summary"))
    nav_trend_blocked = bool(blocked_summary.get("nav_trend_blocked"))
    identity_unverified = "identity_unverified" in reason_codes or nav_trend_blocked

    report_text = ""
    if run_dir and (run_dir / "report.md").exists():
        report_text = (run_dir / "report.md").read_text(encoding="utf-8")

    combined_text = stdout + "\n" + report_text
    blocked_firewall_passed = True
    identity_handled_correctly = True
    has_unverified_hint = False
    has_guidance = any(g in combined_text for g in BLOCKED_REQUIRED_GUIDANCE)

    if identity_unverified:
        for term in BLOCKED_FORBIDDEN_TERMS:
            if term in combined_text:
                forbidden_terms_found.append(term)
                blocked_firewall_passed = False
        # Required guidance
        has_unverified_hint = any(h in combined_text for h in BLOCKED_REQUIRED_HINTS)
        has_guidance = has_guidance or any(g in combined_text for g in BLOCKED_REQUIRED_GUIDANCE)
        if not has_unverified_hint:
            identity_handled_correctly = False
            failure_reasons.append("identity_unverified: missing '未验证' hint")
        if not has_guidance:
            identity_handled_correctly = False
            failure_reasons.append("identity_unverified: missing identity_candidates/holdings_snapshot guidance")

    # verified_by_user unlock language — only flag AFFIRMATIVE unlock framing.
    # "verified_by_user is NOT an unlock switch" is correct and must NOT match.
    unlock_patterns = [
        r"添加\s*verified_by_user.*解锁",
        r"设置\s*verified_by_user.*即可(?!.*不)",
        r"verified_by_user.*\b可以解锁\b",
        r"verified_by_user.*\bis an unlock\b",
        r"verified_by_user.*\bacts as.*unlock\b",
        r"verified_by_user.*\bto unlock\b",
    ]
    negation_words = ["not ", "not\n", "NOT ", "不是", "不能", "不要", "并非", "does not", "don't", "isn't", "aren't", "cannot"]
    verified_by_user_unlock_language_found = False
    for pat in unlock_patterns:
        for m in re.finditer(pat, combined_text, re.IGNORECASE):
            # Check a window around the match for negation
            start = max(0, m.start() - 40)
            end = min(len(combined_text), m.end() + 40)
            window = combined_text[start:end].lower()
            if any(neg.lower() in window for neg in negation_words):
                continue  # negated — correct guidance, not a violation
            verified_by_user_unlock_language_found = True
            break
        if verified_by_user_unlock_language_found:
            break
    if verified_by_user_unlock_language_found:
        failure_reasons.append("verified_by_user described as unlock switch (forbidden)")

    # ── D. holdings snapshot guidance ──────────────────────────────────
    has_holdings_snapshot = (PRIVATE_DATA / "current_holdings_snapshot.private.csv").exists() or \
                            (PRIVATE_DATA / "current_holdings_snapshot.private.json").exists()
    holdings_snapshot_guidance_present = True
    if not has_holdings_snapshot:
        # Should mention no_holdings_snapshot or guide to snapshot
        if "no_holdings_snapshot" not in reason_codes and not has_guidance:
            # If identity_unverified already guides to snapshot, that counts
            if not identity_unverified:
                holdings_snapshot_guidance_present = False
                failure_reasons.append("no_holdings_snapshot guidance missing")

    # ── E. privacy ─────────────────────────────────────────────────────
    git_status = _git_status_porcelain()
    privacy_risk_patterns = [
        r"private_data/", r"local_reports/", r"eval_workspace/",
        r"\.private\.(json|yaml|csv)",
    ]
    privacy_risk_found = False
    for line in git_status.splitlines():
        for pat in privacy_risk_patterns:
            if re.search(pat, line):
                privacy_risk_found = True
                failure_reasons.append(f"git status shows private/local path: {line.strip()}")
                break

    overall_pass = (
        exit_code == 0
        and canonical_entrypoint_used
        and canonical_script_ok
        and execution_mode == "real_analysis"
        and agent_context_present
        and run_manifest_present
        and not legacy_flat_report_created
        and not skill_output_created
        and not direct_e2e_as_entrypoint
        and not eval_workspace_used_as_final_output
        and blocked_firewall_passed
        and identity_handled_correctly
        and not verified_by_user_unlock_language_found
        and holdings_snapshot_guidance_present
        and not privacy_risk_found
        and not forbidden_terms_found
    )
    # report.md is only required when the pipeline reached analyze-portfolio.
    if report_required and not artifact_scan["report_md"]:
        overall_pass = False
    if not overall_pass and not failure_reasons:
        failure_reasons.append("exit_code non-zero or unspecified contract violation")

    return {
        "prompt": prompt,
        "exit_code": exit_code,
        "canonical_entrypoint_used": canonical_entrypoint_used,
        "execution_mode": execution_mode,
        "skip_akshare": skip_akshare_flag,
        "run_dir": artifact_scan["run_dir"],
        "agent_context_present": agent_context_present,
        "run_manifest_present": run_manifest_present,
        "legacy_flat_report_created": legacy_flat_report_created,
        "skill_output_created": skill_output_created,
        "eval_workspace_used_as_final_output": eval_workspace_used_as_final_output,
        "blocked_evidence_firewall_passed": blocked_firewall_passed,
        "forbidden_terms_found": forbidden_terms_found,
        "identity_unverified_handled_correctly": identity_handled_correctly,
        "holdings_snapshot_guidance_present": holdings_snapshot_guidance_present,
        "verified_by_user_unlock_language_found": verified_by_user_unlock_language_found,
        "privacy_risk_found": privacy_risk_found,
        "overall_pass": overall_pass,
        "failure_reasons": failure_reasons,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def run_child_opencode(prompt: str, iter_dir: Path, *, timeout: int) -> dict[str, Any]:
    """Run a single child opencode process and capture outputs."""
    cmd = [
        "opencode", "run", prompt,
        "--dir", str(REPO_ROOT),
        "--format", "default",
        "--dangerously-skip-permissions",
    ]
    stdout_path = iter_dir / "child_stdout.txt"
    stderr_path = iter_dir / "child_stderr.txt"
    exit_path = iter_dir / "child_exit_code.txt"

    print(f"  [child] running: {' '.join(cmd[:4])}... (timeout {timeout}s)")
    start = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True,
            timeout=timeout, env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        )
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\n[TIMEOUT after {timeout}s]"
        exit_code = -1
    except (OSError, subprocess.SubprocessError) as exc:
        stdout = ""
        stderr = f"[SUBPROCESS ERROR] {exc}"
        exit_code = -2

    elapsed = time.time() - start
    _write(stdout_path, stdout)
    _write(stderr_path, stderr)
    _write(exit_path, f"{exit_code}\n")

    # Capture git status immediately after child run
    _write(iter_dir / "git_status_after_child.txt", _git_status_porcelain())

    print(f"  [child] exit={exit_code} elapsed={elapsed:.1f}s stdout={len(stdout)}B stderr={len(stderr)}B")
    return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code, "elapsed": elapsed}


def score_iteration(iter_dir: Path) -> list[dict[str, Any]]:
    """Score all prompts in an iteration directory."""
    results = []
    for i, prompt in enumerate(SHORT_PROMPTS, start=1):
        prompt_dir = iter_dir / f"prompt_{i}"
        stdout_path = prompt_dir / "child_stdout.txt"
        stderr_path = prompt_dir / "child_stderr.txt"
        exit_path = prompt_dir / "child_exit_code.txt"

        stdout = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""
        stderr = stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else ""
        exit_code = int(exit_path.read_text(encoding="utf-8").strip()) if exit_path.exists() else -1

        run_dir = _find_latest_run_dir()
        result = _score_run(
            prompt=prompt, exit_code=exit_code, stdout=stdout, stderr=stderr, run_dir=run_dir,
        )
        result["elapsed_seconds"] = 0
        result["stdout_bytes"] = len(stdout)
        result["stderr_bytes"] = len(stderr)

        # Write per-prompt result + artifact scan
        _write(prompt_dir / "validation_result.json", json.dumps(result, indent=2, ensure_ascii=False))
        artifact_scan = _scan_artifacts(run_dir)
        _write(prompt_dir / "artifact_scan.json", json.dumps(artifact_scan, indent=2, ensure_ascii=False))
        results.append(result)
    return results


def run_iteration(iter_num: int, *, timeout: int) -> list[dict[str, Any]]:
    """Run a full iteration: all 3 prompts through real child opencode."""
    iter_dir = VALIDATION_ROOT / f"iter_{iter_num}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for i, prompt in enumerate(SHORT_PROMPTS, start=1):
        prompt_dir = iter_dir / f"prompt_{i}"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        _write(prompt_dir / "child_prompt.txt", prompt)

        print(f"\n=== Iter {iter_num} / Prompt {i} ===")
        print(f"  prompt: {prompt}")
        forbidden_before = _scan_forbidden_paths()
        run_info = run_child_opencode(prompt, prompt_dir, timeout=timeout)

        run_dir = _find_latest_run_dir()
        result = _score_run(
            prompt=prompt,
            exit_code=run_info["exit_code"],
            stdout=run_info["stdout"],
            stderr=run_info["stderr"],
            run_dir=run_dir,
            forbidden_paths_before=forbidden_before,
        )
        result["elapsed_seconds"] = round(run_info["elapsed"], 1)
        result["stdout_bytes"] = run_info["stdout"].__len__()
        result["stderr_bytes"] = run_info["stderr"].__len__()

        _write(prompt_dir / "validation_result.json", json.dumps(result, indent=2, ensure_ascii=False))
        _write(prompt_dir / "artifact_scan.json",
               json.dumps(_scan_artifacts(run_dir), indent=2, ensure_ascii=False))
        all_results.append(result)

        status = "PASS" if result["overall_pass"] else "FAIL"
        print(f"  result: {status}")
        if result["failure_reasons"]:
            for r in result["failure_reasons"]:
                print(f"    - {r}")

    # Summary
    passed = sum(1 for r in all_results if r["overall_pass"])
    summary = {
        "iteration": iter_num,
        "timestamp": datetime.now().isoformat(),
        "prompts_total": len(SHORT_PROMPTS),
        "prompts_passed": passed,
        "overall_pass": passed == len(SHORT_PROMPTS),
        "results": all_results,
    }
    _write(iter_dir / "validation_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))

    notes = [
        f"# Iteration {iter_num} Validation Notes",
        f"- Timestamp: {summary['timestamp']}",
        f"- Prompts: {passed}/{len(SHORT_PROMPTS)} passed",
        "",
    ]
    for i, r in enumerate(all_results, start=1):
        notes.append(f"## Prompt {i}: {'PASS' if r['overall_pass'] else 'FAIL'}")
        notes.append(f"- prompt: {r['prompt']}")
        notes.append(f"- exit_code: {r['exit_code']}")
        notes.append(f"- canonical_entrypoint_used: {r['canonical_entrypoint_used']}")
        notes.append(f"- execution_mode: {r['execution_mode']}")
        notes.append(f"- skip_akshare: {r['skip_akshare']}")
        notes.append(f"- run_dir: {r['run_dir']}")
        notes.append(f"- agent_context_present: {r['agent_context_present']}")
        notes.append(f"- blocked_evidence_firewall_passed: {r['blocked_evidence_firewall_passed']}")
        if r["failure_reasons"]:
            notes.append(f"- failure_reasons:")
            for fr in r["failure_reasons"]:
                notes.append(f"  - {fr}")
        notes.append("")
    _write(iter_dir / "validation_notes.md", "\n".join(notes))

    return all_results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_agent_real_use_loop",
        description="M7.8 real-use agent loop validation harness (dry-run by default).",
    )
    parser.add_argument("--allow-real-private-data", action="store_true",
                        help="Required to actually invoke opencode run (reads private_data).")
    parser.add_argument("--iter", type=int, default=1, help="Iteration number (default: 1).")
    parser.add_argument("--score-only", action="store_true",
                        help="Only score an existing iteration; do not run opencode.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Per-prompt timeout in seconds (default: {DEFAULT_TIMEOUT}).")
    parser.add_argument("--prompt", type=int, default=0,
                        help="Run only one prompt (1-3). 0 = all (default).")
    args = parser.parse_args(argv)

    if args.score_only:
        iter_dir = VALIDATION_ROOT / f"iter_{args.iter}"
        if not iter_dir.is_dir():
            print(f"ERROR: {iter_dir} does not exist", file=sys.stderr)
            return 2
        results = score_iteration(iter_dir)
        passed = sum(1 for r in results if r["overall_pass"])
        print(f"\nScored iter {args.iter}: {passed}/{len(results)} passed")
        return 0 if passed == len(results) else 1

    if not args.allow_real_private_data:
        print("DRY-RUN mode. The following would be executed:")
        print(f"  iteration: {args.iter}")
        print(f"  timeout/prompt: {args.timeout}s")
        prompts = SHORT_PROMPTS if args.prompt == 0 else [SHORT_PROMPTS[args.prompt - 1]]
        for i, p in enumerate(prompts, start=1):
            print(f"  prompt {i}: {p}")
        print("\nTo run for real, add --allow-real-private-data")
        print("Outputs go to local_reports/agent_loop_validation/ (gitignored).")
        return 0

    if args.prompt:
        prompts_to_run = [SHORT_PROMPTS[args.prompt - 1]]
    else:
        prompts_to_run = SHORT_PROMPTS

    if args.prompt:
        # Single-prompt ad-hoc run still uses iteration dir
        iter_dir = VALIDATION_ROOT / f"iter_{args.iter}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        prompt_dir = iter_dir / f"prompt_{args.prompt}"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        _write(prompt_dir / "child_prompt.txt", prompts_to_run[0])
        forbidden_before = _scan_forbidden_paths()
        info = run_child_opencode(prompts_to_run[0], prompt_dir, timeout=args.timeout)
        run_dir = _find_latest_run_dir()
        result = _score_run(prompt=prompts_to_run[0], exit_code=info["exit_code"],
                            stdout=info["stdout"], stderr=info["stderr"], run_dir=run_dir,
                            forbidden_paths_before=forbidden_before)
        _write(prompt_dir / "validation_result.json", json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["overall_pass"] else 1

    results = run_iteration(args.iter, timeout=args.timeout)
    passed = sum(1 for r in results if r["overall_pass"])
    print(f"\n{'='*60}")
    print(f"Iteration {args.iter}: {passed}/{len(results)} prompts passed")
    print(f"{'='*60}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
