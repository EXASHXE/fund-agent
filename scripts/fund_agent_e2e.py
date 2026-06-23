#!/usr/bin/env python3
"""Canonical cross-platform E2E pipeline orchestrator.

The POSIX and Windows launchers delegate here. Subprocess output is redacted,
critical failures return non-zero, and optional provider failures are recorded
as warnings in ``e2e_summary.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from scripts.fund_identity_utils import is_valid_fund_code

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
VERSION_FILE = REPO_ROOT / "VERSION"


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    step_id: str
    name: str
    ok: bool
    output_path: Path | None = None
    warning: str | None = None


@dataclass
class PipelineState:
    """Accumulated state across pipeline steps.

    Pipeline statuses live here — they are never written back into
    intermediate data files (identity JSON, ledger, etc.).
    """

    steps: list[StepResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    steps_completed: list[str] = field(default_factory=list)
    # Pipeline-level status that used to be written into identity JSON
    fund_data_snapshot_attempted: bool = False
    fund_data_snapshot_status: str | None = None
    reconstruction_attempted: bool = False
    reconstruction_status: str | None = None
    valid_fund_codes_count: int = 0
    name_only_count: int = 0

    def record_step(self, result: StepResult, critical: bool = False) -> None:
        self.steps.append(result)
        if result.ok:
            self.steps_completed.append(result.step_id)
        else:
            (self.errors if critical else self.warnings).append(
                f"{result.step_id} failed"
            )
        if result.warning:
            self.warnings.append(result.warning)


def _read_version() -> str:
    """Read the project version from the VERSION file."""
    return VERSION_FILE.read_text(encoding="utf-8").strip()

_REDACT_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|authorization|cookie)=\S+",
    re.IGNORECASE,
)


def _redact(line: str) -> str:
    return _REDACT_PATTERN.sub(r"\1=***REDACTED***", line)


def _run_step(
    step_num: str,
    name: str,
    cmd: list[str],
    dry_run: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> bool:
    """Run one pipeline command without exposing private file contents."""
    print(f"[step {step_num}] {name}")
    if dry_run:
        print(f"  (dry-run) would run: {' '.join(cmd)}")
        return True
    try:
        env = os.environ.copy()
        env.update(env_overrides or {})
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=REPO_ROOT,
            env=env,
        )
        for line in (result.stdout or "").splitlines():
            print(f"  {_redact(line)}")
        for line in (result.stderr or "").splitlines():
            print(f"  {_redact(line)}", file=sys.stderr)
        if result.returncode != 0:
            print(f"  WARNING: step {step_num} exited with code {result.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  WARNING: step {step_num} timed out")
        return False
    except Exception as exc:  # pragma: no cover - defensive process boundary
        print(f"  WARNING: step {step_num} failed: {_redact(str(exc))}")
        return False


def _python(script: str) -> list[str]:
    return [sys.executable, str(SCRIPTS_DIR / script)]


def _has_usable_nav(path: Path) -> bool:
    """Return whether a NAV snapshot contains at least one usable record."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return any(
        fund.get("records")
        for fund in payload.get("nav_by_fund", {}).values()
        if isinstance(fund, dict)
    )


def _collect_coverage(factor_snapshot: Path, news_snapshot: Path) -> dict[str, Any]:
    """Collect aggregate coverage only; never copy holdings or provider payloads."""
    coverage: dict[str, Any] = {}
    try:
        factor = json.loads(factor_snapshot.read_text(encoding="utf-8"))
        coverage["data_completeness"] = factor.get("data_completeness_factors", {})
        coverage["profile"] = factor.get("profile_coverage", {})
    except (OSError, json.JSONDecodeError):
        pass
    try:
        news = json.loads(news_snapshot.read_text(encoding="utf-8"))
        coverage["news_items_count"] = len(news.get("items", []))
        coverage["news_coverage_gap_count"] = len(news.get("coverage_gaps", []))
    except (OSError, json.JSONDecodeError):
        pass
    return coverage


def run_pipeline(args: argparse.Namespace) -> int:
    as_of = args.as_of or date.today().isoformat()
    private_data = Path(args.private_data_dir) if args.private_data_dir else REPO_ROOT / "private_data"
    run_id = args.run_id or f"e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "eval_workspace" / "runs" / run_id
    output_report = Path(args.output_report) if args.output_report else REPO_ROOT / "local_reports" / "real_portfolio_report.md"
    summary_path = run_dir / "e2e_summary.json"
    dry_run = args.dry_run

    if not dry_run:
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            output_report.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"ERROR: cannot create E2E output directories: {_redact(str(exc))}", file=sys.stderr)
            return 1

    pipeline = PipelineState()

    def run_step(
        step_num: str,
        step_id: str,
        name: str,
        cmd: list[str],
        *,
        critical: bool,
        expected_output: Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> bool:
        ok = _run_step(step_num, name, cmd, dry_run, env_overrides)
        if ok and expected_output is not None and not dry_run and not expected_output.exists():
            ok = False
            print(f"  WARNING: step {step_num} did not create its required output")
        result = StepResult(step_id=step_id, name=name, ok=ok, output_path=expected_output if ok else None)
        pipeline.record_step(result, critical=critical)
        return ok

    alipay_csv = next(iter(sorted(private_data.glob("alipay_record_*.csv"), reverse=True)), None)
    plan_path = private_data / "investment_plan.private.yaml"
    investment_plan = plan_path if plan_path.exists() else None
    input_path = private_data / "portfolio_input.private.json"
    portfolio_input: Path | None = input_path if input_path.exists() else None

    if not any((alipay_csv, investment_plan, portfolio_input)):
        message = "No usable input found: expected an Alipay CSV, investment plan, or portfolio input"
        if dry_run:
            print(f"DRY-RUN: {message}")
        else:
            pipeline.errors.append(message)

    normalized_tx = run_dir / "normalized_transactions.json"
    planned_tx = run_dir / "planned_transactions.json"
    ledger = run_dir / "transaction_ledger.json"
    fund_identity = run_dir / "fund_identity_resolution.json"
    fund_snapshot_dir = run_dir / "fund_data_snapshot"
    portfolio_dir = run_dir / "portfolio"
    nav_snapshot = fund_snapshot_dir / "nav_snapshot.private.json"
    fee_snapshot = fund_snapshot_dir / "fee_schedule_snapshot.private.json"
    fund_profile_snapshot = fund_snapshot_dir / "fund_profile_snapshot.private.json"
    confirmed_portfolio = portfolio_dir / "confirmed_portfolio.private.json"
    kg_context = run_dir / "kg_context_snapshot.json"
    news_snapshot = run_dir / "news_snapshot.json"
    factor_snapshot = run_dir / "factor_snapshot.json"

    if alipay_csv:
        run_step(
            "0a", "import_alipay_transactions", "Import Alipay transactions",
            _python("import_alipay_transactions.py")
            + ["--input", str(alipay_csv), "--output", str(normalized_tx)],
            critical=True, expected_output=normalized_tx,
        )

    if investment_plan:
        run_step(
            "0b", "generate_planned_transactions", "Generate planned transactions (pre-NAV)",
            _python("generate_planned_transactions.py")
            + ["--plan", str(investment_plan), "--as-of-date", as_of, "--output", str(planned_tx)],
            critical=True, expected_output=planned_tx,
        )

    ledger_args = ["--output", str(ledger)]
    if normalized_tx.exists():
        ledger_args += ["--alipay", str(normalized_tx)]
    if planned_tx.exists():
        ledger_args += ["--planned", str(planned_tx)]
    if len(ledger_args) > 2:
        run_step(
            "0c", "build_transaction_ledger", "Build transaction ledger",
            _python("build_transaction_ledger.py") + ledger_args,
            critical=True, expected_output=ledger,
        )

    if ledger.exists():
        # Check for manual override file
        overrides_path = private_data / "fund_identity_overrides.private.yaml"
        identity_cmd = _python("resolve_fund_identities.py") + [
            "--ledger", str(ledger), "--output", str(fund_identity),
        ]
        if overrides_path.exists():
            identity_cmd += ["--overrides", str(overrides_path)]
        identity_ok = run_step(
            "0d", "resolve_fund_identities", "Resolve fund identities",
            identity_cmd,
            critical=False, expected_output=fund_identity,
        )
        # Extract fund codes from identity resolution (always, even with --skip-akshare)
        fund_codes: list[str] = []
        if identity_ok and fund_identity.exists():
            try:
                identity_data = json.loads(fund_identity.read_text(encoding="utf-8"))
                # Support current schema: resolutions[].resolved_fund_code
                # Backward compat: funds[].resolved_code
                entries = identity_data.get("resolutions", identity_data.get("funds", []))
                code_field = "resolved_fund_code" if "resolutions" in identity_data else "resolved_code"
                raw_codes = [
                    entry.get(code_field, "")
                    for entry in entries
                    if entry.get(code_field)
                ]
                # Count name-only: entries where resolved_fund_code is None
                name_only_count = sum(
                    1 for entry in entries
                    if entry.get(code_field) is None
                )
                # Validate: only six-digit codes are valid fund codes
                fund_codes = [c for c in raw_codes if is_valid_fund_code(c)]
                pipeline.valid_fund_codes_count = len(fund_codes)
                pipeline.name_only_count = name_only_count
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                pipeline.warnings.append(
                    f"Identity output unreadable ({type(exc).__name__})"
                )

        # When --skip-akshare is set but NAV overrides exist, still run snapshot
        # (overrides provide all NAV data without needing live AkShare provider)
        nav_overrides = private_data / "nav_overrides.private.json"
        skip_snapshot = args.skip_akshare and not nav_overrides.exists()
        if skip_snapshot:
            pipeline.warnings.append("build_fund_data_snapshot skipped by --skip-akshare (no NAV overrides)")
            print("[step 0e] SKIP: --skip-akshare flag set and no NAV overrides")
        elif fund_codes:
            try:
                live_env = {"RUN_LIVE_PROVIDER_TESTS": "1"} if args.use_live_provider else None
                snapshot_cmd = _python("build_fund_data_snapshot.py") + [
                    "--fund-codes", *fund_codes, "--as-of-date", as_of,
                    "--output-dir", str(fund_snapshot_dir),
                ]
                # Wire private NAV/profile/fee overrides if they exist
                nav_overrides = private_data / "nav_overrides.private.json"
                profile_overrides = private_data / "fund_profile_overrides.private.json"
                fee_overrides = private_data / "fee_overrides.private.json"
                if nav_overrides.exists():
                    snapshot_cmd += ["--nav-overrides", str(nav_overrides)]
                if profile_overrides.exists():
                    snapshot_cmd += ["--profile-overrides", str(profile_overrides)]
                if fee_overrides.exists():
                    snapshot_cmd += ["--fee-overrides", str(fee_overrides)]
                snapshot_ok = run_step(
                    "0e", "build_fund_data_snapshot", "Build fund data snapshot",
                    snapshot_cmd,
                    critical=False, expected_output=nav_snapshot,
                    env_overrides=live_env,
                )
                # Record snapshot status in PipelineState, NOT in identity JSON
                pipeline.fund_data_snapshot_attempted = True
                if not snapshot_ok:
                    pipeline.fund_data_snapshot_status = "provider_unavailable"
                    pipeline.warnings.append("build_fund_data_snapshot: provider/NAV failed or unavailable")
                else:
                    pipeline.fund_data_snapshot_status = "attempted"
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                pipeline.warnings.append(
                    f"build_fund_data_snapshot skipped: invalid identity output ({type(exc).__name__})"
                )
        else:
            if pipeline.name_only_count > 0:
                pipeline.warnings.append(
                    f"build_fund_data_snapshot skipped: {pipeline.name_only_count} name-only references; "
                    "fund_code mapping required for NAV"
                )
            else:
                pipeline.warnings.append("build_fund_data_snapshot skipped: no resolved fund codes")

        usable_nav = _has_usable_nav(nav_snapshot)
        if investment_plan and usable_nav:
            run_step(
                "0e2", "generate_planned_transactions_with_nav",
                "Regenerate planned transactions (with NAV)",
                _python("generate_planned_transactions.py")
                + ["--plan", str(investment_plan), "--as-of-date", as_of,
                   "--nav-snapshot", str(nav_snapshot), "--output", str(planned_tx)],
                critical=True, expected_output=planned_tx,
            )
            ledger_args = ["--output", str(ledger)]
            if normalized_tx.exists():
                ledger_args += ["--alipay", str(normalized_tx)]
            if planned_tx.exists():
                ledger_args += ["--planned", str(planned_tx)]
            run_step(
                "0c2", "rebuild_transaction_ledger_with_nav",
                "Rebuild transaction ledger (NAV-aware)",
                _python("build_transaction_ledger.py") + ledger_args,
                critical=True, expected_output=ledger,
            )

        if usable_nav:
            reconstructed_input = portfolio_dir / "portfolio_input.private.json"
            reconstruct_args = [
                "--ledger", str(ledger), "--nav-snapshot", str(nav_snapshot),
                "--as-of-date", as_of, "--output-dir", str(portfolio_dir),
            ]
            if fee_snapshot.exists():
                reconstruct_args += ["--fee-snapshot", str(fee_snapshot)]
            if fund_identity.exists():
                reconstruct_args += ["--fund-identity-resolution", str(fund_identity)]
            reconstruct_ok = run_step(
                "0f", "reconstruct_portfolio_from_ledger",
                "Reconstruct portfolio from ledger",
                _python("reconstruct_portfolio_from_ledger.py") + reconstruct_args,
                critical=True, expected_output=reconstructed_input,
            )
            # Record reconstruction status in PipelineState, NOT in identity JSON
            pipeline.reconstruction_attempted = True
            if reconstruct_ok and reconstructed_input.exists():
                pipeline.reconstruction_status = "reconstructed_from_ledger"
            else:
                pipeline.reconstruction_status = "reconstruction_failed"
            if reconstructed_input.exists():
                portfolio_input = reconstructed_input
        else:
            # Distinguish why NAV is unavailable
            valid_codes = pipeline.valid_fund_codes_count
            snapshot_attempted = pipeline.fund_data_snapshot_attempted
            if valid_codes == 0:
                nav_reason = "no valid six-digit fund codes"
            elif snapshot_attempted:
                nav_reason = "NAV provider failed or returned no usable data"
            else:
                nav_reason = "NAV snapshot not generated"
            pipeline.warnings.append(f"Portfolio valuation unavailable: {nav_reason}; reconstruction skipped")
            print(f"[step 0f] SKIP: NAV unavailable ({nav_reason})")
            # Record in PipelineState, NOT in identity JSON
            pipeline.reconstruction_attempted = False
            pipeline.reconstruction_status = "nav_unavailable"

    if portfolio_input and portfolio_input.exists():
        kg_args = ["--portfolio-input", str(portfolio_input), "--output", str(kg_context)]
        if fund_profile_snapshot.exists():
            kg_args += ["--fund-profile-snapshot", str(fund_profile_snapshot)]
        if confirmed_portfolio.exists():
            kg_args += ["--confirmed-portfolio", str(confirmed_portfolio)]
        run_step(
            "1", "build_knowledge_graph_context", "Build knowledge graph context",
            _python("build_knowledge_graph_context.py") + kg_args,
            critical=True, expected_output=kg_context,
        )
    else:
        print("[step 1] SKIP: no portfolio input available")
        if not dry_run and any((alipay_csv, investment_plan)):
            # If identity resolved fund codes but NAV was unavailable, this is
            # a partial result (nav_unavailable), not a hard failure.
            if pipeline.reconstruction_status == "nav_unavailable" and pipeline.valid_fund_codes_count > 0:
                pipeline.warnings.append(
                    "Portfolio analysis unavailable: identity resolved but NAV data missing"
                )
            else:
                pipeline.errors.append("No portfolio input available for required analysis")

    if args.skip_news:
        print("[step 2] SKIP: --skip-news flag set")
        pipeline.warnings.append("build_news_snapshot skipped by --skip-news")
    elif kg_context.exists():
        run_step(
            "2", "build_news_snapshot", "Build news snapshot",
            _python("build_news_snapshot.py")
            + ["--kg-context", str(kg_context), "--output", str(news_snapshot)],
            critical=False, expected_output=news_snapshot,
        )
    else:
        print("[step 2] SKIP: no KG context available")

    if portfolio_input and portfolio_input.exists():
        factor_args = ["--portfolio-input", str(portfolio_input), "--output", str(factor_snapshot)]
        if kg_context.exists():
            factor_args += ["--kg-context", str(kg_context)]
        if news_snapshot.exists():
            factor_args += ["--news-snapshot", str(news_snapshot)]
        run_step(
            "3", "build_factor_snapshot", "Build factor snapshot",
            _python("build_factor_snapshot.py") + factor_args,
            critical=True, expected_output=factor_snapshot,
        )

        analysis_args = [
            sys.executable, "-m", "src.fund_agent.cli", "analyze-portfolio",
            "--input", str(portfolio_input), "--format", "markdown",
            "--output", str(output_report),
        ]
        provider_data = fund_snapshot_dir / "provider_data_snapshot.json"
        if provider_data.exists():
            analysis_args += ["--provider-snapshot", str(provider_data)]
        if news_snapshot.exists():
            analysis_args += ["--news-snapshot", str(news_snapshot)]
        if factor_snapshot.exists():
            analysis_args += ["--factor-snapshot", str(factor_snapshot)]
        if kg_context.exists():
            analysis_args += ["--kg-context", str(kg_context)]
        run_step(
            "4", "analyze-portfolio", "Analyze portfolio (markdown report)",
            analysis_args, critical=True, expected_output=output_report,
        )
    else:
        print("[step 3] SKIP: no portfolio input available")
        print("[step 4] SKIP: no portfolio input available")

    if dry_run:
        print("\nE2E dry-run complete.")
        print(f"Summary: {summary_path}")
        print(f"Report:  {output_report}")
        return 0

    status = "failed" if pipeline.errors else "partial" if pipeline.warnings else "success"

    # Determine portfolio_input_source and transaction_reconstruction_status
    portfolio_input_source = "unavailable" if pipeline.reconstruction_status == "nav_unavailable" else "none"
    transaction_reconstruction_status = "skipped"
    alipay_import_stats: dict[str, Any] = {}

    if portfolio_input and portfolio_input.exists():
        # Check if this was reconstructed from ledger or is an existing private input
        if pipeline.reconstruction_status == "reconstructed_from_ledger" and str(portfolio_input).startswith(str(portfolio_dir)):
            portfolio_input_source = "reconstructed_from_ledger"
        else:
            portfolio_input_source = "existing_private_portfolio_input"

    if alipay_csv is not None:
        if normalized_tx.exists():
            transaction_reconstruction_status = "parsed_from_alipay"
            try:
                tx_data = json.loads(normalized_tx.read_text(encoding="utf-8"))
                if isinstance(tx_data, list):
                    alipay_import_stats["total_transactions"] = len(tx_data)
                    fund_txns = [t for t in tx_data if isinstance(t, dict) and (t.get("fund_code") or t.get("fund_name"))]
                    alipay_import_stats["fund_transactions"] = len(fund_txns)
                    # Count by classification
                    classification_counts: dict[str, int] = {}
                    for t in fund_txns:
                        cls = str(t.get("classification", t.get("action", "unknown")))
                        classification_counts[cls] = classification_counts.get(cls, 0) + 1
                    alipay_import_stats["classification_counts"] = classification_counts
                elif isinstance(tx_data, dict):
                    alipay_import_stats["total_transactions"] = len(tx_data.get("transactions", []))
                    fund_txns = [t for t in tx_data.get("transactions", []) if isinstance(t, dict) and (t.get("fund_code") or t.get("fund_name"))]
                    alipay_import_stats["fund_transactions"] = len(fund_txns)
            except (OSError, json.JSONDecodeError):
                pass
        else:
            transaction_reconstruction_status = "not_reconstructed_from_alipay"

    # Warn if Alipay CSV found but no fund transactions parsed
    if alipay_csv is not None and alipay_import_stats.get("fund_transactions", 0) == 0 and not dry_run:
        pipeline.warnings.append("Alipay CSV was found but no fund transactions were parsed")

    # If portfolio_input fallback is used, status should be partial
    if portfolio_input_source == "existing_private_portfolio_input" and not dry_run:
        if transaction_reconstruction_status in ("parsed_from_alipay",):
            # Alipay was parsed but portfolio_input is the fallback
            pass  # This is expected when NAV is unavailable
        if status == "success":
            status = "partial"

    # Collect identity resolution summary (read-only, never write back)
    identity_resolution_summary: dict[str, Any] = {}
    identity_schema_version: str = "unknown"
    if fund_identity.exists():
        try:
            id_data = json.loads(fund_identity.read_text(encoding="utf-8"))
            identity_resolution_summary = id_data.get("summary", {})
            identity_schema_version = id_data.get("schema_version", "unknown")
        except (OSError, json.JSONDecodeError):
            pass

    # Collect valuation_type_counts from portfolio_input if available
    valuation_type_counts: dict[str, int] = {}
    if portfolio_input and portfolio_input.exists():
        try:
            pi_data = json.loads(portfolio_input.read_text(encoding="utf-8"))
            dq = pi_data.get("data_quality", {})
            valuation_type_counts = dq.get("valuation_summary", {})
        except (OSError, json.JSONDecodeError):
            pass

    summary: dict[str, Any] = {
        "run_id": run_id,
        "as_of": as_of,
        "completed_at": datetime.now().isoformat(),
        "status": status,
        "warnings": pipeline.warnings,
        "errors": pipeline.errors,
        "steps_completed": pipeline.steps_completed,
        "pipeline_steps": {
            "fund_data_snapshot_attempted": pipeline.fund_data_snapshot_attempted,
            "fund_data_snapshot_status": pipeline.fund_data_snapshot_status,
            "reconstruction_attempted": pipeline.reconstruction_attempted,
            "reconstruction_status": pipeline.reconstruction_status,
            "valid_fund_codes_count": pipeline.valid_fund_codes_count,
            "name_only_count": pipeline.name_only_count,
        },
        "outputs": {
            "report": str(output_report) if output_report.exists() else None,
            "summary": str(summary_path),
        },
        "output_report": str(output_report) if output_report.exists() else None,
        "coverage": _collect_coverage(factor_snapshot, news_snapshot),
        "portfolio_input_source": portfolio_input_source,
        "transaction_reconstruction_status": transaction_reconstruction_status,
        "alipay_import": alipay_import_stats,
        "identity_resolution": identity_resolution_summary,
        "identity_schema_version": identity_schema_version,
        "valuation_summary": valuation_type_counts,
        "pipeline_version": _read_version(),
    }
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: failed to write e2e_summary.json: {_redact(str(exc))}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    print(f"\nE2E pipeline {status}. Run ID: {run_id}")
    print(f"Summary: {summary_path}")
    print(f"Report:  {output_report if output_report.exists() else 'not generated'}")
    return 1 if pipeline.errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fund-agent-e2e",
        description="fund-agent E2E pipeline runner",
    )
    parser.add_argument("--as-of", default="", help="Portfolio reconstruction date (YYYY-MM-DD)")
    parser.add_argument(
        "--use-live-provider",
        action="store_true",
        help="Set RUN_LIVE_PROVIDER_TESTS=1 for the fund snapshot subprocess",
    )
    parser.add_argument("--skip-news", action="store_true", help="Skip news snapshot step")
    parser.add_argument("--skip-akshare", action="store_true", help="Skip AkShare-dependent steps")
    parser.add_argument("--dry-run", action="store_true", help="Print pipeline steps without executing")
    parser.add_argument("--output-report", default="", help="Output report path")
    parser.add_argument("--run-id", default="", help="Run identifier for eval_workspace")
    parser.add_argument("--private-data-dir", default="", help="Private data directory (default: private_data/)")
    parser.add_argument("--output-dir", default="", help="Output/workspace directory")
    args = parser.parse_args(argv)
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
