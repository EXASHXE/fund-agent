"""Report rendering — compose_personal_fund_report, render_report_markdown, and localization."""

from __future__ import annotations

from typing import Any

from src.tools.portfolio.report_sections.builders import (
    _build_action_watchlist,
    _build_allocation_and_exposure,
    _build_benchmark_and_peer,
    _build_benchmark_divergence,
    _build_cash_deployment,
    _build_data_completeness_and_limitations,
    _build_dca_and_trade_budget,
    _build_event_hype_failure,
    _build_evidence_appendix,
    _build_evidence_status,
    _build_executive_summary,
    _build_personal_health,
    _build_factor_analysis,
    _build_factor_and_style,
    _build_fees_and_redemption,
    _build_manager_and_fund_profile,
    _build_missing_data,
    _build_news_and_events,
    _build_performance_and_nav,
    _build_pnl_and_cost_basis,
    _build_portfolio_snapshot,
    _build_position_contribution,
    _build_professional_diagnostics,
    _build_profit_protection,
    _build_rebalance_plan,
    _build_reconstruction_status,
    _build_research_query_plan,
    _build_right_side_confirmation,
    _build_risk_flags,
    _build_suggested_next_checks,
    _build_transaction_cashflow,
    _build_uncertainty_note,
)
from src.tools.portfolio.report_sections.helpers import (
    _as_dict,
    _string_list,
    _unique_strings,
)
from src.tools.portfolio.report_sections.registry import ZH_CN_SECTION_TITLES


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
    report_limitations = _string_list(artifacts.get("report_limitations") or report.get("report_limitations") or [])
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
        _build_transaction_cashflow(context),
        _build_portfolio_snapshot(context),
        _build_reconstruction_status(context),
        _build_pnl_and_cost_basis(context),
    ]
    if include_v1_sections:
        sections.append(_build_position_contribution(context))
    sections.extend(
        [
            _build_allocation_and_exposure(context),
            _build_risk_flags(context),
            _build_performance_and_nav(context),
            _build_benchmark_and_peer(context),
        ]
    )
    if include_v1_sections:
        sections.append(_build_benchmark_divergence(context))
    sections.extend(
        [
            _build_factor_and_style(context),
            _build_factor_analysis(context),
            _build_fees_and_redemption(context),
            _build_manager_and_fund_profile(context),
            _build_dca_and_trade_budget(context),
            _build_professional_diagnostics(context),
        ]
    )
    if include_v1_sections:
        sections.extend(
            [
                _build_profit_protection(context),
                _build_right_side_confirmation(context),
                _build_event_hype_failure(context),
                _build_news_and_events(context),
                _build_cash_deployment(context),
                _build_evidence_status(context),
                _build_action_watchlist(context),
                _build_missing_data(context),
                _build_suggested_next_checks(context),
                _build_uncertainty_note(context),
            ]
        )
    sections.extend(
        [
            _build_rebalance_plan(context),
            _build_research_query_plan(context),
            _build_data_completeness_and_limitations(context),
            _build_evidence_appendix(context),
            _build_personal_health(context),
        ]
    )
    sections = _localize_sections(sections, language)
    quality_gate_result = _as_dict(artifacts.get("report_quality_gate"))
    quality_gate = _build_quality_gate(
        data_completeness,
        sections,
        options,
        quality_gate_result=quality_gate_result or None,
        fund_analysis_output=artifacts,
    )

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

    sections = report_sections.get("report_sections", []) if isinstance(report_sections, dict) else report_sections
    if not isinstance(sections, list):
        sections = []

    language = (
        "zh-CN"
        if any(isinstance(section, dict) and section.get("language") == "zh-CN" for section in sections)
        else "en"
    )
    title = "个人基金报告" if language == "zh-CN" else "Personal fund report"
    lines: list[str] = [f"# {title}", ""]
    limitations_heading = "限制说明" if language == "zh-CN" else "Limitations"
    global_limitations: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "Untitled section"))
        status = str(section.get("status", "MISSING"))
        bullets = _string_list(section.get("bullets") or [])
        limitations = _string_list(section.get("limitations") or [])

        # Collapse MISSING sections with no bullets — only show limitations in global list
        if status == "MISSING" and not bullets:
            for limitation in limitations:
                item = f"{title}: {limitation}"
                if item not in global_limitations:
                    global_limitations.append(item)
            continue

        lines.append(f"## {title} [{status}]")
        if bullets:
            for bullet in bullets:
                lines.append(f"- {bullet}")
        elif limitations:
            # When there are no bullets but limitations exist, show them as bullets
            # instead of the useless "No section content available" placeholder
            for limitation in limitations:
                lines.append(f"- {limitation}")
            limitations = []  # Already rendered as bullets
        else:
            lines.append("- No section content available from provided artifacts.")
        if limitations:
            lines.append("")
            lines.append(f"{limitations_heading}:")
            for limitation in limitations:
                lines.append(f"- {limitation}")
        if status in {"PARTIAL", "MISSING"}:
            for limitation in limitations:
                item = f"{title}: {limitation}"
                if item not in global_limitations:
                    global_limitations.append(item)
        lines.append("")
    if any(
        isinstance(section, dict) and str(section.get("status", "MISSING")) in {"PARTIAL", "MISSING"}
        for section in sections
    ):
        limitations_heading = "限制说明" if language == "zh-CN" else "Limitations"
        lines.append(f"## {limitations_heading}")
        lines.append("")
        for limitation in global_limitations:
            lines.append(f"- {limitation}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_quality_gate(
    data_completeness: dict[str, Any],
    sections: list[dict[str, Any]],
    options: dict[str, Any],
    quality_gate_result: dict[str, Any] | None = None,
    fund_analysis_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build quality gate dict with backward-compatible fields and new status split.

    When *quality_gate_result* is provided, delegates to
    ``compute_quality_status`` and derives the legacy fields from the
    split status.  Otherwise falls back to the original grade-based logic
    so that existing callers continue to work.
    """
    from src.tools.workflow.advisory_quality_gate import compute_quality_status

    grade = str(data_completeness.get("grade", "D") if data_completeness else "D")
    minimal_report_mode = bool(options.get("minimal_report_mode"))

    if quality_gate_result is not None:
        status = compute_quality_status(
            quality_gate_result,
            data_completeness,
            fund_analysis_output,
        )
        rps = status["report_professional_status"]

        # Derive backward-compatible can_publish_professional_report
        if rps == "PROFESSIONAL":
            can_publish = True
            reason = f"Data completeness grade {grade} supports a professional report."
        elif rps == "LIMITED_BY_DATA":
            can_publish = True
            reason = "Data completeness grade C supports publication only with prominent limitations."
        elif grade == "D" and minimal_report_mode:
            can_publish = True
            reason = "Minimal report mode requested; publish only as a limited snapshot."
        else:
            can_publish = False
            reason = "Data completeness grade D or missing core sections block a professional report."

        return {
            # Legacy backward-compatible fields
            "grade": grade if grade in {"A", "B", "C", "D"} else "D",
            "can_publish_professional_report": can_publish,
            "reason": reason,
            # New status-split fields
            "pipeline_status": status["pipeline_status"],
            "data_readiness_status": status["data_readiness_status"],
            "engineering_status": status["engineering_status"],
            "report_professional_status": status["report_professional_status"],
            "required_user_data": status["required_user_data"],
        }

    # --- Fallback: original logic (no quality_gate_result supplied) ---
    missing_core = {
        section["id"]
        for section in sections
        if section["status"] == "MISSING" and section["id"] in {"executive_summary", "portfolio_snapshot"}
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
            _localize_limitation(str(item)) for item in _string_list(copied.get("limitations") or [])
        ]
        copied["language"] = "zh-CN"
        localized.append(copied)
    return localized


def _localize_bullet(text: str) -> str:
    if text.startswith("Portfolio value "):
        prefix = "Portfolio value "
        rest = text[len(prefix) :]
        value, sep, tail = rest.partition(" across ")
        if sep and " position(s); cash " in tail:
            count, _, cash = tail.partition(" position(s); cash ")
            return f"组合总市值：{value}；持仓数量：{count}；现金：{cash.rstrip('.')}。"
    if text.startswith("Total transactions: "):
        return "交易统计：" + text[len("Total transactions: "):]
    if text.startswith("Completed buy: "):
        return "确认买入：" + text[len("Completed buy: "):]
    if text.startswith("Completed sell: "):
        return "确认卖出：" + text[len("Completed sell: "):]
    if text.startswith("Dividend income: "):
        return "分红收入：" + text[len("Dividend income: "):]
    if text.startswith("Pending amount: "):
        return "待确认金额：" + text[len("Pending amount: "):]
    if text.startswith("Net cashflow: "):
        return "净现金流：" + text[len("Net cashflow: "):]
    if text.startswith("Report source: "):
        return "报告来源：" + text[len("Report source: "):]
    if text.startswith("Transactions parsed: "):
        return "交易解析：" + text[len("Transactions parsed: "):]
    if text.startswith("Ledger built from transactions + current_nav: "):
        return "基于交易+净值构建账本：是。"
    if text.startswith("Ledger built from transactions: "):
        return "基于交易构建账本：" + text[len("Ledger built from transactions: "):]
    if text.startswith("Ledger complete: "):
        return "账本完整性：" + text[len("Ledger complete: "):]
    if text.startswith("NAV snapshot available: "):
        return "净值快照：" + text[len("NAV snapshot available: "):]
    if text.startswith("Confirmed portfolio with valuation: "):
        return "已确认的估值组合：" + text[len("Confirmed portfolio with valuation: "):]
    if text.startswith("Identified "):
        return "已识别" + text[len("Identified "):]
    if text.startswith("Data completeness grade "):
        rest = text[len("Data completeness grade ") :].rstrip(".")
        return f"数据完整度：{rest}。"
    if text.startswith("Completeness grade "):
        rest = text[len("Completeness grade ") :].rstrip(".")
        return f"数据完整度：{rest}。"
    if text.startswith("Risk scan surfaced "):
        return "风险扫描：" + text[len("Risk scan surfaced ") :]
    if text.startswith("No formal decision generated"):
        return "未生成正式决策；如需正式操作请调用 decision-support。"
    if text.startswith("As of "):
        return "截至 " + text[len("As of ") :]
    if text.startswith("Position detail is available"):
        return "持仓明细：" + text[len("Position detail is available ") :]
    if text.startswith("Missing data groups: "):
        return "当前缺失的关键数据：" + text[len("Missing data groups: ") :]
    if text.startswith("Missing evidence: "):
        return "当前缺失的关键证据：" + text[len("Missing evidence: ") :]
    if text.startswith("Next data to fetch: "):
        return "下一步建议补充：" + text[len("Next data to fetch: ") :]
    if text.startswith("decision_support_ready: "):
        return "正式决策准备状态：" + text[len("decision_support_ready: ") :]
    if text.startswith("Formal decision blockers: "):
        return "暂不建议进入正式决策：" + text[len("Formal decision blockers: ") :]
    if text.startswith("Analysis warnings: "):
        return "分析警示：" + text[len("Analysis warnings: ") :]
    if text.startswith("Fee blocker is active"):
        return "赎回费阻断项仍然存在，来源为用户提供的赎回规则。"
    if text.startswith("Fee warning is present"):
        return "赎回费警示项仍然存在，来源为用户提供的赎回规则。"
    if text.startswith("Action watchlist contains "):
        return "操作观察清单：" + text[len("Action watchlist contains ") :]
    if text.startswith("Formal action requires decision_support"):
        return "正式操作需要调用 decision-support；本节仅为分析观察。"
    if text.startswith("Do not enter formal active decision"):
        return "在阻断项清除前，不应进入正式主动决策：" + text.split(":", 1)[-1].strip()
    if text.startswith("This conclusion is based on host-provided data"):
        return "该结论基于用户提供的数据，不包含实时行情抓取。"
    if text.startswith("Report limitations count: "):
        return "报告限制项数量：" + text[len("Report limitations count: ") :]
    if text.startswith("Position contribution covers "):
        return "仓位贡献覆盖：" + text[len("Position contribution covers ") :]
    if text.startswith("Profit protection reviewed "):
        return "盈利保护复核：" + text[len("Profit protection reviewed ") :]
    if text.startswith("Right-side confirmation applies to "):
        return "右侧确认适用于：" + text[len("Right-side confirmation applies to ") :]
    if text.startswith("Event catalyst review covers "):
        return "事件催化复核：" + text[len("Event catalyst review covers ") :]
    if text.startswith("Cash-like weight "):
        return "现金类仓位：" + text[len("Cash-like weight ") :]
    if text.startswith("Unrealized PnL is "):
        return "未实现盈亏：" + text[len("Unrealized PnL is ") :]
    if text.startswith("Position-level PnL is available"):
        return "持仓级盈亏明细：" + text[len("Position-level PnL is available ") :]
    if text.startswith("Transaction-derived cost basis is available"):
        return "交易成本基础：" + text[len("Transaction-derived cost basis is available ") :]
    if text.startswith("Largest position is "):
        return "最大持仓：" + text[len("Largest position is ") :]
    if text.startswith("Largest value position: "):
        return "最大市值持仓：" + text[len("Largest value position: ") :]
    if text.startswith("Largest profit contributor: "):
        return "最大盈利贡献：" + text[len("Largest profit contributor: ") :]
    if text.startswith("Largest loss contributor: "):
        return "最大亏损贡献：" + text[len("Largest loss contributor: ") :]
    if text.startswith("High-profit watchlist contains "):
        return "高盈利观察清单：" + text[len("High-profit watchlist contains ") :]
    if text.startswith("Analysis-only action distribution: "):
        return "分析操作分布：" + text[len("Analysis-only action distribution: ") :]
    if text.startswith("Fee schedule is available for "):
        return "费率表覆盖：" + text[len("Fee schedule is available for ") :]
    if text.startswith("Redemption rules are available for "):
        return "赎回规则覆盖：" + text[len("Redemption rules are available for ") :]
    if text.startswith("Short-holding redemption fee scan found "):
        return "短期赎回费扫描：" + text[len("Short-holding redemption fee scan found ") :]
    if text.startswith("Severe benchmark underperformance is present"):
        return "存在严重基准偏离，来源为提供的数据。"
    if text.startswith("Benchmark divergence is present"):
        return "存在基准偏离，来源为提供的数据。"
    if text.startswith("No severe benchmark divergence was detected"):
        return "未检测到严重基准偏离。"
    if text.startswith("Benchmark divergence reviewed "):
        return "基准偏离复核：" + text[len("Benchmark divergence reviewed ") :]
    if text.startswith("Event hype failure detected for "):
        return "事件催化失效：" + text[len("Event hype failure detected for ") :]
    if text.startswith("No event hype failure was concluded"):
        return "未得出事件催化失效结论。"
    if text.startswith("Cash accounting basis: "):
        return "现金核算基准：" + text[len("Cash accounting basis: ") :]
    if text.startswith("Estimated deployable cash: "):
        return "预计可部署现金：" + text[len("Estimated deployable cash: ") :]
    if text.startswith("No risk flags were generated"):
        return "风险扫描未产生标记。"
    if text.startswith("Risk flags by severity: "):
        return "风险标记按严重程度：" + text[len("Risk flags by severity: ") :]
    if text.startswith("NAV-derived metrics are available for "):
        return "净值指标覆盖：" + text[len("NAV-derived metrics are available for ") :]
    if text.startswith("Highest total return in provided NAV history is "):
        return "历史最高总回报：" + text[len("Highest total return in provided NAV history is ") :]
    if text.startswith("Trade budget: max buy "):
        return "交易预算：" + text[len("Trade budget: max buy ") :]
    if text.startswith("DCA review includes "):
        return "定投复核：" + text[len("DCA review includes ") :]
    if text.startswith("FundAnalysisSkill emits HardEvidence"):
        return "FundAnalysisSkill 单独输出 HardEvidence 至 SkillOutput.evidence_items。"
    if text.startswith("This composed report does not create"):
        return "本报告不生成正式决策或执行账本。"
    if text.startswith("Optional gaps: "):
        return "可选项缺口：" + text[len("Optional gaps: ") :]
    if text.startswith("No required missing data groups were reported"):
        return "未报告必要数据缺口。"
    if text.startswith("Fresh NAV, benchmark, news, or sentiment evidence is needed"):
        return "需要新的净值、基准、新闻或情绪证据才能采取行动。"
    if text.startswith("High-risk event markers: "):
        return "高风险事件标记：" + text[len("High-risk event markers: ") :]
    if text.startswith("Event catalyst review covers "):
        return "事件催化复核：" + text[len("Event catalyst review covers ") :]
    if text.startswith("Rebalance simulation produced "):
        return "再平衡模拟：" + text[len("Rebalance simulation produced ") :]
    if text.startswith("Research query plan includes "):
        return "研究查询计划：" + text[len("Research query plan includes ") :]
    if text.startswith("Short-term trade budget usage is available"):
        return "短期交易预算使用情况可用。"
    if text.startswith("No additional next-data items were requested"):
        return "分析计划未要求补充额外数据。"
    if text.startswith("Cash ratio is "):
        return "现金比例：" + text[len("Cash ratio is ") :]
    if text.startswith("Liquidity reserve gap: "):
        return "流动性储备缺口：" + text[len("Liquidity reserve gap: ") :]
    if text.startswith("Short-term trade budget status: "):
        return "短期交易预算状态：" + text[len("Short-term trade budget status: ") :]
    if text.startswith("Overall status: "):
        return "整体状态：" + text[len("Overall status: ") :]
    if text.startswith("Confidence: "):
        return "置信度：" + text[len("Confidence: ") :]
    if text.startswith("Transactions: "):
        return "交易来源：" + text[len("Transactions: ") :]
    if text.startswith("Valuation: "):
        return "估值来源：" + text[len("Valuation: ") :]
    if text.startswith("Identity: "):
        return "身份来源：" + text[len("Identity: ") :]
    if text.startswith("Valuation quality: "):
        return "估值质量：" + text[len("Valuation quality: ") :]
    if text.startswith("NAV coverage: "):
        return "净值覆盖：" + text[len("NAV coverage: ") :]
    if text.startswith("Stale NAV count: "):
        return "过时净值数量：" + text[len("Stale NAV count: ") :]
    if text.startswith("QDII-like count: "):
        return "QDII类基金数量：" + text[len("QDII-like count: ") :]
    if text.startswith("Action needed: "):
        return "需处理：" + text[len("Action needed: ") :]
    if text.startswith("Reason codes: "):
        return "原因码：" + text[len("Reason codes: ") :]
    return text


def _localize_limitation(text: str) -> str:
    if "missing" in text.lower():
        return "数据缺口：" + text
    if "unavailable" in text.lower():
        return "暂不可用：" + text
    if "absent" in text.lower():
        return "暂缺：" + text
    if "not fabricated" in text.lower():
        return "未合成：" + text
    return text
