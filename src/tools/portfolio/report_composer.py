"""Deterministic personal fund report composer.

The composer turns FundAnalysisSkill artifacts into host-displayable report
sections. It is pure, JSON-serializable, and does not make provider, network,
LLM, or decision-support calls.
"""

from __future__ import annotations

from typing import Any


SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("executive_summary", "Executive summary"),
    ("portfolio_snapshot", "Portfolio snapshot"),
    ("pnl_and_cost_basis", "PnL and cost basis"),
    ("position_contribution", "Position contribution"),
    ("allocation_and_exposure", "Allocation and exposure"),
    ("risk_flags", "Risk flags"),
    ("performance_and_nav", "Performance and NAV"),
    ("benchmark_and_peer", "Benchmark and peer"),
    ("benchmark_divergence", "Benchmark divergence"),
    ("factor_and_style", "Factor and style"),
    ("fees_and_redemption", "Fees and redemption"),
    ("manager_and_fund_profile", "Manager and fund profile"),
    ("dca_and_trade_budget", "DCA and trade budget"),
    ("professional_diagnostics", "Professional diagnostics"),
    ("profit_protection", "Profit protection"),
    ("right_side_confirmation", "Right-side confirmation"),
    ("event_hype_failure", "Event hype failure"),
    ("cash_deployment", "Cash deployment"),
    ("evidence_status", "Evidence status"),
    ("action_watchlist", "Action watchlist"),
    ("missing_data", "Missing data"),
    ("suggested_next_checks", "Suggested next checks"),
    ("uncertainty_note", "Uncertainty note"),
    ("rebalance_plan", "Rebalance plan"),
    ("research_query_plan", "Research query plan"),
    ("data_completeness_and_limitations", "Data completeness and limitations"),
    ("evidence_appendix", "Evidence appendix"),
)

ZH_CN_SECTION_TITLES: dict[str, str] = {
    "executive_summary": "组合概览",
    "portfolio_snapshot": "持仓快照",
    "pnl_and_cost_basis": "收益与成本",
    "position_contribution": "仓位贡献",
    "allocation_and_exposure": "配置与暴露",
    "risk_flags": "风险提示",
    "performance_and_nav": "净值与表现",
    "benchmark_and_peer": "基准与同类",
    "benchmark_divergence": "基准偏离",
    "factor_and_style": "风格因子",
    "fees_and_redemption": "赎回费与持有期",
    "manager_and_fund_profile": "基金资料与经理",
    "dca_and_trade_budget": "定投与交易预算",
    "professional_diagnostics": "专业诊断",
    "profit_protection": "盈利保护",
    "right_side_confirmation": "右侧确认",
    "event_hype_failure": "事件催化检验",
    "cash_deployment": "现金与低风险仓位",
    "evidence_status": "证据状态",
    "action_watchlist": "操作观察清单",
    "missing_data": "缺失数据",
    "suggested_next_checks": "后续检查项",
    "uncertainty_note": "不确定性说明",
    "rebalance_plan": "再平衡分析",
    "research_query_plan": "研究查询计划",
    "data_completeness_and_limitations": "数据限制",
    "evidence_appendix": "证据附录",
}

VALID_STATUSES = {"OK", "PARTIAL", "MISSING"}


def compose_personal_fund_report(
    artifacts: dict[str, Any],
    warnings: list[str] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose deterministic report sections from FundAnalysisSkill artifacts."""

    artifacts = artifacts if isinstance(artifacts, dict) else {}
    options = options if isinstance(options, dict) else {}
    report = _as_dict(artifacts.get("fund_analysis_report"))
    data_completeness = _as_dict(artifacts.get("data_completeness") or report.get("data_completeness"))
    analysis_coverage = _as_dict(artifacts.get("analysis_coverage") or report.get("analysis_coverage"))
    report_limitations = _string_list(
        artifacts.get("report_limitations") or report.get("report_limitations") or []
    )
    combined_warnings = _unique_strings([*(warnings or []), *(_string_list(artifacts.get("warnings") or []))])
    language = _select_language(options)
    include_v1_sections = _include_v1_sections(options, language)

    context = {
        "artifacts": artifacts,
        "report": report,
        "data_completeness": data_completeness,
        "analysis_coverage": analysis_coverage,
        "report_limitations": report_limitations,
        "warnings": combined_warnings,
        "language": language,
    }

    sections = [
        _build_executive_summary(context),
        _build_portfolio_snapshot(context),
        _build_pnl_and_cost_basis(context),
    ]
    if include_v1_sections:
        sections.append(_build_position_contribution(context))
    sections.extend([
        _build_allocation_and_exposure(context),
        _build_risk_flags(context),
        _build_performance_and_nav(context),
        _build_benchmark_and_peer(context),
    ])
    if include_v1_sections:
        sections.append(_build_benchmark_divergence(context))
    sections.extend([
        _build_factor_and_style(context),
        _build_fees_and_redemption(context),
        _build_manager_and_fund_profile(context),
        _build_dca_and_trade_budget(context),
        _build_professional_diagnostics(context),
    ])
    if include_v1_sections:
        sections.extend([
            _build_profit_protection(context),
            _build_right_side_confirmation(context),
            _build_event_hype_failure(context),
            _build_cash_deployment(context),
            _build_evidence_status(context),
            _build_action_watchlist(context),
            _build_missing_data(context),
            _build_suggested_next_checks(context),
            _build_uncertainty_note(context),
        ])
    sections.extend([
        _build_rebalance_plan(context),
        _build_research_query_plan(context),
        _build_data_completeness_and_limitations(context),
        _build_evidence_appendix(context),
    ])
    sections = _localize_sections(sections, language)
    quality_gate = _build_quality_gate(data_completeness, sections, options)

    return {
        "report_sections": sections,
        "report_outline": [
            {
                "id": section["id"],
                "title": section["title"],
                "status": section["status"],
            }
            for section in sections
        ],
        "quality_gate": quality_gate,
        "warnings": combined_warnings,
    }


def render_report_markdown(report_sections: list[dict[str, Any]] | dict[str, Any]) -> str:
    """Render deterministic Markdown from composed report sections."""

    if isinstance(report_sections, dict):
        sections = report_sections.get("report_sections", [])
    else:
        sections = report_sections
    if not isinstance(sections, list):
        sections = []

    language = "zh-CN" if any(
        isinstance(section, dict) and section.get("language") == "zh-CN"
        for section in sections
    ) else "en"
    title = "个人基金报告" if language == "zh-CN" else "Personal fund report"
    lines: list[str] = [f"# {title}", ""]
    global_limitations: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "Untitled section"))
        status = str(section.get("status", "MISSING"))
        lines.append(f"## {title} [{status}]")
        bullets = _string_list(section.get("bullets") or [])
        if bullets:
            for bullet in bullets:
                lines.append(f"- {bullet}")
        else:
            lines.append("- No section content available from provided artifacts.")
        limitations = _string_list(section.get("limitations") or [])
        if limitations:
            lines.append("")
            lines.append("Limitations:")
            for limitation in limitations:
                lines.append(f"- {limitation}")
        if status in {"PARTIAL", "MISSING"}:
            for limitation in limitations:
                item = f"{title}: {limitation}"
                if item not in global_limitations:
                    global_limitations.append(item)
        lines.append("")
    if any(
        isinstance(section, dict)
        and str(section.get("status", "MISSING")) in {"PARTIAL", "MISSING"}
        for section in sections
    ):
        lines.append("## Limitations")
        lines.append("")
        for limitation in global_limitations:
            lines.append(f"- {limitation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_executive_summary(context: dict[str, Any]) -> dict[str, Any]:
    portfolio = _portfolio_summary(context)
    completeness = context["data_completeness"]
    limitations = []
    bullets: list[str] = []
    if portfolio:
        bullets.append(
            "Portfolio value "
            f"{_money(portfolio.get('total_value'))} across "
            f"{int(portfolio.get('position_count') or 0)} position(s); "
            f"cash {_money(portfolio.get('cash_available'))}."
        )
    else:
        limitations.append("Portfolio summary artifact is missing.")

    if completeness:
        bullets.append(
            "Data completeness grade "
            f"{completeness.get('grade', 'D')} with score "
            f"{_fixed(completeness.get('score'), 3)}."
        )
    else:
        limitations.append("Data completeness artifact is missing.")

    risk_flags = _as_list(context["artifacts"].get("risk_flags") or context["report"].get("risk_flags"))
    if risk_flags:
        bullets.append(f"Risk scan surfaced {len(risk_flags)} flag(s) from available inputs.")
    elif "risk_flags" in context["artifacts"] or "risk_flags" in context["report"]:
        bullets.append("Risk scan surfaced no flags from available inputs.")

    bullets.append("No formal decision generated; call decision-support for formal action.")

    status = "OK" if portfolio and completeness.get("grade") in ("A", "B") else "PARTIAL" if portfolio else "MISSING"
    return _section(
        "executive_summary",
        status,
        bullets,
        ["portfolio_summary", "data_completeness", "risk_flags"],
        limitations,
    )


def _build_portfolio_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    portfolio = _portfolio_summary(context)
    positions = _as_dict(context["artifacts"].get("position_summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if portfolio:
        as_of = portfolio.get("as_of_date") or "unspecified date"
        bullets.append(
            f"As of {as_of}, total value is {_money(portfolio.get('total_value'))} "
            f"with {_money(portfolio.get('cash_available'))} cash."
        )
        weights = _as_dict(portfolio.get("position_weights"))
        if weights:
            fund_code, weight = _largest_weight(weights)
            bullets.append(f"Largest position is {fund_code} at {_pct(weight)} of portfolio value.")
    else:
        limitations.append("Portfolio snapshot is unavailable.")

    if positions:
        bullets.append(f"Position detail is available for {len(positions)} fund(s).")
    else:
        limitations.append("Position summary artifact is missing.")

    status = "OK" if portfolio and positions else "PARTIAL" if portfolio else "MISSING"
    return _section("portfolio_snapshot", status, bullets, ["portfolio_summary", "position_summary"], limitations)


def _build_pnl_and_cost_basis(context: dict[str, Any]) -> dict[str, Any]:
    pnl = _as_dict(context["artifacts"].get("pnl_summary") or context["report"].get("pnl_summary"))
    cost_basis = _as_dict(context["artifacts"].get("cost_basis_summary") or context["report"].get("cost_basis_summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if pnl:
        bullets.append(
            "Unrealized PnL is "
            f"{_money(pnl.get('unrealized_pnl'))} "
            f"({_pct(pnl.get('unrealized_pnl_pct'))}) on total cost {_money(pnl.get('total_cost'))}."
        )
        positions = _as_dict(pnl.get("positions"))
        if positions:
            bullets.append(f"Position-level PnL is available for {len(positions)} fund(s).")
    else:
        limitations.append("PnL summary is unavailable from provided artifacts.")

    if cost_basis:
        bullets.append(f"Transaction-derived cost basis is available for {len(cost_basis)} fund(s).")
    elif pnl:
        limitations.append("Transaction-level cost-basis summary is absent; PnL uses provided position cost fields.")

    status = "OK" if pnl else "PARTIAL" if cost_basis else "MISSING"
    return _section("pnl_and_cost_basis", status, bullets, ["pnl_summary", "cost_basis_summary"], limitations)


def _build_position_contribution(context: dict[str, Any]) -> dict[str, Any]:
    contribution = _artifact(context, "position_contribution")
    positions = _as_list(contribution.get("positions"))
    summary = _as_dict(contribution.get("summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if positions:
        bullets.append(f"Position contribution covers {len(positions)} fund(s).")
        largest_value = summary.get("largest_value_position")
        if largest_value:
            bullets.append(f"Largest value position: {largest_value}.")
        largest_profit = summary.get("largest_profit_contributor")
        if largest_profit:
            bullets.append(f"Largest profit contributor: {largest_profit}.")
        largest_loss = summary.get("largest_loss_contributor")
        if largest_loss:
            bullets.append(f"Largest loss contributor: {largest_loss}.")
    else:
        limitations.append("Position contribution artifact is missing.")

    status = "OK" if positions else "MISSING"
    return _section(
        "position_contribution",
        status,
        bullets,
        ["position_contribution"],
        limitations,
    )


def _build_allocation_and_exposure(context: dict[str, Any]) -> dict[str, Any]:
    exposure = _as_dict(context["artifacts"].get("exposure_summary") or context["report"].get("exposure_summary"))
    concentration = _as_dict(context["report"].get("concentration"))
    bullets: list[str] = []
    limitations: list[str] = []

    if exposure:
        for key in ("fund_type_exposure", "industry_exposure", "theme_exposure"):
            values = _as_dict(exposure.get(key))
            if values:
                top_key, top_value = _largest_weight(values)
                bullets.append(f"Top {key.replace('_', ' ')} is {top_key} at {_pct(top_value)}.")
    else:
        limitations.append("Exposure summary is unavailable.")

    if concentration:
        bullets.append(
            "Single-fund max weight is "
            f"{_pct(concentration.get('single_fund_max_weight'))}; "
            f"HHI is {_fixed(concentration.get('hhi'), 6)}."
        )

    status = "OK" if exposure else "PARTIAL" if concentration else "MISSING"
    return _section("allocation_and_exposure", status, bullets, ["exposure_summary", "concentration"], limitations)


def _build_risk_flags(context: dict[str, Any]) -> dict[str, Any]:
    risk_flags = _as_list(context["artifacts"].get("risk_flags") or context["report"].get("risk_flags"))
    completeness = context["data_completeness"]
    missing = set(_string_list(completeness.get("missing_sections") or []))
    limitations: list[str] = []
    bullets: list[str] = []

    if risk_flags:
        by_severity = _risk_counts_by_severity(risk_flags)
        bullets.append(f"Risk flags by severity: {_format_counts(by_severity)}.")
    elif "risk_flags" in context["artifacts"] or "risk_flags" in context["report"]:
        bullets.append("No risk flags were generated from available inputs.")
    else:
        limitations.append("Risk flag artifact is missing.")

    if "Risk Profile" in missing:
        limitations.append("Risk profile is missing; risk checks use default assumptions.")
    if "Constraints" in missing:
        limitations.append("Constraints are missing; constraint-sensitive risk checks are partial.")

    base_status = "OK" if "risk_flags" in context["artifacts"] or "risk_flags" in context["report"] else "MISSING"
    status = "PARTIAL" if base_status == "OK" and limitations else base_status
    return _section("risk_flags", status, bullets, ["risk_flags", "data_completeness"], limitations)


def _build_performance_and_nav(context: dict[str, Any]) -> dict[str, Any]:
    fund_metrics = _as_dict(context["report"].get("fund_metrics"))
    coverage = context["analysis_coverage"]
    bullets: list[str] = []
    limitations: list[str] = []

    if fund_metrics:
        bullets.append(f"NAV-derived metrics are available for {len(fund_metrics)} fund(s).")
        best = _best_total_return(fund_metrics)
        if best:
            bullets.append(f"Highest total return in provided NAV history is {best[0]} at {_pct(best[1])}.")
    else:
        limitations.append("Fund metrics are unavailable because NAV history is missing or incomplete.")

    perf_status = coverage.get("performance")
    if perf_status == "available" and fund_metrics:
        status = "OK"
    elif perf_status in ("partial", "available") or fund_metrics:
        status = "PARTIAL"
    else:
        status = "MISSING"
    return _section("performance_and_nav", status, bullets, ["fund_analysis_report.fund_metrics"], limitations)


def _build_benchmark_and_peer(context: dict[str, Any]) -> dict[str, Any]:
    benchmark = _as_dict(context["artifacts"].get("benchmark_summary") or context["report"].get("benchmark_summary"))
    peer = _as_dict(context["artifacts"].get("peer_summary") or context["report"].get("peer_summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if benchmark:
        comparisons = _as_list(benchmark.get("comparison"))
        if comparisons:
            bullets.append(f"Benchmark gap comparison is available for {len(comparisons)} fund-benchmark pair(s).")
        else:
            bullets.append("Benchmark data is present, but no comparable return gap was derived.")
    else:
        limitations.append("Benchmark data is missing; no benchmark comparison is fabricated.")

    if peer:
        rankings = _as_list(peer.get("rankings"))
        if rankings:
            bullets.append(f"Peer ranking data is available for {len(rankings)} fund(s).")
        else:
            bullets.append("Peer group data is present, but rank or percentile was not provided.")
    else:
        limitations.append("Peer group data is missing; no peer ranking is fabricated.")

    status = "OK" if benchmark and peer else "PARTIAL" if benchmark or peer else "MISSING"
    return _section("benchmark_and_peer", status, bullets, ["benchmark_summary", "peer_summary"], limitations)


def _build_benchmark_divergence(context: dict[str, Any]) -> dict[str, Any]:
    divergence = _artifact(context, "benchmark_divergence_diagnostics")
    items = _as_list(divergence.get("items"))
    summary = _as_dict(divergence.get("summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if items:
        bullets.append(f"Benchmark divergence reviewed {len(items)} fund(s).")
        if summary.get("has_severe_underperformance"):
            bullets.append("Severe benchmark underperformance is present in provided data.")
        elif summary.get("has_benchmark_divergence"):
            bullets.append("Benchmark divergence is present in provided data.")
        else:
            bullets.append("No severe benchmark divergence was detected from provided data.")
    else:
        limitations.append("Benchmark divergence diagnostics are missing.")

    return _section(
        "benchmark_divergence",
        "OK" if items else "MISSING",
        bullets,
        ["benchmark_divergence_diagnostics"],
        limitations,
    )


def _build_factor_and_style(context: dict[str, Any]) -> dict[str, Any]:
    factor = _as_dict(context["artifacts"].get("factor_summary") or context["report"].get("factor_summary"))
    bullets: list[str] = []
    limitations: list[str] = []
    if factor:
        factors = _string_list(factor.get("factors") or [])
        if factors:
            bullets.append(f"Host-provided factor dimensions: {', '.join(factors)}.")
        warnings = _string_list(factor.get("concentration_warnings") or [])
        bullets.extend(warnings)
    else:
        limitations.append("Factor exposure data is missing; no style exposure is fabricated.")
    return _section("factor_and_style", "OK" if factor else "MISSING", bullets, ["factor_summary"], limitations)


def _build_fees_and_redemption(context: dict[str, Any]) -> dict[str, Any]:
    fee = _as_dict(context["artifacts"].get("fee_summary") or context["report"].get("fee_summary"))
    redemption = _as_dict(context["artifacts"].get("redemption_summary") or context["report"].get("redemption_summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if fee:
        funds = _string_list(fee.get("funds_with_fees") or [])
        bullets.append(f"Fee schedule is available for {len(funds)} fund(s).")
        warning = fee.get("fee_warning")
        if isinstance(warning, str):
            bullets.append(warning)
    else:
        limitations.append("Fee schedule is missing; fee analysis is not fabricated.")

    if redemption:
        funds = _string_list(redemption.get("funds_with_rules") or [])
        bullets.append(f"Redemption rules are available for {len(funds)} fund(s).")
        bullets.extend(_string_list(redemption.get("warnings") or []))
    else:
        limitations.append("Redemption rules are missing; liquidity restrictions are not fabricated.")

    status = "OK" if fee and redemption else "PARTIAL" if fee or redemption else "MISSING"
    return _section("fees_and_redemption", status, bullets, ["fee_summary", "redemption_summary"], limitations)


def _build_manager_and_fund_profile(context: dict[str, Any]) -> dict[str, Any]:
    manager = _as_dict(context["artifacts"].get("manager_summary") or context["report"].get("manager_summary"))
    completeness = context["data_completeness"]
    available = set(_string_list(completeness.get("available_sections") or []))
    bullets: list[str] = []
    limitations: list[str] = []

    if manager:
        funds = _string_list(manager.get("funds_with_profiles") or [])
        bullets.append(f"Manager profile is available for {len(funds)} fund(s).")
        warning = manager.get("manager_risk_warning")
        if isinstance(warning, str):
            bullets.append(warning)
        status = "OK"
    elif "Fund Profiles" in available:
        bullets.append("Fund profile data is present, but manager profile details were not provided.")
        limitations.append("Manager tenure and manager-change analysis are unavailable.")
        status = "PARTIAL"
    else:
        limitations.append("Fund profile and manager profile data are missing.")
        status = "MISSING"

    return _section("manager_and_fund_profile", status, bullets, ["manager_summary", "data_completeness"], limitations)


def _build_dca_and_trade_budget(context: dict[str, Any]) -> dict[str, Any]:
    report = context["report"]
    trade_budget = _as_dict(report.get("trade_budget"))
    short_term_budget = _as_dict(context["artifacts"].get("short_term_trade_budget") or report.get("short_term_budget"))
    dca_review = _as_dict(context["artifacts"].get("dca_plan_review") or report.get("dca_review"))
    bullets: list[str] = []
    limitations: list[str] = []

    if trade_budget:
        bullets.append(
            "Trade budget: max buy "
            f"{_money(trade_budget.get('max_buy_amount'))}, max sell "
            f"{_money(trade_budget.get('max_sell_amount'))}, liquidity reserve "
            f"{_money(trade_budget.get('liquidity_reserve'))}."
        )
    else:
        limitations.append("Trade budget artifact is missing.")

    if short_term_budget:
        bullets.append("Short-term trade budget usage is available.")
    if dca_review:
        suggestions = _as_list(dca_review.get("suggestions"))
        bullets.append(f"DCA review includes {len(suggestions)} suggestion(s).")
    elif trade_budget:
        limitations.append("DCA plan review is absent; host did not provide DCA inputs.")

    status = "OK" if trade_budget and dca_review else "PARTIAL" if trade_budget or short_term_budget else "MISSING"
    return _section("dca_and_trade_budget", status, bullets, ["trade_budget", "short_term_trade_budget", "dca_plan_review"], limitations)


def _build_professional_diagnostics(context: dict[str, Any]) -> dict[str, Any]:
    artifacts = context["artifacts"]
    prof_diag = _as_dict(artifacts.get("professional_diagnostics"))
    bullets: list[str] = []
    limitations: list[str] = []

    if not prof_diag:
        limitations.append(
            "Professional diagnostics require host-supplied transactions, holdings, "
            "fund profiles, redemption rules, risk constraints, DCA plans, or budget data."
        )
        return _section(
            "professional_diagnostics", "MISSING", bullets,
            ["professional_diagnostics"], limitations,
        )

    redemption = _as_dict(prof_diag.get("redemption_fee_risk"))
    if redemption:
        affected = _as_list(redemption.get("affected_funds"))
        if affected:
            highest = redemption.get("summary", {}).get("highest_fee_pct")
            fee_str = f"highest host-supplied fee is {highest * 100:.1f}%" if highest is not None else ""
            bullets.append(
                f"Short-holding redemption fee scan found {len(affected)} "
                f"affected fund/transaction item(s); {fee_str}."
            )
            # List first 3 affected funds
            for item in affected[:3]:
                bullets.append(
                    f"Fund {item.get('fund_code', '')} ({item.get('fund_name', '')}): "
                    f"recent buy {item.get('estimated_recent_amount', 0):.0f} "
                    f"within {item.get('threshold_days', '')}-day fee window."
                )

    overlap = _as_dict(prof_diag.get("overlap_diagnostics"))
    if overlap:
        holdings_overlap = _as_list(overlap.get("overlapping_holdings"))
        themes_overlap = _as_list(overlap.get("overlapping_themes"))
        regions_overlap = _as_list(overlap.get("overlapping_regions"))
        total = len(holdings_overlap) + len(themes_overlap) + len(regions_overlap)
        if total > 0:
            top = overlap.get("summary", {}).get("highest_overlap_theme", "")
            top_str = f"Highest: {top}." if top else ""
            bullets.append(f"Overlap scan found {total} overlapping holding/theme/region item(s). {top_str}")

    theme_over = _as_dict(prof_diag.get("theme_overweight_diagnostics"))
    if theme_over:
        over_list = _as_list(theme_over.get("overweight_themes"))
        if over_list:
            summary = theme_over.get("summary", {})
            bullets.append(
                f"Theme overweight scan found {len(over_list)} theme(s) near or above "
                f"host-supplied limit. Max: {summary.get('max_theme', '')} "
                f"at {summary.get('max_theme_weight', 0) * 100:.1f}%."
            )

    dca = _as_dict(prof_diag.get("dca_drawdown_diagnostics"))
    if dca:
        reviewed = _as_list(dca.get("reviewed_funds"))
        summary = dca.get("summary", {})
        bullets.append(
            f"DCA drawdown scan reviewed {summary.get('reviewed_count', 0)} plan(s); "
            f"{summary.get('funds_with_drawdown', 0)} fund(s) are under drawdown. "
            f"Formal DCA changes require decision_support."
        )

    cash = _as_dict(prof_diag.get("cash_budget_diagnostics"))
    if cash:
        bullets.append(f"Cash ratio is {cash.get('cash_ratio', 0) * 100:.1f}%.")
        gap = cash.get("reserve_gap")
        if gap is not None:
            bullets.append(f"Liquidity reserve gap: {gap:,.0f}.")
        status = cash.get("short_term_budget_status", "ok")
        bullets.append(f"Short-term trade budget status: {status}.")

    prof_warnings = _string_list(prof_diag.get("professional_warnings"))
    if prof_warnings:
        # Show up to 5 unique warnings
        unique_warns = []
        for w in prof_warnings:
            if w not in unique_warns:
                unique_warns.append(w)
        for w in unique_warns[:5]:
            bullets.append(w)

    status = "PARTIAL" if prof_warnings else "OK"
    return _section(
        "professional_diagnostics", status, bullets,
        [
            "professional_diagnostics",
            "redemption_fee_risk",
            "overlap_diagnostics",
            "theme_overweight_diagnostics",
            "dca_drawdown_diagnostics",
            "cash_budget_diagnostics",
        ],
        limitations,
    )


def _build_profit_protection(context: dict[str, Any]) -> dict[str, Any]:
    diagnostics = _artifact(context, "profit_protection_diagnostics")
    items = _as_list(diagnostics.get("items"))
    summary = _as_dict(diagnostics.get("summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if items:
        bullets.append(f"Profit protection reviewed {len(items)} position(s).")
        high_profit = [
            item for item in items
            if isinstance(item, dict) and item.get("profit_level") in {"high", "very_high"}
        ]
        if high_profit:
            bullets.append(f"High-profit watchlist contains {len(high_profit)} position(s).")
        action_counts = _as_dict(summary.get("suggested_action_counts"))
        if action_counts:
            bullets.append(f"Analysis-only action distribution: {_format_counts(action_counts)}.")
    else:
        limitations.append("Profit protection diagnostics are missing.")

    return _section(
        "profit_protection",
        "OK" if items else "MISSING",
        bullets,
        ["profit_protection_diagnostics"],
        limitations,
    )


def _build_right_side_confirmation(context: dict[str, Any]) -> dict[str, Any]:
    diagnostics = _artifact(context, "right_side_confirmation_diagnostics")
    items = _as_list(diagnostics.get("items"))
    summary = _as_dict(diagnostics.get("summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if items:
        applicable = [
            item for item in items
            if isinstance(item, dict) and item.get("applicability") != "not_applicable"
        ]
        confirmed = [
            item for item in applicable
            if isinstance(item, dict) and item.get("right_side_confirmed") is True
        ]
        bullets.append(
            f"Right-side confirmation applies to {len(applicable)} drawdown position(s); "
            f"{len(confirmed)} confirmed."
        )
        if summary.get("needs_more_evidence"):
            bullets.append("Fresh NAV, benchmark, news, or sentiment evidence is needed before action.")
    else:
        limitations.append("Right-side confirmation diagnostics are missing.")

    return _section(
        "right_side_confirmation",
        "OK" if items else "MISSING",
        bullets,
        ["right_side_confirmation_diagnostics"],
        limitations,
    )


def _build_event_hype_failure(context: dict[str, Any]) -> dict[str, Any]:
    diagnostics = _artifact(context, "event_hype_failure_diagnostics")
    items = _as_list(diagnostics.get("items"))
    summary = _as_dict(diagnostics.get("summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if items:
        failed = [
            item for item in items
            if isinstance(item, dict) and item.get("hype_failed") is True
        ]
        bullets.append(f"Event catalyst review covers {len(items)} event(s).")
        if failed:
            bullets.append(f"Event hype failure detected for {len(failed)} event(s).")
        else:
            bullets.append("No event hype failure was concluded from available evidence.")
        high_risk = _string_list(summary.get("high_risk_events") or [])
        if high_risk:
            bullets.append(f"High-risk event markers: {', '.join(high_risk)}.")
    else:
        limitations.append("Event hype diagnostics are missing or no host event metadata was provided.")

    return _section(
        "event_hype_failure",
        "OK" if items else "MISSING",
        bullets,
        ["event_hype_failure_diagnostics"],
        limitations,
    )


def _build_cash_deployment(context: dict[str, Any]) -> dict[str, Any]:
    diagnostics = _artifact(context, "cash_deployment_diagnostics")
    summary = _as_dict(diagnostics.get("summary"))
    bullets: list[str] = []
    limitations: list[str] = []

    if summary:
        bullets.append(
            "Cash-like weight "
            f"{_pct(summary.get('cash_like_weight'))}; deployment readiness "
            f"{summary.get('deployment_readiness', 'unknown')}."
        )
        bullets.append(
            f"Cash accounting basis: {summary.get('cash_accounting_basis', 'unspecified')}."
        )
        deployable = summary.get("estimated_deployable_cash")
        if deployable is not None:
            bullets.append(f"Estimated deployable cash: {_money(deployable)}.")
    else:
        limitations.append("Cash deployment diagnostics are missing.")

    return _section(
        "cash_deployment",
        "OK" if summary else "MISSING",
        bullets,
        ["cash_deployment_diagnostics"],
        limitations,
    )


def _build_evidence_status(context: dict[str, Any]) -> dict[str, Any]:
    plan = _artifact(context, "analysis_plan")
    gap = _artifact(context, "evidence_gap_diagnostics")
    redemption = _artifact(context, "redemption_fee_risk")
    bullets: list[str] = []
    limitations: list[str] = []

    if plan:
        ready = bool(plan.get("decision_support_ready"))
        bullets.append(f"decision_support_ready: {ready}.")
        blockers = _string_list(plan.get("blockers") or [])
        if blockers:
            bullets.append(f"Formal decision blockers: {', '.join(blockers)}.")
        warnings = _string_list(plan.get("warnings") or [])
        if warnings:
            bullets.append(f"Analysis warnings: {', '.join(warnings[:6])}.")
    else:
        limitations.append("analysis_plan artifact is missing.")

    missing = _missing_gap_codes(gap)
    if missing:
        bullets.append(f"Missing evidence: {', '.join(missing)}.")
    if redemption:
        if redemption.get("has_blocker"):
            bullets.append("Fee blocker is active from host-provided redemption rules.")
        elif redemption.get("has_warning"):
            bullets.append("Fee warning is present from host-provided redemption rules.")

    status = "OK" if plan and not missing else "PARTIAL" if plan or gap else "MISSING"
    return _section(
        "evidence_status",
        status,
        bullets,
        ["analysis_plan", "evidence_gap_diagnostics", "redemption_fee_risk"],
        limitations,
    )


def _build_action_watchlist(context: dict[str, Any]) -> dict[str, Any]:
    plan = _as_dict(context["artifacts"].get("suggested_rebalance_plan"))
    analysis_plan = _artifact(context, "analysis_plan")
    bullets: list[str] = []
    limitations: list[str] = []

    if plan:
        trades = _as_list(plan.get("suggested_trade_plan"))
        bullets.append(f"Action watchlist contains {len(trades)} simulated trade leg(s).")
        bullets.append("Formal action requires decision_support; this section is analysis-only.")
    else:
        limitations.append("Suggested rebalance plan is missing.")

    blockers = _string_list(analysis_plan.get("blockers") or [])
    if blockers:
        bullets.append(f"Do not enter formal active decision until blockers clear: {', '.join(blockers)}.")

    return _section(
        "action_watchlist",
        "OK" if plan else "PARTIAL" if blockers else "MISSING",
        bullets,
        ["suggested_rebalance_plan", "analysis_plan"],
        limitations,
    )


def _build_missing_data(context: dict[str, Any]) -> dict[str, Any]:
    plan = _artifact(context, "analysis_plan")
    gap = _artifact(context, "evidence_gap_diagnostics")
    missing = _string_list(plan.get("missing_inputs") or []) or _missing_gap_codes(gap)
    bullets: list[str] = []
    limitations: list[str] = []

    if missing:
        bullets.append(f"Missing data groups: {', '.join(missing)}.")
    elif plan or gap:
        bullets.append("No required missing data groups were reported.")
    else:
        limitations.append("Missing-data diagnostics are unavailable.")

    details = _as_list(gap.get("details"))
    for detail in details[:5]:
        if isinstance(detail, dict):
            code = detail.get("code", "unknown")
            next_data = detail.get("recommended_next_data", "")
            bullets.append(f"{code}: next data {next_data}.")

    return _section(
        "missing_data",
        "PARTIAL" if missing else "OK" if plan or gap else "MISSING",
        bullets,
        ["analysis_plan", "evidence_gap_diagnostics"],
        limitations,
    )


def _build_suggested_next_checks(context: dict[str, Any]) -> dict[str, Any]:
    plan = _artifact(context, "analysis_plan")
    next_data = _string_list(plan.get("next_data_to_fetch") or [])
    bullets: list[str] = []
    limitations: list[str] = []

    if next_data:
        bullets.append(f"Next data to fetch: {', '.join(next_data)}.")
    elif plan:
        bullets.append("No additional next-data items were requested by analysis_plan.")
    else:
        limitations.append("analysis_plan is missing; no next checks can be derived.")

    return _section(
        "suggested_next_checks",
        "PARTIAL" if next_data else "OK" if plan else "MISSING",
        bullets,
        ["analysis_plan.next_data_to_fetch"],
        limitations,
    )


def _build_uncertainty_note(context: dict[str, Any]) -> dict[str, Any]:
    limitations = list(context["report_limitations"])
    bullets = [
        "This conclusion is based on host-provided data and does not include live market fetching.",
        "No formal decision generated; call decision-support for formal action.",
    ]
    if limitations:
        bullets.append(f"Report limitations count: {len(limitations)}.")

    return _section(
        "uncertainty_note",
        "PARTIAL" if limitations else "OK",
        bullets,
        ["report_limitations", "report_sections"],
        limitations[:5],
    )


def _build_rebalance_plan(context: dict[str, Any]) -> dict[str, Any]:
    plan = _as_dict(context["artifacts"].get("suggested_rebalance_plan"))
    bullets: list[str] = []
    limitations: list[str] = []
    if plan:
        trades = _as_list(plan.get("suggested_trade_plan"))
        bullets.append(
            f"Rebalance simulation produced {len(trades)} trade leg(s) "
            f"with total trade amount {_money(plan.get('total_trade_amount'))}."
        )
        bullets.extend(_string_list(plan.get("warnings") or []))
        status = "OK"
    else:
        limitations.append("Rebalance plan is missing; target weights or constraints may be unavailable.")
        status = "MISSING"
    return _section("rebalance_plan", status, bullets, ["suggested_rebalance_plan"], limitations)


def _build_research_query_plan(context: dict[str, Any]) -> dict[str, Any]:
    plan = _as_dict(context["artifacts"].get("research_query_plan") or context["report"].get("research_query_plan"))
    coverage = context["analysis_coverage"]
    bullets: list[str] = []
    limitations: list[str] = []
    if plan:
        news = _as_list(plan.get("news_queries"))
        sentiment = _as_list(plan.get("sentiment_queries"))
        bullets.append(f"Research query plan includes {len(news)} news query(ies) and {len(sentiment)} sentiment query(ies).")
        status = "OK"
    else:
        research_status = coverage.get("research_plan")
        if research_status == "not_requested":
            limitations.append("Research planning was not requested by the host.")
            status = "MISSING"
        elif research_status == "missing_inputs":
            limitations.append("Research planning was requested, but required inputs were missing.")
            status = "PARTIAL"
        else:
            limitations.append("Research query plan is missing.")
            status = "MISSING"
    return _section("research_query_plan", status, bullets, ["research_query_plan"], limitations)


def _build_data_completeness_and_limitations(context: dict[str, Any]) -> dict[str, Any]:
    completeness = context["data_completeness"]
    limitations = list(context["report_limitations"])
    bullets: list[str] = []
    if completeness:
        bullets.append(
            f"Completeness grade {completeness.get('grade', 'D')} "
            f"with score {_fixed(completeness.get('score'), 3)}."
        )
        missing = _string_list(completeness.get("missing_sections") or [])
        if missing:
            bullets.append(f"Missing data groups: {', '.join(missing)}.")
        optional_missing = _string_list(completeness.get("optional_missing") or [])
        if optional_missing:
            bullets.append(f"Optional gaps: {', '.join(optional_missing)}.")
        status = "OK" if completeness.get("grade") in ("A", "B") else "PARTIAL"
    else:
        limitations.append("Data completeness artifact is missing.")
        status = "MISSING"
    return _section("data_completeness_and_limitations", status, bullets, ["data_completeness", "report_limitations"], limitations)


def _build_evidence_appendix(context: dict[str, Any]) -> dict[str, Any]:
    report = context["report"]
    artifacts = context["artifacts"]
    bullets: list[str] = []
    limitations: list[str] = []
    if report or artifacts.get("portfolio_summary"):
        bullets.append("FundAnalysisSkill emits HardEvidence separately in SkillOutput.evidence_items.")
        bullets.append("This composed report does not create formal decisions or execution ledgers.")
        status = "OK"
    else:
        limitations.append("No analysis artifacts are available for evidence appendix context.")
        status = "MISSING"
    return _section("evidence_appendix", status, bullets, ["SkillOutput.evidence_items"], limitations)


def _build_quality_gate(
    data_completeness: dict[str, Any],
    sections: list[dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, Any]:
    grade = str(data_completeness.get("grade", "D") if data_completeness else "D")
    minimal_report_mode = bool(options.get("minimal_report_mode"))
    missing_core = {
        section["id"]
        for section in sections
        if section["status"] == "MISSING"
        and section["id"] in {"executive_summary", "portfolio_snapshot"}
    }
    if grade in ("A", "B") and not missing_core:
        can_publish = True
        reason = f"Data completeness grade {grade} supports a professional report."
    elif grade == "C" and not missing_core:
        can_publish = True
        reason = "Data completeness grade C supports publication only with prominent limitations."
    elif grade == "D" and minimal_report_mode and not missing_core:
        can_publish = True
        reason = "Minimal report mode requested; publish only as a limited snapshot."
    else:
        can_publish = False
        reason = "Data completeness grade D or missing core sections block a professional report."
    return {
        "grade": grade if grade in {"A", "B", "C", "D"} else "D",
        "can_publish_professional_report": can_publish,
        "reason": reason,
    }


def _section(
    section_id: str,
    status: str,
    bullets: list[str],
    data_sources: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    title_map = dict(SECTION_ORDER)
    clean_status = status if status in VALID_STATUSES else "MISSING"
    return {
        "id": section_id,
        "title": title_map[section_id],
        "status": clean_status,
        "bullets": _unique_strings(bullets),
        "data_sources": _unique_strings(data_sources),
        "limitations": _unique_strings(limitations),
    }


def _select_language(options: dict[str, Any]) -> str:
    language = str(options.get("language", "en") or "en")
    normalized = language.replace("_", "-")
    if normalized.lower() in {"zh-cn", "zh-hans-cn", "zh"}:
        return "zh-CN"
    return "en"


def _include_v1_sections(options: dict[str, Any], language: str) -> bool:
    return True


def _localize_sections(sections: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    if language != "zh-CN":
        return sections

    localized: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        copied = dict(section)
        section_id = str(copied.get("id", ""))
        copied["title"] = ZH_CN_SECTION_TITLES.get(section_id, str(copied.get("title", "")))
        copied["bullets"] = [_localize_bullet(str(bullet)) for bullet in _string_list(copied.get("bullets") or [])]
        copied["limitations"] = [
            _localize_limitation(str(item))
            for item in _string_list(copied.get("limitations") or [])
        ]
        copied["language"] = "zh-CN"
        localized.append(copied)
    return localized


def _localize_bullet(text: str) -> str:
    if text.startswith("Portfolio value "):
        prefix = "Portfolio value "
        rest = text[len(prefix):]
        value, sep, tail = rest.partition(" across ")
        if sep and " position(s); cash " in tail:
            count, _, cash = tail.partition(" position(s); cash ")
            return f"组合总市值：{value}；持仓数量：{count}；现金：{cash.rstrip('.')}。"
    if text.startswith("Data completeness grade "):
        rest = text[len("Data completeness grade "):].rstrip(".")
        return f"数据完整度：{rest}。"
    if text.startswith("Completeness grade "):
        rest = text[len("Completeness grade "):].rstrip(".")
        return f"数据完整度：{rest}。"
    if text.startswith("Risk scan surfaced "):
        return "风险扫描：" + text[len("Risk scan surfaced "):]
    if text.startswith("No formal decision generated"):
        return "未生成正式决策；如需正式操作请调用 decision-support。"
    if text.startswith("As of "):
        return "截至 " + text[len("As of "):]
    if text.startswith("Position detail is available"):
        return "持仓明细：" + text[len("Position detail is available "):]
    if text.startswith("Missing data groups: "):
        return "当前缺失的关键数据：" + text[len("Missing data groups: "):]
    if text.startswith("Missing evidence: "):
        return "当前缺失的关键证据：" + text[len("Missing evidence: "):]
    if text.startswith("Next data to fetch: "):
        return "下一步建议补充：" + text[len("Next data to fetch: "):]
    if text.startswith("decision_support_ready: "):
        return "正式决策准备状态：" + text[len("decision_support_ready: "):]
    if text.startswith("Formal decision blockers: "):
        return "暂不建议进入正式决策：" + text[len("Formal decision blockers: "):]
    if text.startswith("Analysis warnings: "):
        return "分析警示：" + text[len("Analysis warnings: "):]
    if text.startswith("Fee blocker is active"):
        return "赎回费阻断项仍然存在，来源为用户提供的赎回规则。"
    if text.startswith("Fee warning is present"):
        return "赎回费警示项仍然存在，来源为用户提供的赎回规则。"
    if text.startswith("Action watchlist contains "):
        return "操作观察清单：" + text[len("Action watchlist contains "):]
    if text.startswith("Formal action requires decision_support"):
        return "正式操作需要调用 decision-support；本节仅为分析观察。"
    if text.startswith("Do not enter formal active decision"):
        return "在阻断项清除前，不应进入正式主动决策：" + text.split(":", 1)[-1].strip()
    if text.startswith("This conclusion is based on host-provided data"):
        return "该结论基于用户提供的数据，不包含实时行情抓取。"
    if text.startswith("Report limitations count: "):
        return "报告限制项数量：" + text[len("Report limitations count: "):]
    if text.startswith("Position contribution covers "):
        return "仓位贡献覆盖：" + text[len("Position contribution covers "):]
    if text.startswith("Profit protection reviewed "):
        return "盈利保护复核：" + text[len("Profit protection reviewed "):]
    if text.startswith("Right-side confirmation applies to "):
        return "右侧确认适用于：" + text[len("Right-side confirmation applies to "):]
    if text.startswith("Event catalyst review covers "):
        return "事件催化复核：" + text[len("Event catalyst review covers "):]
    if text.startswith("Cash-like weight "):
        return "现金类仓位：" + text[len("Cash-like weight "):]
    return text


def _localize_limitation(text: str) -> str:
    if "missing" in text.lower():
        return "数据缺口：" + text
    if "unavailable" in text.lower():
        return "暂不可用：" + text
    return text


def _artifact(context: dict[str, Any], key: str) -> dict[str, Any]:
    artifacts = context["artifacts"]
    report = context["report"]
    return _as_dict(artifacts.get(key) or report.get(key))


def _missing_gap_codes(gap: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for key in sorted(gap):
        if key == "details":
            continue
        if key.startswith("missing_") and gap.get(key) is True:
            result.append(key)
    return result


def _portfolio_summary(context: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(
        context["artifacts"].get("portfolio_summary")
        or context["report"].get("portfolio_metrics")
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def _money(value: Any) -> str:
    try:
        amount = float(value or 0.0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:,.2f}"


def _pct(value: Any) -> str:
    try:
        pct = float(value or 0.0) * 100
    except (TypeError, ValueError):
        pct = 0.0
    return f"{pct:.2f}%"


def _fixed(value: Any, digits: int) -> str:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:.{digits}f}"


def _largest_weight(values: dict[str, Any]) -> tuple[str, Any]:
    sortable: list[tuple[str, float]] = []
    for key, value in values.items():
        try:
            sortable.append((str(key), float(value)))
        except (TypeError, ValueError):
            continue
    if not sortable:
        return ("unknown", 0.0)
    sortable.sort(key=lambda item: (-item[1], item[0]))
    return sortable[0]


def _risk_counts_by_severity(risk_flags: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for flag in risk_flags:
        if not isinstance(flag, dict):
            continue
        severity = str(flag.get("severity") or "unspecified")
        counts[severity] = counts.get(severity, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _best_total_return(fund_metrics: dict[str, Any]) -> tuple[str, float] | None:
    candidates: list[tuple[str, float]] = []
    for fund_code, metrics in fund_metrics.items():
        if not isinstance(metrics, dict):
            continue
        try:
            candidates.append((str(fund_code), float(metrics.get("total_return"))))
        except (TypeError, ValueError):
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return candidates[0]
