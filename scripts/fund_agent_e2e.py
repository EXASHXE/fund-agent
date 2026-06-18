#!/usr/bin/env python3
"""fund-agent-e2e Python orchestrator — shared E2E pipeline runner.

This is the canonical Python implementation of the E2E pipeline.
Both bin/fund-agent-e2e (bash) and bin/fund-agent-e2e.cmd (Windows)
delegate to this script.

Pipeline:
  import_alipay_transactions → generate_planned_transactions (pre-NAV) →
  build_transaction_ledger → resolve_fund_identities →
  build_fund_data_snapshot → generate_planned_transactions (with NAV) →
  rebuild ledger with NAV-aware planned transactions →
  reconstruct_portfolio_from_ledger →
  build_knowledge_graph_context → build_news_snapshot →
  build_factor_snapshot → analyze-portfolio markdown

Never prints private file contents or API key values.
Degrades gracefully if provider/news keys are absent.
Never uses stale round3 envelopes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

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
) -> bool:
    """Run a pipeline step. Returns True on success."""
    print(f"[step {step_num}] {name}")
    if dry_run:
        print(f"  (dry-run) would run: {' '.join(cmd)}")
        return True
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
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
    except Exception as exc:
        print(f"  WARNING: step {step_num} failed: {exc}")
        return False


def _python(script: str) -> list[str]:
    """Build a python command for a script in SCRIPTS_DIR."""
    return [sys.executable, str(SCRIPTS_DIR / script)]


def _file_exists(path: str | Path) -> bool:
    return Path(path).exists()


def _dir_exists(path: str | Path) -> bool:
    return Path(path).is_dir()


def run_pipeline(args: argparse.Namespace) -> int:
    as_of = args.as_of or date.today().isoformat()
    private_data = Path(args.private_data_dir) if args.private_data_dir else REPO_ROOT / "private_data"
    run_id = args.run_id or f"e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "eval_workspace" / "runs" / run_id
    output_report = args.output_report or str(REPO_ROOT / "local_reports" / "real_portfolio_report.md")

    dry_run = args.dry_run
    skip_news = args.skip_news
    skip_akshare = args.skip_akshare

    run_dir.mkdir(parents=True, exist_ok=True)
    Path(output_report).parent.mkdir(parents=True, exist_ok=True)

    # Detect input files
    alipay_csv = ""
    for f in sorted(private_data.glob("alipay_record_*.csv")):
        alipay_csv = str(f)

    investment_plan = ""
    plan_path = private_data / "investment_plan.private.yaml"
    if plan_path.exists():
        investment_plan = str(plan_path)

    portfolio_input = ""
    pi_path = private_data / "portfolio_input.private.json"
    if pi_path.exists():
        portfolio_input = str(pi_path)

    # Pipeline step paths
    normalized_tx = str(run_dir / "normalized_transactions.json")
    planned_tx = str(run_dir / "planned_transactions.json")
    ledger = str(run_dir / "transaction_ledger.json")
    fund_identity = str(run_dir / "fund_identity_resolution.json")
    fund_snapshot_dir = str(run_dir / "fund_data_snapshot")
    portfolio_dir = str(run_dir / "portfolio")
    kg_context = str(run_dir / "kg_context_snapshot.json")
    news_snapshot = str(run_dir / "news_snapshot.json")
    factor_snapshot = str(run_dir / "factor_snapshot.json")

    # Step 0a: Import Alipay transactions
    if alipay_csv:
        _run_step("0a", "Import Alipay transactions",
                  _python("import_alipay_transactions.py") + ["--input", alipay_csv, "--output", normalized_tx],
                  dry_run=dry_run)

    # Step 0b: Generate planned transactions (pre-NAV, to collect fund codes)
    if investment_plan:
        _run_step("0b", "Generate planned transactions (pre-NAV)",
                  _python("generate_planned_transactions.py") + ["--plan", investment_plan, "--as-of-date", as_of, "--output", planned_tx],
                  dry_run=dry_run)

    # Step 0c: Build transaction ledger
    ledger_args = ["--output", ledger]
    if _file_exists(normalized_tx):
        ledger_args += ["--alipay", normalized_tx]
    if _file_exists(planned_tx):
        ledger_args += ["--planned", planned_tx]
    if len(ledger_args) > 2:
        _run_step("0c", "Build transaction ledger",
                  _python("build_transaction_ledger.py") + ledger_args,
                  dry_run=dry_run)

    # Step 0d-0f: Resolve identities, build snapshot, reconstruct
    nav_snapshot = ""
    fee_snapshot = ""
    fund_profile_snapshot = ""
    confirmed_portfolio = ""

    if _file_exists(ledger):
        _run_step("0d", "Resolve fund identities",
                  _python("resolve_fund_identities.py") + ["--ledger", ledger, "--output", fund_identity],
                  dry_run=dry_run)

        # Step 0e: Build fund data snapshot
        if not skip_akshare and _file_exists(fund_identity):
            try:
                with open(fund_identity, encoding="utf-8") as f:
                    identity_data = json.load(f)
                fund_codes = [fd.get("resolved_code", "") for fd in identity_data.get("funds", []) if fd.get("resolved_code")]
                if fund_codes:
                    _run_step("0e", "Build fund data snapshot",
                              _python("build_fund_data_snapshot.py") + ["--fund-codes"] + fund_codes + ["--as-of-date", as_of, "--output-dir", fund_snapshot_dir],
                              dry_run=dry_run)
            except Exception:
                pass

        nav_snapshot = str(Path(fund_snapshot_dir) / "nav_snapshot.private.json")
        fee_snapshot = str(Path(fund_snapshot_dir) / "fee_schedule_snapshot.private.json")
        fund_profile_snapshot = str(Path(fund_snapshot_dir) / "fund_profile_snapshot.private.json")

        # Step 0e2: Regenerate planned transactions with NAV for rule_confirmed
        if investment_plan and _file_exists(nav_snapshot):
            _run_step("0e2", "Regenerate planned transactions (with NAV)",
                      _python("generate_planned_transactions.py") + ["--plan", investment_plan, "--as-of-date", as_of, "--nav-snapshot", nav_snapshot, "--output", planned_tx],
                      dry_run=dry_run)

            # Rebuild ledger with NAV-aware planned transactions
            ledger_args2 = ["--output", ledger]
            if _file_exists(normalized_tx):
                ledger_args2 += ["--alipay", normalized_tx]
            if _file_exists(planned_tx):
                ledger_args2 += ["--planned", planned_tx]
            _run_step("0c2", "Rebuild transaction ledger (NAV-aware)",
                      _python("build_transaction_ledger.py") + ledger_args2,
                      dry_run=dry_run)

        # Step 0f: Reconstruct portfolio
        if _file_exists(nav_snapshot):
            reconstruct_args = ["--ledger", ledger, "--nav-snapshot", nav_snapshot, "--as-of-date", as_of, "--output-dir", portfolio_dir]
            if _file_exists(fee_snapshot):
                reconstruct_args += ["--fee-snapshot", fee_snapshot]
            _run_step("0f", "Reconstruct portfolio from ledger",
                      _python("reconstruct_portfolio_from_ledger.py") + reconstruct_args,
                      dry_run=dry_run)

        # Update portfolio input from reconstruction
        reconstructed_pi = str(Path(portfolio_dir) / "portfolio_input.private.json")
        if _file_exists(reconstructed_pi):
            portfolio_input = reconstructed_pi

        confirmed_portfolio = str(Path(portfolio_dir) / "confirmed_portfolio.private.json")

    # Step 1: Build KG Context
    if portfolio_input and _file_exists(portfolio_input):
        kg_args = ["--portfolio-input", portfolio_input, "--output", kg_context]
        if _file_exists(fund_profile_snapshot):
            kg_args += ["--fund-profile-snapshot", fund_profile_snapshot]
        if _file_exists(confirmed_portfolio):
            kg_args += ["--confirmed-portfolio", confirmed_portfolio]
        _run_step("1", "Build knowledge graph context",
                  _python("build_knowledge_graph_context.py") + kg_args,
                  dry_run=dry_run)
    else:
        print("[step 1] SKIP: no portfolio input available")

    # Step 2: Build News Snapshot
    if skip_news:
        print("[step 2] SKIP: --skip-news flag set")
    elif _file_exists(kg_context):
        ok = _run_step("2", "Build news snapshot",
                       _python("build_news_snapshot.py") + ["--kg-context", kg_context, "--output", news_snapshot],
                       dry_run=dry_run)
        if not ok and not dry_run:
            print("[step 2] WARNING: news snapshot failed (provider keys may be absent); continuing")
    else:
        print("[step 2] SKIP: no KG context available")

    # Step 3: Build Factor Snapshot
    if portfolio_input and _file_exists(portfolio_input):
        factor_args = ["--portfolio-input", portfolio_input, "--output", factor_snapshot]
        if _file_exists(kg_context):
            factor_args += ["--kg-context", kg_context]
        if _file_exists(news_snapshot):
            factor_args += ["--news-snapshot", news_snapshot]
        _run_step("3", "Build factor snapshot",
                  _python("build_factor_snapshot.py") + factor_args,
                  dry_run=dry_run)
    else:
        print("[step 3] SKIP: no portfolio input available")

    # Step 4: Analyze Portfolio
    if portfolio_input and _file_exists(portfolio_input):
        analysis_args = [sys.executable, "-m", "fund_agent.cli",
                         "analyze-portfolio",
                         "--input", portfolio_input,
                         "--format", "markdown",
                         "--output", output_report]
        provider_data = str(Path(fund_snapshot_dir) / "provider_data_snapshot.json")
        if _file_exists(provider_data):
            analysis_args += ["--provider-snapshot", provider_data]
        if _file_exists(news_snapshot):
            analysis_args += ["--news-snapshot", news_snapshot]
        if _file_exists(factor_snapshot):
            analysis_args += ["--factor-snapshot", factor_snapshot]
        if _file_exists(kg_context):
            analysis_args += ["--kg-context", kg_context]
        _run_step("4", "Analyze portfolio (markdown report)",
                  analysis_args, dry_run=dry_run)

    # Write e2e_summary.json
    if not dry_run:
        steps_completed: list[str] = []
        if _file_exists(normalized_tx):
            steps_completed.append("import_alipay_transactions")
        if _file_exists(planned_tx):
            steps_completed.append("generate_planned_transactions")
        if _file_exists(ledger):
            steps_completed.append("build_transaction_ledger")
        if _file_exists(fund_identity):
            steps_completed.append("resolve_fund_identities")
        if _dir_exists(fund_snapshot_dir):
            steps_completed.append("build_fund_data_snapshot")
        if _dir_exists(portfolio_dir):
            steps_completed.append("reconstruct_portfolio_from_ledger")
        if _file_exists(kg_context):
            steps_completed.append("build_knowledge_graph_context")
        if _file_exists(news_snapshot):
            steps_completed.append("build_news_snapshot")
        if _file_exists(factor_snapshot):
            steps_completed.append("build_factor_snapshot")
        if _file_exists(output_report):
            steps_completed.append("analyze-portfolio")

        summary: dict[str, Any] = {
            "run_id": run_id,
            "as_of": as_of,
            "completed_at": datetime.now().isoformat(),
            "steps_completed": steps_completed,
            "output_report": output_report,
            "pipeline_version": "0.10.5",
        }
        summary_path = Path(run_dir) / "e2e_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(json.dumps(summary, indent=2))

    print()
    print(f"E2E pipeline complete. Run ID: {run_id}")
    print(f"Summary: {run_dir}/e2e_summary.json")
    print(f"Report:  {output_report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fund-agent-e2e",
        description="fund-agent E2E pipeline runner",
    )
    parser.add_argument("--as-of", default="", help="Portfolio reconstruction date (YYYY-MM-DD)")
    parser.add_argument("--use-live-provider", action="store_true", help="Enable live provider data fetch")
    parser.add_argument("--skip-news", action="store_true", help="Skip news snapshot step")
    parser.add_argument("--skip-akshare", action="store_true", help="Skip AkShare-dependent steps")
    parser.add_argument("--dry-run", action="store_true", help="Print pipeline steps without executing")
    parser.add_argument("--output-report", default="", help="Output report path")
    parser.add_argument("--run-id", default="", help="Run identifier for eval_workspace")
    parser.add_argument("--private-data-dir", default="", help="Private data directory (default: private_data/)")
    parser.add_argument("--output-dir", default="", help="Output/workspace directory (default: eval_workspace/runs/<run_id>/)")
    args = parser.parse_args(argv)
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
