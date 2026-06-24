#!/usr/bin/env python3
"""Agent-facing personal run orchestrator.

Runs doctor -> E2E -> health report -> agent context.
Outputs a deterministic evidence package for external agent consumption.
No private data in console output or agent_context files.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.fund_agent_e2e import main as e2e_main
from scripts.fund_agent_private_data_doctor import run_doctor
from src.tools.portfolio.agent_context import (
    build_agent_context,
    render_agent_context_markdown,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _generate_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_json_safe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve_existing_summary(args: argparse.Namespace) -> tuple[dict[str, Any], Path] | None:
    """Try to load an existing e2e_summary from --summary-path or --run-dir.

    Returns (summary_dict, summary_path) if found, else None.
    """
    if args.summary_path:
        sp = Path(args.summary_path)
        if sp.exists():
            summary = _load_json_safe(sp)
            if summary:
                return summary, sp
        return None

    if args.run_dir:
        rd = Path(args.run_dir)
        sp = rd / "e2e_summary.json"
        if sp.exists():
            summary = _load_json_safe(sp)
            if summary:
                return summary, sp
        return None

    return None


def _build_run_manifest(
    *,
    run_id: str,
    doctor_ok: bool,
    e2e_status: str,
    artifacts: dict[str, str],
    skip_akshare: bool,
    skip_news: bool,
    transaction_source: str,
    private_data_configured: bool,
    health: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "fund_agent_run_manifest.v1",
        "run_id": run_id,
        "completed_at": datetime.now().isoformat(),
        "private_data_configured": private_data_configured,
        "doctor_ok": doctor_ok,
        "doctor_status": "ok" if doctor_ok else "issues",
        "e2e_status": e2e_status,
        "health_overall_status": health.get("overall_status", "unavailable"),
        "confidence_level": health.get("confidence_level", "unavailable"),
        "reason_codes": health.get("reason_codes", []),
        "mode": "deterministic" if (skip_akshare and skip_news) else "live",
        "flags": {
            "skip_akshare": skip_akshare,
            "skip_news": skip_news,
            "transaction_source": transaction_source,
        },
        "artifacts": artifacts,
    }


def _print_console_summary(
    *,
    run_id: str,
    health: dict[str, Any],
    run_dir: Path,
    output_dir: Path,
) -> None:
    overall = health.get("overall_status", "unavailable").upper()
    confidence = health.get("confidence_level", "unavailable").upper()
    reason_codes = health.get("reason_codes", [])

    print()
    print("Fund Agent evidence package created.")
    print()
    print(f"Run ID: {run_id}")
    print(f"Status: {overall}")
    print(f"Confidence: {confidence}")
    if reason_codes:
        print(f"Reason codes: {', '.join(reason_codes)}")
    print()
    print("Artifacts:")

    # Relative path from output_dir root
    rel_dir = run_dir.relative_to(output_dir) if run_dir.is_relative_to(output_dir) else run_dir
    for name in ("agent_context.md", "e2e_summary.json", "report.md", "personal_health_report.json"):
        artifact_path = rel_dir / name
        print(f"- {artifact_path}")

    print()
    print("Next:")
    print("Ask your agent to read agent_context.md and continue the analysis.")


def _run_print_only(args: argparse.Namespace) -> int:
    """Handle --health-report-only / --agent-context-only with existing summary."""
    existing = _resolve_existing_summary(args)
    if existing is None:
        return -1  # Signal: no existing summary found, fall through to full pipeline

    e2e_summary, summary_path = existing
    health = _as_dict(e2e_summary.get("personal_health_report"))
    run_id = e2e_summary.get("run_id", summary_path.parent.name)

    if args.health_report_only:
        print(json.dumps(health, indent=2, ensure_ascii=False))
        return 0

    if args.agent_context_only:
        agent_context = build_agent_context(e2e_summary, run_id=run_id)
        agent_context_md = render_agent_context_markdown(agent_context)

        # Optionally write to run-dir if --run-dir is specified
        if args.run_dir:
            rd = Path(args.run_dir)
            _write_json(rd / "agent_context.json", agent_context)
            _write_text(rd / "agent_context.md", agent_context_md)

        print(agent_context_md)
        return 0

    return -1


def run_personal(args: argparse.Namespace) -> int:
    # ── Print-only mode: skip pipeline if summary exists ──────────────
    if args.health_report_only or args.agent_context_only:
        rc = _run_print_only(args)
        if rc >= 0:
            return rc
        # No existing summary found — fall through to full pipeline

    run_id = args.run_id or _generate_run_id()
    private_data = Path(args.private_data_dir) if args.private_data_dir else REPO_ROOT / "private_data"
    output_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "local_reports"
    run_dir = output_dir / run_id

    run_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Doctor ────────────────────────────────────────────────
    print("[step 1] Running private data doctor...")
    doctor_result = run_doctor(private_data)
    doctor_ok = doctor_result.get("ok", False)
    if not doctor_ok:
        print(f"  Doctor status: {doctor_result.get('status', 'unknown')}")
        for err in doctor_result.get("errors", []):
            print(f"  ERROR: {err}")
        # Doctor warnings are non-fatal; continue to E2E

    # ── Step 2: E2E pipeline ──────────────────────────────────────────
    print("[step 2] Running E2E pipeline...")
    e2e_argv = [
        "--run-id", run_id,
        "--private-data-dir", str(private_data),
        "--output-dir", str(run_dir),
        "--transaction-source", args.transaction_source,
    ]
    if args.skip_akshare:
        e2e_argv.append("--skip-akshare")
    if args.skip_news:
        e2e_argv.append("--skip-news")
    if args.dry_run:
        e2e_argv.append("--dry-run")

    e2e_rc = e2e_main(e2e_argv)
    e2e_status = "success" if e2e_rc == 0 else "partial" if e2e_rc == 1 else "failed"

    # ── Step 3: Load summary and build agent context ──────────────────
    e2e_summary_path = run_dir / "e2e_summary.json"
    e2e_summary = _load_json_safe(e2e_summary_path)

    # If E2E wrote summary elsewhere (eval_workspace), try to find it
    if not e2e_summary:
        alt_path = REPO_ROOT / "eval_workspace" / "runs" / run_id / "e2e_summary.json"
        e2e_summary = _load_json_safe(alt_path)
        if e2e_summary and alt_path.exists():
            e2e_summary_path = alt_path

    health = _as_dict(e2e_summary.get("personal_health_report"))

    # Build agent context
    agent_context = build_agent_context(
        e2e_summary,
        run_id=run_id,
    )
    agent_context_md = render_agent_context_markdown(agent_context)

    # ── Step 4: Write artifacts ───────────────────────────────────────
    _write_json(run_dir / "personal_health_report.json", health)
    _write_json(run_dir / "agent_context.json", agent_context)
    _write_text(run_dir / "agent_context.md", agent_context_md)

    # Copy e2e_summary to run_dir if it was written elsewhere
    if e2e_summary and e2e_summary_path != run_dir / "e2e_summary.json":
        _write_json(run_dir / "e2e_summary.json", e2e_summary)

    # Build run manifest
    artifact_paths = {
        "e2e_summary": "e2e_summary.json",
        "personal_health_report": "personal_health_report.json",
        "agent_context_md": "agent_context.md",
        "agent_context_json": "agent_context.json",
    }
    # Check for report.md
    report_path = run_dir / "report.md"
    if not report_path.exists():
        # E2E may have written it elsewhere; check e2e_summary for the path
        report_from_summary = e2e_summary.get("output_report", "")
        if report_from_summary:
            src = Path(report_from_summary)
            if src.exists():
                try:
                    report_content = src.read_text(encoding="utf-8")
                    _write_text(report_path, report_content)
                except OSError:
                    pass
    if report_path.exists():
        artifact_paths["report"] = "report.md"

    manifest = _build_run_manifest(
        run_id=run_id,
        doctor_ok=doctor_ok,
        e2e_status=e2e_status,
        artifacts=artifact_paths,
        skip_akshare=args.skip_akshare,
        skip_news=args.skip_news,
        transaction_source=args.transaction_source,
        private_data_configured=private_data.is_dir(),
        health=health,
    )
    _write_json(run_dir / "run_manifest.json", manifest)

    # ── Step 5: Console output ────────────────────────────────────────
    if args.health_report_only:
        print(json.dumps(health, indent=2, ensure_ascii=False))
        return 0

    if args.agent_context_only:
        print(agent_context_md)
        return 0

    _print_console_summary(
        run_id=run_id,
        health=health,
        run_dir=run_dir,
        output_dir=output_dir,
    )

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fund-agent-personal-run",
        description=(
            "Agent-facing personal run: produces a deterministic evidence "
            "package for external agent consumption. Doctor -> E2E -> "
            "health report -> agent context."
        ),
    )
    parser.add_argument(
        "--private-data-dir", default="",
        help="Private data directory (default: private_data/)",
    )
    parser.add_argument(
        "--output-dir", default="",
        help="Output root directory (default: local_reports/)",
    )
    parser.add_argument(
        "--transaction-source",
        choices=["auto", "alipay", "portfolio_input"],
        default="auto",
        help="Transaction source: auto (default), alipay, or portfolio_input",
    )
    parser.add_argument(
        "--skip-akshare",
        action="store_true",
        default=True,
        help="Skip AkShare-dependent steps (default: True, deterministic mode)",
    )
    parser.add_argument(
        "--no-skip-akshare",
        action="store_false",
        dest="skip_akshare",
        help="Allow AkShare-dependent steps (live mode)",
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        default=True,
        help="Skip news snapshot step (default: True, deterministic mode)",
    )
    parser.add_argument(
        "--no-skip-news",
        action="store_false",
        dest="skip_news",
        help="Allow news snapshot step (live mode)",
    )
    parser.add_argument(
        "--run-id", default="",
        help="Run identifier (default: auto-generated timestamp)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pipeline steps without executing",
    )
    parser.add_argument(
        "--health-report-only",
        action="store_true",
        help=(
            "Print only the personal health report JSON. "
            "With --summary-path or --run-dir, reads existing summary "
            "without running the pipeline."
        ),
    )
    parser.add_argument(
        "--agent-context-only",
        action="store_true",
        help=(
            "Print only the agent context markdown. "
            "With --summary-path or --run-dir, reads existing summary "
            "without running the pipeline."
        ),
    )
    parser.add_argument(
        "--summary-path", default="",
        help="Path to existing e2e_summary.json (skip pipeline when used with print-only flags)",
    )
    parser.add_argument(
        "--run-dir", default="",
        help="Path to existing run directory containing e2e_summary.json (skip pipeline)",
    )
    args = parser.parse_args(argv)
    return run_personal(args)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
