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
from src.tools.portfolio.personal_health_report import build_personal_health_summary
from src.tools.portfolio.portfolio_input_transactions import (
    build_ledger_from_portfolio_input_transactions,
    load_portfolio_input_transactions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
VERSION_FILE = REPO_ROOT / "VERSION"


# ── Transaction source routing ────────────────────────────────────────


@dataclass
class TransactionSourceDecision:
    """Result of transaction source selection logic."""

    source: str  # "alipay" | "portfolio_input.transactions" | "none"
    reason: str
    use_alipay: bool = False
    use_portfolio_input_transactions: bool = False
    error: str | None = None
    warning: str | None = None


def decide_transaction_source(
    requested: str,
    alipay_csv_exists: bool,
    portfolio_input_exists: bool,
    portfolio_input_transactions_count: int,
) -> TransactionSourceDecision:
    """Decide which transaction source to use based on request and availability.

    Semantics:
      - auto: Alipay CSV preferred, then portfolio_input.transactions fallback
      - alipay: Only use Alipay; error if missing; no fallback
      - portfolio_input: Only use portfolio_input.transactions; error if missing; no fallback
    """
    if requested == "auto":
        if alipay_csv_exists:
            return TransactionSourceDecision(
                source="alipay",
                reason="auto: Alipay CSV available and takes precedence",
                use_alipay=True,
            )
        if portfolio_input_exists and portfolio_input_transactions_count > 0:
            return TransactionSourceDecision(
                source="portfolio_input.transactions",
                reason="auto: no Alipay CSV, falling back to portfolio_input.transactions",
                use_portfolio_input_transactions=True,
            )
        return TransactionSourceDecision(
            source="none",
            reason="auto: no Alipay CSV and no portfolio_input.transactions available",
            error="No usable transaction source found",
        )

    if requested == "alipay":
        if alipay_csv_exists:
            return TransactionSourceDecision(
                source="alipay",
                reason="explicit: Alipay CSV available",
                use_alipay=True,
            )
        return TransactionSourceDecision(
            source="none",
            reason="explicit: requested alipay but no Alipay CSV found",
            error="Requested alipay transaction source but no Alipay CSV found",
        )

    if requested == "portfolio_input":
        if portfolio_input_exists and portfolio_input_transactions_count > 0:
            return TransactionSourceDecision(
                source="portfolio_input.transactions",
                reason="explicit: portfolio_input.transactions available",
                use_portfolio_input_transactions=True,
            )
        return TransactionSourceDecision(
            source="none",
            reason="explicit: requested portfolio_input but no portfolio_input.transactions found",
            error="Requested portfolio_input transaction source but no portfolio_input.transactions found",
        )

    # Unknown requested value — should not reach here due to argparse choices
    return TransactionSourceDecision(
        source="none",
        reason=f"unknown transaction source: {requested}",
        error=f"Unknown transaction source: {requested}",
    )


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


def _resolve_identities_with_name_search(
    *,
    ledger_path: Path,
    overrides_path: Path | None,
    output_path: Path,
    enable_name_search: bool = True,
    private_data_dir: Path | None = None,
) -> bool:
    """M7.13: Resolve fund identities with provider fallback chain.

    Builds a ChainedFundIdentitySearchProvider:
    1. LocalIdentityCandidateCacheProvider (if cache file exists in private_data)
    2. AkShareNameSearchProvider (network provider, may fail)

    When --enable-name-search is set, this is called instead of the subprocess
    approach because we need to inject FundIdentitySearchProvider objects.

    Returns True if identity resolution succeeded (output file written).
    """
    try:
        import yaml
    except ImportError:
        yaml = None  # type: ignore[assignment]

    from scripts.resolve_fund_identities import resolve_fund_identities, _load_overrides
    from src.tools.portfolio.akshare_name_search_provider import AkShareNameSearchProvider
    from src.tools.portfolio.local_identity_candidate_cache_provider import (
        LocalIdentityCandidateCacheProvider,
    )
    from src.tools.portfolio.name_search_provider_chain import (
        ChainedFundIdentitySearchProvider,
    )

    # Load ledger data
    try:
        ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  ERROR: Cannot read ledger: {exc}", file=sys.stderr)
        return False

    # Load overrides if available
    override_lookup: dict[str, dict[str, Any]] = {}
    override_warnings: list[str] = []
    if overrides_path and overrides_path.exists():
        override_lookup, override_warnings = _load_overrides(overrides_path)
        for w in override_warnings:
            print(f"  Warning: {w}", file=sys.stderr)

    # M7.13: Build provider chain
    providers = []

    # 1. Local cache provider (if cache file exists)
    local_cache_provider = None
    local_cache_path = None
    if private_data_dir and private_data_dir.is_dir():
        for cache_name in (
            "fund_identity_candidate_cache.private.csv",
            "fund_identity_candidate_cache.private.json",
        ):
            candidate_path = private_data_dir / cache_name
            if candidate_path.exists():
                local_cache_path = candidate_path
                break

    if local_cache_path is not None:
        local_cache_provider = LocalIdentityCandidateCacheProvider(local_cache_path)
        providers.append(local_cache_provider)
        print(f"  Local identity candidate cache found: {local_cache_path.name}")

    # 2. AkShare network provider
    akshare_provider = AkShareNameSearchProvider()
    providers.append(akshare_provider)

    # Build chain (always use chain for consistent diagnostics)
    name_search_provider: Any = ChainedFundIdentitySearchProvider(providers)

    # Run identity resolution
    try:
        result = resolve_fund_identities(
            ledger_data=ledger_data,
            override_lookup=override_lookup,
            name_search_provider=name_search_provider,
            enable_name_search=enable_name_search,
        )
    except Exception as exc:
        print(f"  ERROR: Identity resolution failed: {exc}", file=sys.stderr)
        return False

    # Include override validation warnings
    if override_warnings:
        result["summary"]["override_validation_warnings"] = override_warnings

    # M7.13: Include aggregated provider diagnostics
    provider_diag = name_search_provider.get_diagnostics()
    result["name_search_provider_diagnostics"] = provider_diag

    # M7.13: Include local cache diagnostics separately
    if local_cache_provider is not None:
        result["local_cache_diagnostics"] = local_cache_provider.get_diagnostics()

    # Write output
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  Identity resolution written: {output_path}")
        summary_line = json.dumps(result["summary"], ensure_ascii=False, indent=2)
        print(summary_line)
        return True
    except OSError as exc:
        print(f"  ERROR: Cannot write identity output: {exc}", file=sys.stderr)
        return False


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


def _load_nav_coverage_summary(portfolio_dir: Path) -> dict[str, Any]:
    """Load NAV coverage summary from reconstruction output.

    Reads only the summary counts — never copies holdings, fund names,
    amounts, or transaction details. Returns {} if unavailable.
    """
    confirmed = portfolio_dir / "confirmed_portfolio.private.json"
    if not confirmed.exists():
        return {}
    try:
        data = json.loads(confirmed.read_text(encoding="utf-8"))
        # nav_coverage_summary is nested under summary.nav_coverage_summary
        summary = data.get("summary", {})
        nav_cs = summary.get("nav_coverage_summary")
        if isinstance(nav_cs, dict):
            # Return only counts — strip any private fields if present
            safe_keys = {
                "positions_total", "positions_estimated", "positions_cashflow_only",
                "positions_unavailable", "positions_manual_review_required",
                "nav_coverage_full_count", "nav_coverage_partial_count",
                "nav_coverage_none_count", "nav_coverage_latest_only_count",
                "latest_nav_stale_count", "qdii_like_count",
                "estimated_current_value_total", "estimated_current_value_coverage_count",
                "estimated_current_value_total_is_partial",
                "trade_date_nav_requested_count", "trade_date_nav_found_count",
            }
            return {k: v for k, v in nav_cs.items() if k in safe_keys}
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {}


def _yaml_quote(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _relative_output(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path.name)


def _write_identity_overrides_template(
    fund_identity_path: Path,
    output_path: Path,
) -> Path | None:
    """Write a private fill-in template for name-only fund references.

    The generated file may contain private fund names, so callers must keep it
    under gitignored run/private directories and never print its contents.
    """
    try:
        identity_data = json.loads(fund_identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None

    entries = identity_data.get("resolutions", identity_data.get("funds", []))
    if not isinstance(entries, list):
        return None

    names: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        is_name_only = (
            entry.get("resolution_status") == "name_only"
            or entry.get("identity_verification_status") == "name_only"
        )
        if not is_name_only:
            continue
        raw_name = (
            entry.get("raw_fund_name")
            or entry.get("fund_name")
            or entry.get("raw_reference")
        )
        if not raw_name:
            continue
        raw_name = str(raw_name)
        if raw_name not in seen:
            seen.add(raw_name)
            names.append(raw_name)

    if not names:
        return None

    lines = [
        "# Auto-generated private template from fund identity resolution.",
        "# Fill each fund_code with the official six-digit fund code, then copy",
        "# this file to private_data/fund_identity_overrides.private.yaml.",
        "# Do not commit this file.",
        "",
        "funds:",
    ]
    for name in names:
        lines.extend([
            f"  - raw_name: {_yaml_quote(name)}",
            '    fund_code: ""',
            f"    fund_name: {_yaml_quote(name)}",
        ])
    lines.extend(["", "aliases: {}", ""])

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        return None
    return output_path


def _build_personal_health_report(
    *,
    pipeline: PipelineState,
    portfolio_input_source: str,
    transaction_source_used: str,
    portfolio_input_txn_stats: dict[str, Any],
    identity_resolution_summary: dict[str, Any],
    valuation_type_counts: dict[str, int],
    nav_coverage_summary: dict[str, Any] | None = None,
    name_search_provider_diagnostics: dict[str, Any] | None = None,
    local_cache_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build personal health report from collected pipeline state.

    Wraps build_personal_health_summary with error handling so that
    a health report failure never crashes the E2E pipeline or leaks
    private data.
    """
    try:
        e2e_summary_data: dict[str, Any] = {
            "transaction_source": transaction_source_used,
            "portfolio_input_source": portfolio_input_source,
            "pipeline_steps": {
                "fund_data_snapshot_attempted": pipeline.fund_data_snapshot_attempted,
                "fund_data_snapshot_status": pipeline.fund_data_snapshot_status,
                "reconstruction_attempted": pipeline.reconstruction_attempted,
                "reconstruction_status": pipeline.reconstruction_status,
                "valid_fund_codes_count": pipeline.valid_fund_codes_count,
                "name_only_count": pipeline.name_only_count,
            },
        }
        # M7.13: Include provider chain diagnostics
        if name_search_provider_diagnostics:
            e2e_summary_data["name_search_provider_diagnostics"] = name_search_provider_diagnostics
        if local_cache_diagnostics:
            e2e_summary_data["local_cache_diagnostics"] = local_cache_diagnostics

        artifacts = {
            "e2e_summary": e2e_summary_data,
            "portfolio_input_transactions_summary": portfolio_input_txn_stats,
            "identity_summary": identity_resolution_summary,
            "valuation_summary": valuation_type_counts,
            "nav_coverage_summary": nav_coverage_summary or {},
        }
        return build_personal_health_summary(artifacts)
    except Exception as exc:
        # Never crash the pipeline; return a minimal error report
        return {
            "schema_version": "personal_health_report.v1",
            "overall_status": "unavailable",
            "confidence_level": "unavailable",
            "reason_codes": [],
            "data_sources": {
                "transaction_source": transaction_source_used,
                "valuation_source": portfolio_input_source,
                "identity_source": "unavailable",
            },
            "valuation_quality": {
                "positions_total": 0,
                "confirmed_count": 0,
                "estimated_full_coverage_count": 0,
                "estimated_partial_coverage_count": 0,
                "cashflow_only_count": 0,
                "unavailable_count": 0,
                "manual_review_count": 0,
                "estimated_current_value_total_is_partial": False,
            },
            "nav_coverage": {
                "full": 0,
                "partial": 0,
                "none": 0,
                "latest_only": 0,
                "stale_count": 0,
                "qdii_like_count": 0,
            },
            "fix_it_checklist": [],
            "safety_notes": [f"Health report generation failed: {type(exc).__name__}"],
        }


def run_pipeline(args: argparse.Namespace) -> int:
    as_of = args.as_of or date.today().isoformat()
    private_data = Path(args.private_data_dir) if args.private_data_dir else REPO_ROOT / "private_data"
    run_id = args.run_id or f"e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "eval_workspace" / "runs" / run_id

    # M7.7: For personal/private-data analysis, --output-report is mandatory.
    # The legacy flat path local_reports/real_portfolio_report.md is forbidden.
    is_canonical = (
        os.environ.get("FUND_AGENT_CANONICAL_PERSONAL_RUN") == "1"
        or getattr(args, "invoked_by_personal_run", False)
    )
    is_personal_data = private_data.name == "private_data" and private_data.is_dir()
    has_explicit_report = bool(args.output_report)

    if not has_explicit_report:
        if is_canonical:
            # personal-run must always specify --output-report; this is a bug
            print(
                "ERROR: canonical personal-run must specify --output-report. "
                "This is an internal error — please report.",
                file=sys.stderr,
            )
            return 1
        if is_personal_data and not getattr(args, "allow_noncanonical_test_run", False):
            print(
                "ERROR: --output-report is required for personal/private-data analysis. "
                "Use bin/fund-agent-personal-run which sets this automatically.",
                file=sys.stderr,
            )
            return 1

    if args.output_report:
        output_report = Path(args.output_report)
    elif getattr(args, "allow_noncanonical_test_run", False):
        # Test runs without --output-report default to run_dir instead of legacy flat path
        output_report = run_dir / "report.md"
    else:
        output_report = REPO_ROOT / "local_reports" / "real_portfolio_report.md"

    # M7.7: Block the legacy flat report path — always, even with --allow-noncanonical-test-run.
    # The flat path is inherently wrong for personal analysis; tests should use a run_dir path.
    # Check both exact repo-root match and any path ending in local_reports/real_portfolio_report.md
    legacy_flat = REPO_ROOT / "local_reports" / "real_portfolio_report.md"
    is_legacy_flat_path = (
        output_report.resolve() == legacy_flat.resolve()
        or output_report.name == "real_portfolio_report.md"
        and output_report.parent.name == "local_reports"
    )
    if is_legacy_flat_path and is_personal_data:
        print(
            "ERROR: local_reports/real_portfolio_report.md is forbidden for personal analysis. "
            "Use bin/fund-agent-personal-run which outputs to local_reports/<run_id>/report.md.",
            file=sys.stderr,
        )
        return 1

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
    identity_overrides_template = run_dir / "fund_identity_overrides.template.private.yaml"
    identity_overrides_template_output: Path | None = None

    # ── Transaction source selection ──────────────────────────────────
    # Probe available sources, then decide based on --transaction-source flag.
    pi_txns = load_portfolio_input_transactions(input_path) if input_path.exists() else []
    txn_decision = decide_transaction_source(
        requested=args.transaction_source,
        alipay_csv_exists=alipay_csv is not None,
        portfolio_input_exists=input_path.exists(),
        portfolio_input_transactions_count=len(pi_txns),
    )
    transaction_source_used = txn_decision.source
    portfolio_input_txn_stats: dict[str, Any] = {}

    if txn_decision.error:
        pipeline.errors.append(txn_decision.error)
        print(f"[step 0a] SKIP: {txn_decision.reason}")
    elif txn_decision.warning:
        pipeline.warnings.append(txn_decision.warning)

    # Execute the chosen source
    if txn_decision.use_alipay:
        run_step(
            "0a", "import_alipay_transactions", "Import Alipay transactions",
            _python("import_alipay_transactions.py")
            + ["--input", str(alipay_csv), "--output", str(normalized_tx)],
            critical=True, expected_output=normalized_tx,
        )
    elif txn_decision.use_portfolio_input_transactions:
        pi_ledger = build_ledger_from_portfolio_input_transactions(pi_txns)
        if not dry_run:
            try:
                run_dir.mkdir(parents=True, exist_ok=True)
                normalized_tx.write_text(
                    json.dumps(pi_ledger, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError as exc:
                print(f"ERROR: failed to write portfolio_input transactions: {_redact(str(exc))}", file=sys.stderr)
        portfolio_input_txn_stats = pi_ledger.get("summary", {})
        pi_warnings = pi_ledger.get("warnings", [])
        if pi_warnings and not dry_run:
            pipeline.warnings.append(
                f"portfolio_input.transactions has {len(pi_warnings)} validation warning(s); "
                f"check transaction source data"
            )
        print(f"[step 0a-alt] portfolio_input.transactions: {pi_ledger['summary'].get('total_transactions', 0)} transaction(s)")

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

        # M7.12: When --enable-name-search, resolve identities programmatically
        # to inject the FundIdentitySearchProvider (subprocess can't pass objects)
        if args.enable_name_search:
            identity_ok = _resolve_identities_with_name_search(
                ledger_path=ledger,
                overrides_path=overrides_path if overrides_path.exists() else None,
                output_path=fund_identity,
                enable_name_search=True,
                private_data_dir=private_data,
            )
            result = StepResult(
                step_id="0d", name="Resolve fund identities (with name search)",
                ok=identity_ok, output_path=fund_identity if identity_ok else None,
            )
            pipeline.record_step(result, critical=False)
        else:
            identity_ok = run_step(
                "0d", "resolve_fund_identities", "Resolve fund identities",
                identity_cmd,
                critical=False, expected_output=fund_identity,
            )
        # Extract fund codes from identity resolution (always, even with --skip-akshare)
        fund_codes: list[str] = []
        identity_mismatch_codes: set[str] = set()
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
                # Track identity-mismatch codes — these must NOT enter NAV fetch
                for entry in entries:
                    ivs = entry.get("identity_verification_status", "")
                    if ivs == "code_name_mismatch":
                        code = entry.get(code_field, "")
                        if code and is_valid_fund_code(code):
                            identity_mismatch_codes.add(code)
                # Filter out mismatched codes from NAV fetch
                if identity_mismatch_codes:
                    mismatched_count = len(identity_mismatch_codes)
                    fund_codes = [c for c in fund_codes if c not in identity_mismatch_codes]
                    pipeline.warnings.append(
                        f"{mismatched_count} fund code(s) have identity mismatch; "
                        "blocked from NAV fetch and valuation"
                    )
                pipeline.valid_fund_codes_count = len(fund_codes) + len(identity_mismatch_codes)
                pipeline.name_only_count = name_only_count
                if name_only_count > 0:
                    identity_overrides_template_output = _write_identity_overrides_template(
                        fund_identity,
                        identity_overrides_template,
                    )
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

    analysis_report_generated = False

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
        analysis_report_generated = run_step(
            "4", "analyze-portfolio", "Analyze portfolio (markdown report)",
            analysis_args, critical=True, expected_output=output_report,
        )
    else:
        print("[step 3] SKIP: no portfolio input available")
        print("[step 4] SKIP: no portfolio input available")

    if dry_run:
        print("\nE2E dry-run complete.")
        print(f"Summary: {summary_path}")
        print(f"Report:  {output_report.relative_to(REPO_ROOT) if output_report.is_relative_to(REPO_ROOT) else output_report.name}")
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

    # Derive transaction_reconstruction_status from the actual source decision
    if txn_decision.use_alipay:
        if normalized_tx.exists():
            transaction_reconstruction_status = "parsed_from_alipay"
            try:
                tx_data = json.loads(normalized_tx.read_text(encoding="utf-8"))
                if isinstance(tx_data, list):
                    alipay_import_stats["total_transactions"] = len(tx_data)
                    fund_txns = [t for t in tx_data if isinstance(t, dict) and (t.get("fund_code") or t.get("fund_name"))]
                    alipay_import_stats["fund_transactions"] = len(fund_txns)
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
    elif txn_decision.use_portfolio_input_transactions:
        transaction_reconstruction_status = "parsed_from_portfolio_input_transactions"
    elif txn_decision.error:
        transaction_reconstruction_status = "requested_source_missing"

    # Warn if Alipay was used but no fund transactions parsed
    if txn_decision.use_alipay and alipay_import_stats.get("fund_transactions", 0) == 0 and not dry_run:
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
    name_search_provider_diagnostics: dict[str, Any] = {}
    local_cache_diagnostics: dict[str, Any] = {}
    if fund_identity.exists():
        try:
            id_data = json.loads(fund_identity.read_text(encoding="utf-8"))
            identity_resolution_summary = id_data.get("summary", {})
            identity_schema_version = id_data.get("schema_version", "unknown")
            # M7.12: Extract name search provider diagnostics
            name_search_provider_diagnostics = id_data.get("name_search_provider_diagnostics", {})
            # M7.13: Extract local cache diagnostics
            local_cache_diagnostics = id_data.get("local_cache_diagnostics", {})
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

    report_output = _relative_output(output_report) if analysis_report_generated else None

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
            "report": report_output,
            "summary": str(summary_path.relative_to(REPO_ROOT)) if summary_path.is_relative_to(REPO_ROOT) else str(summary_path.name),
            "identity_overrides_template": _relative_output(identity_overrides_template_output),
        },
        "output_report": report_output,
        "coverage": _collect_coverage(factor_snapshot, news_snapshot),
        "portfolio_input_source": portfolio_input_source,
        "transaction_reconstruction_status": transaction_reconstruction_status,
        "transaction_source": transaction_source_used,
        "alipay_import": alipay_import_stats,
        "portfolio_input_transactions": portfolio_input_txn_stats,
        "identity_resolution": identity_resolution_summary,
        "identity_schema_version": identity_schema_version,
        "name_search_provider_diagnostics": name_search_provider_diagnostics,
        "local_cache_diagnostics": local_cache_diagnostics or None,
        "valuation_summary": valuation_type_counts,
        "personal_health_report": _build_personal_health_report(
            pipeline=pipeline,
            portfolio_input_source=portfolio_input_source,
            transaction_source_used=transaction_source_used,
            portfolio_input_txn_stats=portfolio_input_txn_stats,
            identity_resolution_summary=identity_resolution_summary,
            valuation_type_counts=valuation_type_counts,
            nav_coverage_summary=_load_nav_coverage_summary(portfolio_dir),
            name_search_provider_diagnostics=name_search_provider_diagnostics,
            local_cache_diagnostics=local_cache_diagnostics or None,
        ),
        "pipeline_version": _read_version(),
    }
    try:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: failed to write e2e_summary.json: {_redact(str(exc))}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))

    # If --health-report-only, also print a focused health summary
    if args.health_report_only:
        health = summary.get("personal_health_report", {})
        print("\n── Personal Health Report ──")
        print(json.dumps(health, indent=2))

    print(f"\nE2E pipeline {status}. Run ID: {run_id}")
    print(f"Summary: {summary_path}")
    print(f"Report:  {report_output or 'not generated'}")
    return 1 if pipeline.errors else 0


def _check_noncanonical_personal_analysis(args: argparse.Namespace) -> int | None:
    """M7.7: Fail fast if e2e is called directly for personal/private-data analysis.

    Returns None if the invocation is allowed, or a non-zero exit code if blocked.
    """
    # Canonical provenance means personal-run invoked this — always allowed
    has_canonical_env = os.environ.get("FUND_AGENT_CANONICAL_PERSONAL_RUN") == "1"
    has_canonical_arg = getattr(args, "invoked_by_personal_run", False)
    if has_canonical_env or has_canonical_arg:
        return None

    # Explicit test override
    if getattr(args, "allow_noncanonical_test_run", False):
        return None

    # Detect personal/private-data analysis signals
    private_data_dir = args.private_data_dir or str(REPO_ROOT / "private_data")
    private_data_path = Path(private_data_dir)

    # Signal 1: --private-data-dir points to "private_data"
    is_private_data_dir = private_data_path.name == "private_data" and private_data_path.is_dir()

    # Signal 2: --transaction-source is alipay or auto (implies real transactions)
    txn_source = getattr(args, "transaction_source", "auto")
    is_personal_txn_source = txn_source in ("alipay", "auto")

    # Signal 3: run_id starts with "personal-"
    run_id = args.run_id or ""
    is_personal_run_id = run_id.startswith("personal-")

    # Signal 4: output report is the legacy flat path
    output_report = args.output_report or ""
    is_legacy_flat_report = "real_portfolio_report.md" in output_report

    # Signal 5: private_data directory contains real portfolio artifacts
    has_real_portfolio_artifacts = False
    if is_private_data_dir:
        artifact_indicators = [
            "alipay_record_*.csv",
            "portfolio_input.private.json",
            "fund_identity_overrides.private.yaml",
            "nav_overrides.private.json",
        ]
        for pattern in artifact_indicators:
            if list(private_data_path.glob(pattern)):
                has_real_portfolio_artifacts = True
                break

    # Determine if this looks like personal analysis
    personal_signals = sum([
        is_private_data_dir,
        is_personal_txn_source,
        is_personal_run_id,
        is_legacy_flat_report,
        has_real_portfolio_artifacts,
    ])

    # Need at least 2 signals to block (avoid false positives on generic e2e)
    if personal_signals < 2:
        return None

    # Also block if no --output-report and private data detected (legacy flat path fallback)
    if not args.output_report and (is_private_data_dir or has_real_portfolio_artifacts):
        personal_signals += 1

    if personal_signals >= 2:
        print(
            "ERROR [non_canonical_personal_analysis_entrypoint]:\n"
            "Personal portfolio analysis must use bin/fund-agent-personal-run.\n"
            "Do not call scripts/fund_agent_e2e.py directly for private_data analysis.\n"
            "\n"
            "Suggested command:\n"
            "  bin/fund-agent-personal-run \\\n"
            "    --private-data-dir private_data \\\n"
            "    --output-dir local_reports \\\n"
            "    --transaction-source auto \\\n"
            "    --execution-mode real_analysis \\\n"
            "    --skip-news \\\n"
            "    --generate-fixit-package",
            file=sys.stderr,
        )
        return 1

    return None


def main(argv: list[str] | None = None, *, env_overrides: dict[str, str] | None = None) -> int:
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
    parser.add_argument("--enable-name-search", action="store_true", default=False,
                        help="Enable M7.11/M7.12 name-based fund identity candidate discovery")
    parser.add_argument("--dry-run", action="store_true", help="Print pipeline steps without executing")
    parser.add_argument("--output-report", default="", help="Output report path")
    parser.add_argument("--run-id", default="", help="Run identifier for eval_workspace")
    parser.add_argument("--private-data-dir", default="", help="Private data directory (default: private_data/)")
    parser.add_argument("--output-dir", default="", help="Output/workspace directory")
    parser.add_argument(
        "--transaction-source",
        choices=["auto", "alipay", "portfolio_input"],
        default="auto",
        help="Transaction source: auto (default, alipay first), alipay, or portfolio_input",
    )
    parser.add_argument(
        "--health-report-only",
        action="store_true",
        help="Print only the personal health report section from e2e_summary.json (does not skip pipeline steps)",
    )
    parser.add_argument(
        "--invoked-by-personal-run",
        action="store_true",
        help=argparse.SUPPRESS,  # Internal: set by fund-agent-personal-run for provenance
    )
    parser.add_argument(
        "--allow-noncanonical-test-run",
        action="store_true",
        help=(
            "Allow non-canonical invocation for tests/synthetic fixtures only. "
            "NOT for personal analysis with real private data."
        ),
    )
    args = parser.parse_args(argv)

    # ── M7.7: Non-canonical personal analysis guard ───────────────────
    if env_overrides:
        for k, v in env_overrides.items():
            os.environ[k] = v

    guard_result = _check_noncanonical_personal_analysis(args)
    if guard_result is not None:
        return guard_result

    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
