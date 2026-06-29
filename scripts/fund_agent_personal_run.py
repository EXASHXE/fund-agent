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
from src.tools.portfolio.current_holdings_snapshot import load_current_holdings_snapshot
from src.tools.portfolio.holdings_snapshot_overlay import apply_holdings_snapshot_overlay

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


def _load_holdings_snapshot(args: argparse.Namespace, private_data: Path) -> dict[str, Any] | None:
    """Load holdings snapshot from explicit path or auto-detect from private_data."""
    snapshot_path = None

    # Explicit path takes priority
    if args.holdings_snapshot:
        snapshot_path = Path(args.holdings_snapshot)
        if not snapshot_path.exists():
            print(f"  WARNING: --holdings-snapshot path not found: {snapshot_path}", file=sys.stderr)
            return None
    else:
        # Auto-detect
        for name in ("current_holdings_snapshot.private.csv", "current_holdings_snapshot.private.json"):
            candidate = private_data / name
            if candidate.exists():
                snapshot_path = candidate
                break

    if snapshot_path is None:
        return None

    try:
        return load_current_holdings_snapshot(snapshot_path)
    except (ValueError, FileNotFoundError) as exc:
        print(f"  WARNING: Failed to load holdings snapshot: {exc}", file=sys.stderr)
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _summary_step_completed(summary: dict[str, Any], step_id: str) -> bool:
    steps = summary.get("steps_completed", [])
    return isinstance(steps, list) and step_id in steps


def _summary_report_generated(summary: dict[str, Any]) -> bool:
    """Return whether the E2E summary proves a report came from this run."""
    outputs = _as_dict(summary.get("outputs"))
    return _summary_step_completed(summary, "analyze-portfolio") and bool(
        outputs.get("report") or summary.get("output_report")
    )


def _copy_identity_template_to_private_data(run_dir: Path, private_data: Path) -> bool:
    """Copy the generated fill-in template into private_data without overwriting."""
    source = run_dir / "fund_identity_overrides.template.private.yaml"
    final_overrides = private_data / "fund_identity_overrides.private.yaml"
    target = private_data / "fund_identity_overrides.template.private.yaml"
    if not source.exists() or final_overrides.exists() or target.exists():
        return False
    try:
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        return False
    return True


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


def _resolve_skip_akshare(args: argparse.Namespace) -> bool:
    """Determine skip_akshare based on execution_mode and explicit flags.

    Rules:
    - real_analysis: skip_akshare=False (live NAV required).
      If user explicitly passes --skip-akshare, fail fast.
    - offline_debug: skip_akshare=True (deterministic, no live data).
    """
    execution_mode = getattr(args, "execution_mode", "real_analysis")

    if execution_mode == "real_analysis":
        if args._explicit_skip_akshare:
            print(
                "ERROR: --skip-akshare is not allowed with --execution-mode real_analysis.\n"
                "For offline/deterministic mode, use --execution-mode offline_debug.",
                file=sys.stderr,
            )
            return True  # Will be caught by caller
        return False  # real_analysis → no skip → live NAV
    else:
        # offline_debug
        return True  # skip akshare


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
    execution_mode: str = "real_analysis",
    enable_name_search: bool = False,
    e2e_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # M7.12+M7.13: Extract name search diagnostics from e2e_summary
    name_search_diag: dict[str, Any] = {
        "name_search_enabled": enable_name_search,
        "name_search_provider_injected": False,
    }
    if e2e_summary:
        identity = _as_dict(e2e_summary.get("identity_resolution", {}))
        name_search_diag["name_search_provider_injected"] = bool(
            e2e_summary.get("name_search_provider_diagnostics", {})
        )
        name_search_diag["name_search_requested_count"] = identity.get(
            "name_search_requested_count",
            sum(1 for r in identity.get("resolutions", [])
                if r.get("name_search_candidates") or r.get("resolution_source") == "name_search_auto_verified"),
        )
        name_search_diag["name_search_candidate_count"] = identity.get(
            "name_search_candidate_count", 0)
        name_search_diag["name_search_unique_high_confidence_count"] = identity.get(
            "name_search_unique_high_confidence_count", 0)
        name_search_diag["name_search_ambiguous_count"] = identity.get(
            "name_search_ambiguous_count", 0)
        name_search_diag["name_search_no_result_count"] = identity.get(
            "name_search_no_result_count", 0)
        name_search_diag["name_search_promoted_provider_verified_count"] = identity.get(
            "name_search_promoted_provider_verified_count", 0)
        # Provider diagnostics
        provider_diag = e2e_summary.get("name_search_provider_diagnostics", {})
        if provider_diag:
            name_search_diag["name_search_provider_status"] = provider_diag.get(
                "name_search_provider_status", "unknown")
            name_search_diag["name_search_provider_last_error"] = provider_diag.get(
                "name_search_provider_last_error", "")
        # M7.13: Provider chain diagnostics
        if provider_diag.get("provider_chain_enabled"):
            name_search_diag["provider_chain_enabled"] = True
            name_search_diag["providers_attempted"] = provider_diag.get("providers_attempted", [])
            name_search_diag["providers_succeeded"] = provider_diag.get("providers_succeeded", [])
            name_search_diag["providers_failed"] = provider_diag.get("providers_failed", [])
            name_search_diag["fallback_used"] = provider_diag.get("fallback_used", False)
        # M7.13: Local cache diagnostics
        local_cache_diag = e2e_summary.get("local_cache_diagnostics", {})
        if local_cache_diag:
            name_search_diag["local_cache_present"] = local_cache_diag.get(
                "name_search_provider_status", "") != "cache_missing"
            name_search_diag["local_cache_candidate_count"] = local_cache_diag.get(
                "name_search_provider_entry_count", 0)
            name_search_diag["network_provider_status"] = "network_error" if any(
                p in provider_diag.get("providers_failed", [])
                for p in provider_diag.get("providers_attempted", [])
                if "akshare" in p.lower() or "network" in p.lower()
            ) else "available"

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
        "execution_mode": execution_mode,
        "flags": {
            "skip_akshare": skip_akshare,
            "skip_news": skip_news,
            "transaction_source": transaction_source,
            "enable_name_search": enable_name_search,
        },
        "name_search_diagnostics": name_search_diag,
        "canonical_entrypoint": True,
        "invoked_script": "fund_agent_personal_run",
        "artifacts": artifacts,
    }


def _print_console_summary(
    *,
    run_id: str,
    health: dict[str, Any],
    run_dir: Path,
    output_dir: Path,
    artifacts: dict[str, str],
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
    display_order = [
        ("agent_context_md", "agent_context.md"),
        ("e2e_summary", "e2e_summary.json"),
        ("report", "report.md"),
        ("identity_overrides_template", "fund_identity_overrides.template.private.yaml"),
        ("personal_health_report", "personal_health_report.json"),
    ]
    for artifact_key, filename in display_order:
        if artifact_key not in artifacts:
            continue
        artifact_path = rel_dir / filename
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

    # ── Execution mode resolution ─────────────────────────────────────
    execution_mode = getattr(args, "execution_mode", "real_analysis")
    skip_akshare = _resolve_skip_akshare(args)

    # Fail fast if real_analysis + explicit --skip-akshare
    if execution_mode == "real_analysis" and args._explicit_skip_akshare:
        return 1

    # Override args.skip_akshare with the resolved value
    args.skip_akshare = skip_akshare

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
        "--output-report", str(run_dir / "report.md"),
        "--transaction-source", args.transaction_source,
        "--invoked-by-personal-run",
    ]
    if args.skip_akshare:
        e2e_argv.append("--skip-akshare")
    if args.skip_news:
        e2e_argv.append("--skip-news")
    if args.dry_run:
        e2e_argv.append("--dry-run")
    if getattr(args, "enable_name_search", False):
        e2e_argv.append("--enable-name-search")

    e2e_env = {"FUND_AGENT_CANONICAL_PERSONAL_RUN": "1"}
    e2e_rc = e2e_main(e2e_argv, env_overrides=e2e_env)

    # ── Step 2b: Load holdings snapshot (if available) ────────────────
    holdings_snapshot = _load_holdings_snapshot(args, private_data)
    if holdings_snapshot:
        print(f"  Holdings snapshot loaded: {holdings_snapshot['summary']['positions_total']} position(s)")

    # ── Step 3: Load summary and build agent context ──────────────────
    e2e_summary_path = run_dir / "e2e_summary.json"
    e2e_summary = _load_json_safe(e2e_summary_path)

    # If E2E wrote summary elsewhere (eval_workspace), try to find it
    if not e2e_summary:
        alt_path = REPO_ROOT / "eval_workspace" / "runs" / run_id / "e2e_summary.json"
        e2e_summary = _load_json_safe(alt_path)
        if e2e_summary and alt_path.exists():
            e2e_summary_path = alt_path

    summary_status = str(e2e_summary.get("status", "")).lower()
    if summary_status in {"success", "partial", "failed"}:
        e2e_status = summary_status
    else:
        e2e_status = "success" if e2e_rc == 0 else "failed"

    health = _as_dict(e2e_summary.get("personal_health_report"))

    report_path = run_dir / "report.md"
    report_generated = _summary_report_generated(e2e_summary)

    if not report_path.exists() and report_generated:
        # E2E may have written it elsewhere; copy only when the summary proves
        # the analyze step completed in this run. This prevents stale reports.
        report_from_summary = e2e_summary.get("output_report", "")
        if report_from_summary:
            src = Path(report_from_summary)
            if not src.is_absolute():
                src = REPO_ROOT / src
            if src.exists():
                try:
                    report_content = src.read_text(encoding="utf-8")
                    _write_text(report_path, report_content)
                except OSError:
                    pass
    report_available = report_generated and report_path.exists()

    # ── Step 4: Write artifacts ───────────────────────────────────────
    _write_json(run_dir / "personal_health_report.json", health)

    # Copy e2e_summary to run_dir if it was written elsewhere
    if e2e_summary and e2e_summary_path != run_dir / "e2e_summary.json":
        _write_json(run_dir / "e2e_summary.json", e2e_summary)

    # Merge holdings snapshot into e2e_summary if available
    if holdings_snapshot:
        e2e_summary["holdings_snapshot"] = {
            "loaded": True,
            "positions_count": holdings_snapshot["summary"]["positions_total"],
            "shares_available_count": holdings_snapshot["summary"]["shares_available_count"],
            "current_value_available_count": holdings_snapshot["summary"]["current_value_available_count"],
            "user_verified_count": holdings_snapshot["summary"]["user_verified_count"],
            "valued_count": holdings_snapshot["summary"]["valued_count"],
            "summary": holdings_snapshot["summary"],
        }
        # Write holdings snapshot to run_dir (desensitized counts only)
        _write_json(run_dir / "holdings_snapshot_summary.json", e2e_summary["holdings_snapshot"])
        # Update valuation_summary if holdings provide current_value
        vs = e2e_summary.get("valuation_summary", {})
        if holdings_snapshot["summary"]["valued_count"] > 0:
            vs["holdings_snapshot_valued_count"] = holdings_snapshot["summary"]["valued_count"]
            vs["holdings_snapshot_loaded"] = True
        e2e_summary["valuation_summary"] = vs

        # Apply holdings snapshot overlay to confirmed_portfolio if available
        confirmed_portfolio_path = run_dir / "portfolio" / "confirmed_portfolio.private.json"
        if not confirmed_portfolio_path.exists():
            # Try alternative location
            alt_cp = REPO_ROOT / "eval_workspace" / "runs" / run_id / "portfolio" / "confirmed_portfolio.private.json"
            if alt_cp.exists():
                confirmed_portfolio_path = alt_cp

        if confirmed_portfolio_path.exists():
            try:
                confirmed_portfolio = _load_json_safe(confirmed_portfolio_path)
                if confirmed_portfolio and confirmed_portfolio.get("positions"):
                    overlay_result = apply_holdings_snapshot_overlay(confirmed_portfolio, holdings_snapshot)
                    # Write overlay result back
                    _write_json(confirmed_portfolio_path, overlay_result)
                    # Update e2e_summary with overlay results
                    cp_summary = overlay_result.get("summary", {})
                    e2e_summary["holdings_snapshot"]["overlay_applied"] = True
                    e2e_summary["holdings_snapshot"]["snapshot_valued_count"] = cp_summary.get("holdings_snapshot_valued_count", 0)
                    e2e_summary["holdings_snapshot"]["reconciliation_gap_count"] = cp_summary.get("reconciliation_gap_count", 0)
                    e2e_summary["holdings_snapshot"]["portfolio_valuation_status"] = cp_summary.get("portfolio_valuation_status", "")
                    # Update valuation_summary with overlay results
                    vs["holdings_snapshot_overlay_applied"] = True
                    vs["portfolio_valuation_status_after_overlay"] = cp_summary.get("portfolio_valuation_status", "")
                    e2e_summary["valuation_summary"] = vs
                    if cp_summary.get("reconciliation_gap_count", 0) > 0:
                        print(f"  WARNING: {cp_summary['reconciliation_gap_count']} reconciliation gap(s) detected between snapshot and reconstruction")
            except (OSError, ValueError) as exc:
                print(f"  WARNING: Failed to apply holdings snapshot overlay: {exc}", file=sys.stderr)
    else:
        e2e_summary["holdings_snapshot"] = {"loaded": False}

    # Write updated e2e_summary back to disk (with holdings_snapshot data)
    _write_json(run_dir / "e2e_summary.json", e2e_summary)

    artifact_paths = {
        "e2e_summary": "e2e_summary.json",
        "personal_health_report": "personal_health_report.json",
        "agent_context_md": "agent_context.md",
        "agent_context_json": "agent_context.json",
    }
    if report_available:
        artifact_paths["report"] = "report.md"
    identity_template_path = run_dir / "fund_identity_overrides.template.private.yaml"
    if identity_template_path.exists():
        _copy_identity_template_to_private_data(run_dir, private_data)
        artifact_paths["identity_overrides_template"] = "fund_identity_overrides.template.private.yaml"

    # Build agent context after artifact availability is known.
    context_artifact_paths = {
        "e2e_summary": "e2e_summary.json",
        "personal_health_report": "personal_health_report.json",
        **({"report": "report.md"} if report_available else {}),
    }
    if identity_template_path.exists():
        context_artifact_paths["identity_overrides_template"] = "fund_identity_overrides.template.private.yaml"
    agent_context = build_agent_context(
        e2e_summary,
        run_id=run_id,
        artifact_paths=context_artifact_paths,
    )
    agent_context_md = render_agent_context_markdown(agent_context)
    _write_json(run_dir / "agent_context.json", agent_context)
    _write_text(run_dir / "agent_context.md", agent_context_md)

    # ── Step 4b: Generate fix-it package (if requested) ───────────────
    fixit_dir = None
    if args.generate_fixit_package:
        fixit_dir = run_dir / "fixit"
        _generate_fixit_package(fixit_dir, e2e_summary, holdings_snapshot, run_dir=run_dir)
        artifact_paths["fixit_readme"] = "fixit/README.md"
        artifact_paths["fixit_holdings_template"] = "fixit/current_holdings_snapshot_template.csv"
        artifact_paths["fixit_identity_template"] = "fixit/fund_identity_overrides.suggested.yaml"
        artifact_paths["fixit_nav_needed"] = "fixit/nav_overrides_needed.csv"
        artifact_paths["fixit_fee_needed"] = "fixit/fee_overrides_needed.csv"

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
        execution_mode=execution_mode,
        enable_name_search=getattr(args, "enable_name_search", False),
        e2e_summary=e2e_summary,
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
        artifacts=artifact_paths,
    )

    return 1 if e2e_status == "failed" else 0


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
        "--execution-mode",
        choices=["real_analysis", "offline_debug"],
        default="real_analysis",
        help=(
            "Execution mode: real_analysis (default, live NAV) or "
            "offline_debug (deterministic, no live data)"
        ),
    )
    parser.add_argument(
        "--skip-akshare",
        action="store_true",
        default=False,
        help=(
            "Skip AkShare-dependent steps. NOT allowed with real_analysis mode; "
            "use --execution-mode offline_debug instead."
        ),
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
    parser.add_argument(
        "--holdings-snapshot", default="",
        help=(
            "Path to current holdings snapshot (.csv or .json). "
            "Auto-detects private_data/current_holdings_snapshot.private.{csv,json}"
        ),
    )
    parser.add_argument(
        "--generate-fixit-package",
        action="store_true",
        help="Generate fix-it package with data templates for missing information",
    )
    parser.add_argument(
        "--enable-transaction-derived-valuation",
        action="store_true",
        default=False,
        help=(
            "Enable transaction-derived holdings reconstruction (M7.9). "
            "When no holdings snapshot is available, reconstruct units and "
            "current_value from transaction amounts, trade-date NAV, fee rules, "
            "and trade date rules. All reconstructed values are labeled as "
            "estimated/transaction-derived, never platform_reported."
        ),
    )
    parser.add_argument(
        "--enable-name-search",
        action="store_true",
        default=False,
        help=(
            "Enable name-based fund identity candidate discovery (M7.11/M7.12). "
            "When no fund_identity_overrides are available, searches for candidate "
            "fund codes from provider name lookup. Only unique high-confidence "
            "matches auto-promote to provider_verified. Ambiguous/low-confidence "
            "candidates stay unverified for manual review."
        ),
    )
    args = parser.parse_args(argv)
    # Track whether --skip-akshare was explicitly passed (not just the default)
    args._explicit_skip_akshare = "--skip-akshare" in (argv or sys.argv[1:])
    return run_personal(args)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _generate_fixit_package(
    fixit_dir: Path,
    e2e_summary: dict[str, Any],
    holdings_snapshot: dict[str, Any] | None,
    run_dir: Path | None = None,
) -> None:
    """Generate fix-it package with data templates for missing information.

    Only writes template/suggested files — never includes real private data.
    M7.6: Also generates identity_candidates.private.csv for user review.
    M7.13: Also generates identity_candidate_cache_template.private.csv.
    """
    fixit_dir.mkdir(parents=True, exist_ok=True)

    # 1. README
    readme = _build_fixit_readme(e2e_summary, holdings_snapshot)
    _write_text(fixit_dir / "README.md", readme)

    # 2. Current holdings snapshot template
    _write_text(
        fixit_dir / "current_holdings_snapshot_template.csv",
        "as_of_date,fund_code,fund_name,shares,latest_nav,nav_date,current_value,holding_cost,holding_profit,holding_profit_pct,source,user_verified\n"
        ",,Your Fund Name,,,,,,,,,\n",
    )

    # 3. Suggested identity overrides (desensitized — no real fund names)
    identity = e2e_summary.get("identity_resolution", {})
    unverified_count = int(identity.get("identity_verification_status_counts", {}).get("manual_override_unverified", 0))
    identity_yaml = (
        "# Suggested fund identity overrides\n"
        "# M7.6: Fill in verified_by_user: true ONLY AFTER manually verifying the code and name.\n"
        "# You must also provide verification_source and verified_at.\n"
        "# DO NOT add verified_by_user:true without first verifying — it is NOT an unlock switch.\n"
        "# DO NOT commit this file with real fund codes\n\n"
        f"# {unverified_count} fund(s) need identity verification\n\n"
        "funds: []\n"
    )
    _write_text(fixit_dir / "fund_identity_overrides.suggested.yaml", identity_yaml)

    # 4. NAV overrides needed
    vs = e2e_summary.get("valuation_summary", {})
    nav_needed = vs.get("insufficient_trade_date_nav_coverage", False)
    nav_csv = "fund_code,trade_date,nav\n"
    if nav_needed:
        nav_csv += ",,fill in trade-date NAV for missing dates\n"
    _write_text(fixit_dir / "nav_overrides_needed.csv", nav_csv)

    # 5. Fee overrides needed
    fee_unknown_count = int(vs.get("redemption_fee_unknown_count", 0))
    fee_csv = "fund_code,redemption_fee_tier_days,redemption_fee_pct\n"
    if fee_unknown_count > 0:
        fee_csv += f"# {fee_unknown_count} fund(s) with unknown redemption fees\n"
        fee_csv += ",7,0.015\n,30,0.005\n,365,0.0\n"
    _write_text(fixit_dir / "fee_overrides_needed.csv", fee_csv)

    # 6. M7.6: Identity candidates private CSV — contains real fund names and candidate codes
    # M7.13: Also load identity resolution file for individual resolutions
    if run_dir is not None:
        id_file = run_dir / "fund_identity_resolution.json"
        if id_file.exists():
            try:
                id_data = json.loads(id_file.read_text(encoding="utf-8"))
                if "resolutions" in id_data and "identity_resolution" in e2e_summary:
                    e2e_summary["identity_resolution"]["resolutions"] = id_data["resolutions"]
            except (OSError, json.JSONDecodeError):
                pass
    _generate_identity_candidates_csv(fixit_dir, e2e_summary)

    print(f"  Fix-it package generated: {fixit_dir}")


def _build_fixit_readme(
    e2e_summary: dict[str, Any],
    holdings_snapshot: dict[str, Any] | None,
) -> str:
    """Build README.md for fix-it package."""
    reason_codes = list(e2e_summary.get("personal_health_report", {}).get("reason_codes", []))
    vs = e2e_summary.get("valuation_summary", {})
    identity = e2e_summary.get("identity_resolution", {})
    unverified_count = int(identity.get("identity_verification_status_counts", {}).get("manual_override_unverified", 0))

    lines = [
        "# Fix-it Package — Personal Data Completion Guide",
        "",
        "This package contains templates to help you provide missing data.",
        "After filling in the templates, place them in your `private_data/` directory and re-run.",
        "",
        "## Current Status",
        "",
        f"- Reason codes: {', '.join(reason_codes) if reason_codes else 'none'}",
        f"- Valuation: {vs.get('estimated_count', 0)} estimated, {vs.get('cashflow_only_count', 0)} cashflow-only",
        f"- Identity: {unverified_count} unverified",
        "",
        "## What to Provide",
        "",
        "### 1. Current Holdings Snapshot (Most Effective)",
        "",
        "The single most effective way to get portfolio valuation is to provide",
        "a current holdings snapshot from your platform (e.g., Alipay holdings page).",
        "",
        "Fill in `current_holdings_snapshot_template.csv` with:",
        "- fund_code (6-digit code)",
        "- fund_name",
        "- shares (number of units held)",
        "- latest_nav and nav_date",
        "- current_value (total market value)",
        "- user_verified: true (after you verify the data)",
        "",
        "Place the filled file as: `private_data/current_holdings_snapshot.private.csv`",
        "",
        "### 2. Fund Identity Verification (M7.6)",
        "",
        "If fund codes are unverified, review `identity_candidates.private.csv` first.",
        "This file contains the candidate codes that the system found for each fund.",
        "",
        "**IMPORTANT:** Candidate codes are NOT verified. You must manually verify each one.",
        "",
        "After verifying, edit `fund_identity_overrides.suggested.yaml`:",
        "- Set `verified_by_user: true` ONLY AFTER verifying the code and name match",
        "- Set `verification_source` (must be one of: alipay_holdings_page, fund_detail_page,",
        "  official_fund_statement, provider_cross_check, user_manual_verified)",
        "- Set `verified_at` (date of verification)",
        "",
        "**Do NOT add verified_by_user:true without first verifying.**",
        "It is NOT an unlock switch — it records that you have verified the mapping.",
        "",
        "### 3. NAV Overrides",
        "",
        "If trade-date NAV is missing, fill in `nav_overrides_needed.csv`.",
        "Note: latest NAV alone is NOT sufficient for valuation.",
        "You need either shares + latest NAV, or complete trade-date NAV history.",
        "",
        "### 4. Fee Overrides",
        "",
        "If redemption fees are unknown, fill in `fee_overrides_needed.csv`.",
        "",
        "### 5. Local Identity Candidate Cache (M7.13)",
        "",
        "When network providers are unavailable (SSL errors, corporate firewall, etc.),",
        "you can populate a local identity candidate cache for offline name search.",
        "",
        "Fill in `identity_candidate_cache_template.private.csv` with candidate fund codes",
        "from 支付宝/天天基金/基金详情页, then place it as:",
        "`private_data/fund_identity_candidate_cache.private.csv`",
        "",
        "**IMPORTANT:**",
        "- This is NOT a holdings snapshot.",
        "- This is NOT a verified override.",
        "- Candidates still go through M7.11 deterministic scoring and auto-verify gate.",
        "- If ambiguous, candidates stay unverified and appear in identity_candidates.private.csv.",
        "",
        "## Key Principle",
        "",
        "- **Holdings snapshot** → current portfolio structure and market value",
        "- **Transaction history** → cost basis, P&L attribution, historical analysis",
        "- **Both together** → complete picture with reconciliation",
        "",
        "## Re-running",
        "",
        "```bash",
        "bin/fund-agent-personal-run \\",
        "  --private-data-dir private_data \\",
        "  --output-dir local_reports \\",
        "  --transaction-source auto \\",
        "  --execution-mode real_analysis \\",
        "  --skip-news \\",
        "  --generate-fixit-package",
        "```",
    ]
    return "\n".join(lines)


def _generate_identity_candidates_csv(
    fixit_dir: Path,
    e2e_summary: dict[str, Any],
) -> None:
    """M7.6/M7.12: Generate identity_candidates.private.csv for user review.

    Contains real fund names and candidate codes — this is a private artifact.
    Users must verify each candidate before adding verified_by_user:true.
    M7.12: Also includes name search candidates from M7.11 discovery.
    """
    identity = e2e_summary.get("identity_resolution", {})
    resolutions = identity.get("resolutions", [])

    if not resolutions:
        return

    # Build CSV with candidate information
    csv_lines = [
        "raw_fund_name,candidate_fund_code,candidate_fund_name,candidate_source,verification_status,match_score,match_bucket,user_verified,verified_at,verification_source",
    ]

    candidate_count = 0
    verified_count = 0
    unverified_count = 0
    mismatch_count = 0
    name_search_candidate_count = 0

    for res in resolutions:
        if not isinstance(res, dict):
            continue
        raw_name = res.get("raw_fund_name", "")
        resolved_code = res.get("resolved_fund_code", "")
        identity_status = res.get("identity_verification_status", "")
        resolution_source = res.get("resolution_source", "")

        # Include entries with resolved codes
        if resolved_code:
            # Determine candidate source
            candidates = res.get("candidates", [])
            candidate_source = resolution_source
            if candidates:
                candidate_source = candidates[-1].get("source", resolution_source)

            # Determine verification fields
            user_verified = "true" if identity_status in ("user_verified_override", "provider_verified", "verified") else "false"
            verified_at = res.get("verified_at", "")
            verification_source = res.get("verification_source", "")

            csv_lines.append(
                f"{raw_name},{resolved_code},,{candidate_source},{identity_status},,,"
                f"{user_verified},{verified_at},{verification_source}"
            )

            candidate_count += 1
            if identity_status in ("verified", "provider_verified", "user_verified_override"):
                verified_count += 1
            elif identity_status == "code_name_mismatch":
                mismatch_count += 1
            else:
                unverified_count += 1

        # M7.12: Include name search candidates (even without resolved code)
        name_search_candidates = res.get("name_search_candidates", [])
        for cand in name_search_candidates:
            cand_code = cand.get("fund_code", "")
            cand_name = cand.get("fund_name", "")
            cand_score = cand.get("match_score", "")
            cand_bucket = cand.get("match_bucket", "")
            csv_lines.append(
                f"{raw_name},{cand_code},{cand_name},name_search_candidate,{identity_status},"
                f"{cand_score},{cand_bucket},,,"
            )
            name_search_candidate_count += 1

        # Include name-only entries without resolved codes (for fix-it)
        if not resolved_code and not name_search_candidates and identity_status in (
            "name_only", "name_search_candidate_unverified", "code_unverified",
        ):
            csv_lines.append(
                f"{raw_name},,,unresolved,{identity_status},,,,"
            )

    _write_text(fixit_dir / "identity_candidates.private.csv", "\n".join(csv_lines) + "\n")

    # Write public counts-only summary
    summary = {
        "candidate_count": candidate_count,
        "verified_count": verified_count,
        "unverified_count": unverified_count,
        "mismatch_count": mismatch_count,
        "name_search_candidate_count": name_search_candidate_count,
    }
    _write_json(fixit_dir / "identity_candidates_summary.json", summary)

    # M7.13: Generate identity candidate cache template if providers failed
    _generate_identity_candidate_cache_template(fixit_dir, e2e_summary)

    if unverified_count > 0 or name_search_candidate_count > 0:
        print(f"  Identity candidates: {unverified_count} unverified, {verified_count} verified, {mismatch_count} mismatch, {name_search_candidate_count} name-search")


def _generate_identity_candidate_cache_template(
    fixit_dir: Path,
    e2e_summary: dict[str, Any],
) -> None:
    """M7.13: Generate identity_candidate_cache_template.private.csv.

    This template helps users populate a local identity candidate cache
    for offline name search fallback when network providers are unavailable.

    This is NOT a holdings snapshot, NOT a verified override, and NOT
    authoritative. It is only a candidate source for provider name search.
    """
    provider_diag = e2e_summary.get("name_search_provider_diagnostics", {})
    identity = e2e_summary.get("identity_resolution", {})
    resolutions = identity.get("resolutions", [])

    # Only generate template if:
    # 1. Provider chain had failures, OR
    # 2. There are name-only funds that could benefit from cache
    chain_failed = bool(provider_diag.get("providers_failed", []))
    has_name_only = any(
        r.get("identity_verification_status") == "name_only"
        for r in resolutions
        if isinstance(r, dict)
    )

    if not chain_failed and not has_name_only:
        return

    # Build template CSV
    csv_lines = [
        "normalized_name,fund_code,fund_name,fund_type,share_class,source,updated_at,confidence_hint,notes",
        "# Fill in candidate fund codes for each fund name below.",
        "# This is NOT a verified override — candidates still go through M7.11 scoring.",
        "# Source: 支付宝/天天基金/基金详情页",
        "# Place the filled file as: private_data/fund_identity_candidate_cache.private.csv",
        "",
    ]

    # Add rows for name-only funds
    for res in resolutions:
        if not isinstance(res, dict):
            continue
        identity_status = res.get("identity_verification_status", "")
        if identity_status != "name_only":
            continue
        raw_name = res.get("raw_fund_name", "")
        csv_lines.append(f"{raw_name},,,,,manual,,,")

    _write_text(
        fixit_dir / "identity_candidate_cache_template.private.csv",
        "\n".join(csv_lines) + "\n",
    )

    print("  Identity candidate cache template generated (for offline name search fallback)")


if __name__ == "__main__":
    raise SystemExit(main())
