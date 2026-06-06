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
    ("allocation_and_exposure", "Allocation and exposure"),
    ("risk_flags", "Risk flags"),
    ("performance_and_nav", "Performance and NAV"),
    ("benchmark_and_peer", "Benchmark and peer"),
    ("factor_and_style", "Factor and style"),
    ("fees_and_redemption", "Fees and redemption"),
    ("manager_and_fund_profile", "Manager and fund profile"),
    ("dca_and_trade_budget", "DCA and trade budget"),
    ("rebalance_plan", "Rebalance plan"),
    ("research_query_plan", "Research query plan"),
    ("data_completeness_and_limitations", "Data completeness and limitations"),
    ("evidence_appendix", "Evidence appendix"),
)

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

    context = {
        "artifacts": artifacts,
        "report": report,
        "data_completeness": data_completeness,
        "analysis_coverage": analysis_coverage,
        "report_limitations": report_limitations,
        "warnings": combined_warnings,
    }

    sections = [
        _build_executive_summary(context),
        _build_portfolio_snapshot(context),
        _build_pnl_and_cost_basis(context),
        _build_allocation_and_exposure(context),
        _build_risk_flags(context),
        _build_performance_and_nav(context),
        _build_benchmark_and_peer(context),
        _build_factor_and_style(context),
        _build_fees_and_redemption(context),
        _build_manager_and_fund_profile(context),
        _build_dca_and_trade_budget(context),
        _build_rebalance_plan(context),
        _build_research_query_plan(context),
        _build_data_completeness_and_limitations(context),
        _build_evidence_appendix(context),
    ]
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

    lines: list[str] = ["# Personal fund report", ""]
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
