"""Optional host-supplied data summaries for FundAnalysisSkill."""

from __future__ import annotations

from typing import Any

from src.schemas.skill import SkillInput
from src.tools.research.query_plan import build_research_query_plan

from .context import CoreMetricsBundle, OptionalSummariesBundle, PortfolioInputBundle


def build_optional_summaries(
    bundle: PortfolioInputBundle,
    metrics: CoreMetricsBundle,
    skill_input: SkillInput,
    warnings: list[str],
) -> OptionalSummariesBundle:
    # Check for optional data dimensions host might have requested
    add_missing_optional_warnings(
        warnings,
        bundle.fund_codes,
        benchmarks=bundle.benchmarks,
        benchmark_history=bundle.benchmark_history,
        peer_group=bundle.peer_group,
        factor_exposures=bundle.factor_exposures,
        manager_profiles=bundle.manager_profiles,
        fee_schedules=bundle.fee_schedules,
        redemption_rules=bundle.redemption_rules,
    )

    # Research query plan (deterministic, no network)
    query_plan = None
    if bundle.research_planning:
        try:
            themes = list(metrics.exposures.get("theme_exposure", {}).keys()) if isinstance(metrics.exposures, dict) else []
            industries = list(metrics.industry_exposure.keys()) if isinstance(metrics.industry_exposure, dict) else []
            query_plan = build_research_query_plan(
                portfolio_positions=bundle.positions,
                holdings=bundle.holdings,
                fund_profiles=bundle.fund_profiles,
                themes=themes[:20],
                industries=industries[:20],
                kg_context=skill_input.kg_context,
            )
        except Exception:
            pass

    # Optional data pass-through summaries
    benchmark_summary = summarize_benchmark_gap(
        metrics.fund_metrics,
        bundle.benchmarks,
        bundle.benchmark_history,
    ) if (bundle.benchmarks or bundle.benchmark_history) else None
    peer_summary = summarize_peer_data(bundle.peer_group) if bundle.peer_group else None
    fee_summary = summarize_fee_schedule(
        bundle.fee_schedules,
        bundle.fund_codes,
    ) if bundle.fee_schedules else None
    redemption_summary = summarize_redemption_constraints(
        bundle.redemption_rules,
        bundle.fund_codes,
    ) if bundle.redemption_rules else None
    factor_summary = summarize_factor_exposures(
        bundle.factor_exposures
    ) if bundle.factor_exposures else None
    manager_summary = summarize_manager_profiles(
        bundle.manager_profiles,
        bundle.fund_codes,
    ) if bundle.manager_profiles else None

    return OptionalSummariesBundle(
        benchmark_summary=benchmark_summary,
        peer_summary=peer_summary,
        fee_summary=fee_summary,
        redemption_summary=redemption_summary,
        factor_summary=factor_summary,
        manager_summary=manager_summary,
        query_plan=query_plan,
    )


def summarize_benchmark_gap(
    fund_metrics: dict[str, Any],
    benchmarks: dict[str, Any],
    benchmark_history: dict[str, Any],
) -> dict[str, Any] | None:
    """Summarise benchmark gap from host-provided data. Does not fabricate rankings.

    If benchmark_history provides point-in-time values alongside fund nav history,
    produces a simple performance comparison; otherwise pass-through only.
    """
    result: dict[str, Any] = {
        "benchmarks_available": sorted(str(key) for key in benchmarks.keys()) if benchmarks else [],
    }
    if benchmarks:
        result["benchmarks"] = {
            str(key): benchmarks[key]
            for key in sorted(benchmarks, key=str)
        }
    if benchmark_history:
        result["benchmark_history"] = {
            str(key): benchmark_history[key]
            for key in sorted(benchmark_history, key=str)
        }
        result["benchmark_history_keys"] = sorted(str(key) for key in benchmark_history.keys())
        # Attempt simple host-driven comparison if data shape allows
        comparison = derive_benchmark_comparison(benchmark_history, fund_metrics)
        if comparison:
            result["comparison"] = comparison
    return result if (benchmarks or benchmark_history) else None


def derive_benchmark_comparison(
    benchmark_history: dict[str, Any],
    fund_metrics: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """Derive a simple point-in-time comparison from benchmark history and fund metrics.

    Only uses host-provided data shapes; does not compute missing returns.
    """
    comparisons: list[dict[str, Any]] = []
    for fund_code in sorted(fund_metrics, key=str):
        metrics = fund_metrics[fund_code]
        if not isinstance(metrics, dict):
            continue
        fund_return = metrics.get("total_return")
        if fund_return is None:
            continue
        for bm_key in sorted(benchmark_history, key=str):
            bm_data = benchmark_history[bm_key]
            if not isinstance(bm_data, list) or len(bm_data) < 2:
                continue
            # Use first and last benchmark data point
            try:
                first_val = float(bm_data[0].get("value", bm_data[0].get("nav", 0)))
                last_val = float(bm_data[-1].get("value", bm_data[-1].get("nav", 0)))
                if first_val > 0:
                    bm_return = (last_val - first_val) / first_val
                    comparisons.append(
                        {
                            "fund_code": fund_code,
                            "benchmark": bm_key,
                            "fund_return": round(float(fund_return), 4),
                            "benchmark_return": round(bm_return, 4),
                            "excess_return": round(float(fund_return) - bm_return, 4),
                            "note": "host-provided data only; not a ranking or attribution analysis",
                        }
                    )
            except (TypeError, ValueError, IndexError):
                continue
    return comparisons if comparisons else None


def summarize_peer_data(peer_group: dict[str, Any]) -> dict[str, Any] | None:
    """Summarise peer group data. Extracts rank/percentile if host-provided.

    Does NOT invent peer ranking — only surfaces what the host already provides.
    """
    if not peer_group:
        return None
    result: dict[str, Any] = {
        "funds_with_peers": sorted(str(key) for key in peer_group.keys()),
        "peer_data": {
            str(key): peer_group[key]
            for key in sorted(peer_group, key=str)
        },
    }
    # Extract rankings where host-provided
    rankings: list[dict[str, Any]] = []
    for fund_code in sorted(peer_group, key=str):
        peer_info = peer_group[fund_code]
        if isinstance(peer_info, dict):
            entry: dict[str, Any] = {"fund_code": str(fund_code)}
            rank = peer_info.get("rank")
            total = peer_info.get("total")
            percentile = peer_info.get("percentile")
            category = peer_info.get("category", "")
            if rank is not None:
                entry["rank"] = rank
            if total is not None:
                entry["total"] = total
            if percentile is not None:
                entry["percentile"] = percentile
            if category:
                entry["category"] = category
            if rank is not None or percentile is not None:
                rankings.append(entry)
    if rankings:
        result["rankings"] = rankings
    return result


def summarize_fee_schedule(
    fee_schedules: dict[str, Any],
    fund_codes: list[str],
) -> dict[str, Any] | None:
    """Summarise fee schedules from host-provided data.

    Extracts management_fee, custody_fee, sales_fee, redemption_fee where present.
    """
    if not fee_schedules:
        return None
    fees_found: dict[str, Any] = {}
    fee_totals: dict[str, float] = {}
    for fc in sorted(fund_codes):
        fs = fee_schedules.get(fc)
        if fs and isinstance(fs, dict):
            extracted: dict[str, Any] = {}
            for key in ("management_fee", "custody_fee", "sales_fee", "redemption_fee", "total_expense_ratio"):
                val = fs.get(key)
                if val is not None:
                    try:
                        extracted[key] = float(val)
                    except (TypeError, ValueError):
                        extracted[key] = val
            if extracted:
                fees_found[fc] = extracted
                if isinstance(extracted.get("total_expense_ratio"), (int, float)):
                    fee_totals[fc] = float(extracted["total_expense_ratio"])
                else:
                    fee_totals[fc] = sum(
                        float(v) for key, v in extracted.items()
                        if key != "redemption_fee"
                        and isinstance(v, (int, float))
                        and v > 0
                    )
    if not fees_found:
        return None
    result: dict[str, Any] = {
        "funds_with_fees": sorted(fees_found.keys()),
        "fee_schedules": fees_found,
    }
    # Flag high-fee funds
    high_fee_funds = [
        fc for fc, total in fee_totals.items()
        if isinstance(total, (int, float)) and total > 0.025
    ]
    if high_fee_funds:
        result["high_fee_funds"] = high_fee_funds
        result["fee_warning"] = (
            f"Fund(s) {', '.join(high_fee_funds)} have total fees > 2.5% p.a.; "
            f"consider lower-cost alternatives if available"
        )
    return result


def summarize_redemption_constraints(
    redemption_rules: dict[str, Any],
    fund_codes: list[str],
) -> dict[str, Any] | None:
    """Summarise redemption rules from host-provided data.

    Extracts lockup, holding period, redemption fee risk, and liquidity notes.
    """
    if not redemption_rules:
        return None
    rules_found: dict[str, Any] = {}
    lockup_funds: list[str] = []
    high_fee_funds: list[str] = []
    for fc in sorted(fund_codes):
        rules = redemption_rules.get(fc)
        if rules and isinstance(rules, dict):
            summary: dict[str, Any] = {}
            for key in ("lockup_days", "lockup_months", "holding_period_days",
                        "redemption_fee_pct", "redemption_fee_schedule",
                        "liquidity_note", "suspended"):
                val = rules.get(key)
                if val is not None:
                    summary[key] = val
            if summary:
                rules_found[fc] = summary
                lockup = summary.get("lockup_days", summary.get("lockup_months"))
                if lockup and (isinstance(lockup, (int, float)) and float(lockup) > 0):
                    lockup_funds.append(fc)
                rfee = summary.get("redemption_fee_pct")
                if rfee and isinstance(rfee, (int, float)) and float(rfee) > 0.01:
                    high_fee_funds.append(fc)
                suspended = summary.get("suspended")
                if suspended and fc not in lockup_funds:
                    lockup_funds.append(fc)
    if not rules_found:
        return None
    result: dict[str, Any] = {
        "funds_with_rules": sorted(rules_found.keys()),
        "redemption_constraints": rules_found,
    }
    warnings: list[str] = []
    if lockup_funds:
        result["lockup_funds"] = lockup_funds
        warnings.append(
            f"Fund(s) {', '.join(lockup_funds)} have lockup or suspension "
            f"constraints — verify redemption eligibility"
        )
    if high_fee_funds:
        result["high_redemption_fee_funds"] = high_fee_funds
        warnings.append(
            f"Fund(s) {', '.join(high_fee_funds)} charge >1% redemption fees "
            f"— early redemption may be costly"
        )
    if warnings:
        result["warnings"] = warnings
    return result


def summarize_factor_exposures(
    factor_exposures: dict[str, Any],
) -> dict[str, Any] | None:
    """Summarise style/factor exposures from host-provided data.

    Flags concentration or missing style data; does not invent exposures.
    """
    if not factor_exposures:
        return None
    result: dict[str, Any] = {
        "factors": sorted(str(key) for key in factor_exposures.keys()),
        "factor_exposures": {
            str(key): factor_exposures[key]
            for key in sorted(factor_exposures, key=str)
        },
    }
    # Detect concentration in any single factor
    concentration_warnings: list[str] = []
    for factor_name in sorted(factor_exposures, key=str):
        exposure_data = factor_exposures[factor_name]
        if isinstance(exposure_data, dict):
            for fund_code in sorted(exposure_data, key=str):
                exp_val = exposure_data[fund_code]
                try:
                    abs_val = abs(float(exp_val))
                    if abs_val > 0.5:
                        concentration_warnings.append(
                            f"Fund {fund_code} has high {factor_name} exposure ({abs_val:.2f})"
                        )
                except (TypeError, ValueError):
                    pass
    if concentration_warnings:
        result["concentration_warnings"] = concentration_warnings
    return result


def summarize_manager_profiles(
    manager_profiles: dict[str, Any],
    fund_codes: list[str],
) -> dict[str, Any] | None:
    """Summarise manager profiles from host-provided data.

    Extracts tenure, start_date, and change-risk flags from provided fields only.
    """
    if not manager_profiles:
        return None
    profiles_found: dict[str, Any] = {}
    change_risk_funds: list[str] = []
    for fc in sorted(fund_codes):
        profile = manager_profiles.get(fc)
        if profile and isinstance(profile, dict):
            summary: dict[str, Any] = {}
            for key in ("manager_name", "tenure", "tenure_years", "start_date",
                        "manager_change", "manager_change_risk", "team_size"):
                val = profile.get(key)
                if val is not None:
                    summary[key] = val
            if summary:
                profiles_found[fc] = summary
                # Flag manager-change risk
                risk = summary.get("manager_change_risk")
                if risk and str(risk).lower() in ("high", "true", "1", "yes", "elevated"):
                    change_risk_funds.append(fc)
                change = summary.get("manager_change")
                if change and str(change).lower() in ("true", "1", "yes", "changed", "recent"):
                    if fc not in change_risk_funds:
                        change_risk_funds.append(fc)
                # Flag short tenure
                tenure_yrs = summary.get("tenure_years", summary.get("tenure"))
                if tenure_yrs and isinstance(tenure_yrs, (int, float)) and float(tenure_yrs) < 2.0:
                    if fc not in change_risk_funds:
                        change_risk_funds.append(fc)
    if not profiles_found:
        return None
    result: dict[str, Any] = {
        "funds_with_profiles": sorted(profiles_found.keys()),
        "manager_profiles": profiles_found,
    }
    if change_risk_funds:
        result["manager_change_risk_funds"] = change_risk_funds
        result["manager_risk_warning"] = (
            f"Fund(s) {', '.join(change_risk_funds)} have elevated "
            f"manager-change risk or short manager tenure"
        )
    return result


def add_missing_optional_warnings(
    warnings: list[str],
    fund_codes: list[str],
    *,
    benchmarks: dict[str, Any],
    benchmark_history: dict[str, Any],
    peer_group: dict[str, Any],
    factor_exposures: dict[str, Any],
    manager_profiles: dict[str, Any],
    fee_schedules: dict[str, Any],
    redemption_rules: dict[str, Any],
) -> None:
    """Emit warnings when host provides optional data dimensions but data is missing
    or only partially available for the requested fund codes."""
    # Benchmark: host provided benchmarks/history but some funds are not covered
    if benchmarks:
        benchmark_codes = {str(code) for code in benchmarks.keys()}
        fund_code_set = {str(code) for code in fund_codes}
        if benchmark_codes & fund_code_set:
            missing_bm = [fc for fc in fund_codes if fc not in benchmark_codes]
        else:
            missing_bm = []
        if missing_bm:
            warnings.append(
                f"Benchmark data missing for fund(s): {', '.join(missing_bm)}; "
                f"benchmark comparison incomplete"
            )

    if peer_group:
        missing_peer = [fc for fc in fund_codes if fc not in peer_group]
        if missing_peer:
            warnings.append(
                f"Peer group data missing for fund(s): {', '.join(missing_peer)}; "
                f"peer comparison partial"
            )

    if factor_exposures:
        covered_codes: set[str] = set()
        for exposure_data in factor_exposures.values():
            if isinstance(exposure_data, dict):
                covered_codes.update(exposure_data.keys())
        missing_factor = [fc for fc in fund_codes if fc not in covered_codes]
        if missing_factor and covered_codes:
            warnings.append(
                f"Factor exposure data missing for fund(s): {', '.join(missing_factor)}"
            )

    if manager_profiles:
        missing_mgr = [fc for fc in fund_codes if fc not in manager_profiles]
        if missing_mgr:
            warnings.append(
                f"Manager profile missing for fund(s): {', '.join(missing_mgr)}"
            )

    if fee_schedules:
        missing_fee = [fc for fc in fund_codes if fc not in fee_schedules]
        if missing_fee:
            warnings.append(
                f"Fee schedule missing for fund(s): {', '.join(missing_fee)}"
            )

    if redemption_rules:
        missing_rule = [fc for fc in fund_codes if fc not in redemption_rules]
        if missing_rule:
            warnings.append(
                f"Redemption rules missing for fund(s): {', '.join(missing_rule)}"
            )
