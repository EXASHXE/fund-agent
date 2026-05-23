"""Render investment research evidence drafts and Agent-decided final reports."""

from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from src.output.templates import portfolio_overview_table, qdii_hint, report_header, risk_disclaimer


def generate_report(
    analyzer,
    scores: List[Dict],
    correlations,
    stress_tests: List[Dict],
    holdings_data: Optional[Dict] = None,
    news_data: Optional[List[Dict]] = None,
    recommendations: Optional[List[Dict]] = None,
    recommendation_status: str = "skipped",
    unscores: Optional[List[Dict]] = None,
    workflow_context: Optional[Dict] = None,
    inter_recommendation_correlations=None,
    agent_decisions: Optional[Dict] = None,
) -> str:
    """Build a report with a strict boundary between evidence and decisions."""
    del analyzer, inter_recommendation_correlations
    scores = scores or []
    holdings_data = holdings_data or {}
    news_data = news_data or []
    decisions = agent_decisions or {}
    is_final = bool(decisions.get("fund_scores"))

    lines = [report_header(len(scores)).rstrip()]
    if is_final:
        lines.append("> 报告状态：Agent 最终研判（决策来源为已提供的 Agent 决策数据）")
    else:
        lines.append("> 报告状态：证据稿；待 Agent 最终评定，不构成行动建议")
    lines.extend(["", *_render_tldr(scores, holdings_data, decisions, is_final)])

    lines.extend(["", "## 一、新闻资讯与 Agent 舆情研判", ""])
    lines.extend(_render_news_section(news_data, decisions))

    lines.append("")
    if holdings_data:
        lines.append(portfolio_overview_table(holdings_data).rstrip())
    else:
        lines.extend([
            "## 二、持仓总览与收益口径",
            "",
            "未提供持仓计算结果；本章不输出配置判断。",
        ])

    lines.append("")
    if workflow_context:
        lines.append(_render_workflow_focus(
            workflow_context, holdings_data, scores=scores, news_data=news_data,
            agent_decisions=decisions,
        ).rstrip())
    else:
        lines.extend([
            "## 三、定投执行与申购结算状态",
            "",
            "未提供定投与申购结算证据。",
        ])

    lines.extend(["", "## 四、单基金深度诊断", ""])
    lines.extend(_render_fund_diagnostics(scores, holdings_data, decisions))

    lines.extend(["", "## 五、组合研判与执行方案", ""])
    lines.extend(_render_agent_actions(scores, holdings_data, decisions))

    lines.extend(["", "## 六、组合风险、相关性与压力测试", ""])
    lines.extend(_render_risk_section(correlations, stress_tests, decisions, unscores or []))

    lines.extend(["", "## 七、推荐候选与观察池", ""])
    lines.extend(_render_recommendations(
        recommendations or [], recommendation_status, agent_decisions,
    ))

    lines.extend(["", risk_disclaimer().rstrip(), ""])
    return "\n".join(lines)


def _render_tldr(
    scores: List[Dict], holdings_data: Dict, decisions: Dict, is_final: bool,
) -> List[str]:
    lines = ["## TL;DR", ""]
    portfolio = decisions.get("portfolio") or {}
    if is_final:
        lines.append(f"- Agent 组合立场：{portfolio.get('stance', '待说明')}")
        lines.append(f"- Agent 摘要：{portfolio.get('tldr', '已形成逐基金决策，详见第五章。')}")
    else:
        valid_scores = [
            float(item.get("composite_score", 0) or 0)
            for item in scores if item.get("composite_score") is not None
        ]
        baseline = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        lines.append(f"- 量化基准分均值：{baseline:.2f}/100（仅为输入证据）")
        lines.append("- 当前为证据稿，最终动作需由 Agent 结合风险约束判断。")
    if holdings_data.get("total_value") is not None:
        lines.append(f"- 组合当前市值：¥{float(holdings_data.get('total_value', 0) or 0):,.2f}")
    return lines


def _render_news_section(news_data: List[Dict], decisions: Dict) -> List[str]:
    if not news_data:
        return ["未提供截至口径日的有效新闻证据。"]

    news_decisions = decisions.get("news") or {}
    lines = [
        "> 仅展示截至口径日有效新闻；衰减词典信号为辅助证据，不直接产生投资动作。",
        "",
    ]
    for item in news_data:
        code = str(item.get("fund_code", ""))
        name = item.get("fund_name") or code or "未命名基金"
        evaluation = item.get("news_evaluation") or {}
        signal = _as_float(item.get("sentiment_mean"))
        quality = _as_float(evaluation.get("quality_score"))
        coverage_count = evaluation.get("holding_coverage_count", "-")
        coverage_pct = evaluation.get("holding_coverage_pct")
        coverage_text = _format_ratio_pct(coverage_pct)
        warning = evaluation.get("coverage_warning") or "未提供新闻覆盖限制说明"

        body = [
            "| 指标 | 证据 |",
            "|------|------|",
            f"| 截至口径日有效新闻 | {int(item.get('news_count', 0) or 0)} 条 |",
            f"| 衰减词典信号（辅助） | {signal:+.3f} |",
            f"| 新闻质量评估 | {quality:.2f} |",
            f"| 命中持仓数量 / 权重覆盖 | {coverage_count} / {coverage_text} |",
            f"| 覆盖限制 | {warning} |",
            "",
        ]
        agent_news = news_decisions.get(code) or {}
        if agent_news:
            body.extend([
                "**Agent 舆情研判**",
                "",
                f"- 摘要：{agent_news.get('summary', '未说明')}",
                f"- 影响方向：{agent_news.get('impact', '未说明')}",
                f"- 相关性：{agent_news.get('relevance', '未说明')}",
                f"- 置信度：{_format_confidence(agent_news.get('confidence'))}",
            ])
            if agent_news.get("watch"):
                body.append(f"- 观察事项：{_join_value(agent_news.get('watch'))}")
        else:
            body.append("待 Agent 根据新闻证据与覆盖限制进行最终研判。")

        daily = item.get("daily_aggregates") or []
        if daily:
            body.extend(["", "**逐日辅助信号**", "", "| 日期 | 新闻数 | 信号均值 |", "|------|------:|---------:|"])
            for row in daily:
                body.append(
                    f"| {row.get('date', '-')} | {row.get('count', row.get('news_count', '-'))} "
                    f"| {_as_float(row.get('sentiment_mean')):+.3f} |"
                )

        sampled = item.get("news_list") or []
        if sampled:
            body.extend(["", "**证据样本**", "", "| 日期 | 标题 |", "|------|------|"])
            for news in sampled[:8]:
                body.append(f"| {news.get('date', '-')} | {news.get('title', '-')} |")

        post_cutoff = item.get("post_cutoff_news") or []
        if post_cutoff:
            body.extend([
                "",
                "**口径日后观察（不纳入当日归因）**",
                "",
                "| 日期 | 标题 |",
                "|------|------|",
            ])
            for news in post_cutoff[:5]:
                body.append(f"| {news.get('date', '-')} | {news.get('title', '-')} |")
        lines.extend(_details(f"{name}（{code}）新闻证据", body))
    return lines


def _render_fund_diagnostics(
    scores: List[Dict], holdings_data: Dict, decisions: Dict,
) -> List[str]:
    if not scores:
        return ["无可用的基金评分证据。"]

    holding_lookup = {
        str(item.get("code", "")): item for item in (holdings_data.get("funds") or [])
    }
    detail_lookup = holdings_data.get("by_fund") or {}
    fund_decisions = decisions.get("fund_scores") or {}
    lines: List[str] = []
    for score in scores:
        code = str(score.get("fund_code", ""))
        name = score.get("fund_name") or code
        fund = holding_lookup.get(code, {})
        detail = detail_lookup.get(code, {})
        decision = fund_decisions.get(code) or {}
        finals = decision.get("final_scores") or {}
        adjusts = decision.get("agent_adjustments") or {}
        total_adjustment = adjusts.get("total")
        if total_adjustment is None and all(
            isinstance(adjusts.get(key), (int, float)) for key in ("macro", "meso", "micro")
        ):
            total_adjustment = sum(adjusts[key] for key in ("macro", "meso", "micro"))
        fund_type = score.get("fund_type") or fund.get("fund_type") or detail.get("fund_type", "")
        title = f"{name}（{code}）"
        body = [
            f"### {title}{qdii_hint(name, fund_type)}",
            "",
            "| 维度 | 量化基准分 | Agent 调整 | 最终分 | 关键依据 |",
            "|------|-----------:|-----------:|-------:|----------|",
            _score_row("宏观", score.get("macro_score"), adjusts.get("macro"), finals.get("macro"), score.get("macro_basis")),
            _score_row("中观", score.get("meso_score"), adjusts.get("meso"), finals.get("meso"), score.get("meso_basis")),
            _score_row("微观", score.get("micro_score"), adjusts.get("micro"), finals.get("micro"), score.get("micro_basis")),
            _score_row("综合", score.get("composite_score"), total_adjustment, finals.get("total"), "量化基准与 Agent 校准汇总"),
            "",
        ]
        if decision:
            body.extend([
                f"- Agent 最终评分：{_score_value(finals.get('total'))}/100",
                f"- Agent 最终动作：{decision.get('final_action', '未说明')}",
                f"- 研判依据：{_join_value(decision.get('rationale'))}",
                f"- 复核触发：{_join_value(decision.get('triggers'))}",
            ])
            if decision.get("trend_view"):
                body.append(f"- 趋势判断：{_join_value(decision.get('trend_view'))}")
        else:
            body.extend([
                "- Agent 最终评分：待评定",
                "- 本条为量化证据，不输出规则动作；待 Agent 最终评定。",
            ])

        if fund or detail:
            body.extend([
                "",
                "**持仓与约束证据**",
                "",
                "| 指标 | 数值 |",
                "|------|------|",
                f"| 当前市值 | ¥{_as_float(fund.get('value', detail.get('current_value'))):,.2f} |",
                f"| 累计收益 | ¥{_as_float(fund.get('profit', detail.get('profit'))):+,.2f} |",
                f"| 待确认金额 | ¥{_as_float(fund.get('pending_amount', detail.get('pending_amount'))):,.2f} |",
            ])

        body.extend([
            "",
            "**风险边界证据**",
            "",
            "| 指标 | 设定值 |",
            "|------|------|",
            f"| **止盈线** | +{_as_float(score.get('stop_profit_pct'), 20.0):.2f}% |",
            f"| **止损线** | {_negative_pct(score.get('stop_loss_pct'), -15.0)} |",
            f"| 年化波动率 | {_format_optional_pct(score.get('annual_volatility'))} |",
        ])
        lines.extend(_details(title, body))
    return lines


def _render_agent_actions(scores: List[Dict], holdings_data: Dict, decisions: Dict) -> List[str]:
    fund_decisions = decisions.get("fund_scores") or {}
    if not fund_decisions:
        return ["本报告为证据稿；动作、配置范围、执行金额与触发条件须由 Agent 最终给出。"]

    holding_lookup = {
        str(item.get("code", "")): item for item in (holdings_data.get("funds") or [])
    }
    total_value = _as_float(holdings_data.get("total_value"))
    known_names = {
        str(item.get("fund_code", "")): item.get("fund_name", "")
        for item in scores
    }
    lines = [
        "| 基金 | 当前占比 | Agent 动作 | Agent 目标范围 | 本期执行金额 | Agent 触发条件 |",
        "|------|---------:|------------|---------------:|-------------:|----------------|",
    ]
    for code, decision in fund_decisions.items():
        fund = holding_lookup.get(str(code), {})
        name = known_names.get(str(code)) or fund.get("name") or str(code)
        current_pct = (
            _as_float(fund.get("value")) / total_value * 100 if total_value else None
        )
        target = decision.get("target_weight_pct")
        amount = decision.get("adjust_amount")
        lines.append(
            f"| {name}（{code}） | {_format_optional_pct(current_pct)} | "
            f"{decision.get('final_action', '未说明')} | {_format_optional_pct(target)} | "
            f"{_format_money(amount)} | {_join_value(decision.get('triggers'))} |"
        )
    portfolio = decisions.get("portfolio") or {}
    if portfolio.get("execution_notes"):
        lines.extend(["", f"- 执行说明：{_join_value(portfolio.get('execution_notes'))}"])
    return lines


def _render_risk_section(
    correlations, stress_tests: List[Dict], decisions: Dict, unscores: List[Dict],
) -> List[str]:
    lines: List[str] = []
    if _has_correlation_data(correlations):
        lines.extend([
            "**相关性证据**",
            "",
            "相关性矩阵已作为组合集中度与同向风险的输入证据提供给 Agent。",
            "",
        ])
    else:
        lines.extend(["未提供可用相关性矩阵。", ""])

    if stress_tests:
        lines.extend(["**压力测试证据**", "", "| 场景 | 估算影响 |", "|------|----------|"])
        for item in stress_tests:
            scenario = item.get("scenario") or item.get("name") or "未命名场景"
            impact = (
                item.get("portfolio_impact")
                if item.get("portfolio_impact") is not None else item.get("impact", "-")
            )
            lines.append(f"| {scenario} | {impact} |")
    else:
        lines.append("未启用或未获得压力测试结果。")

    if decisions.get("portfolio", {}).get("risk_summary"):
        lines.extend(["", f"- Agent 风险结论：{_join_value(decisions['portfolio']['risk_summary'])}"])
    else:
        lines.extend(["", "压力与相关性线索仅作为 Agent 风险研判证据。"])

    if unscores:
        lines.extend(["", f"- 因数据不足未纳入基准评分：{len(unscores)} 只基金。"])
    return lines


def _render_recommendations(
    recommendations: List[Dict], recommendation_status: str, agent_decisions: Optional[Dict],
) -> List[str]:
    if agent_decisions is not None and "recommendations" in agent_decisions:
        final_recs = agent_decisions.get("recommendations") or []
        if not final_recs:
            return ["本次 Agent 未给出最终推荐；候选不会自动回填为结论。"]
        lines = [
            "| Agent 推荐基金 | 推荐理由 | 风险约束 |",
            "|----------------|----------|----------|",
        ]
        for item in final_recs:
            label = item.get("name") or item.get("fund_name") or item.get("code", "-")
            if item.get("code") and item.get("code") not in label:
                label = f"{label}（{item['code']}）"
            lines.append(
                f"| {label} | {_join_value(item.get('rationale') or item.get('reason'))} "
                f"| {_join_value(item.get('risk_constraints') or item.get('risks'))} |"
            )
        return lines

    if recommendations:
        lines = [
            "以下为规则筛选候选（仅供 Agent 复核，不构成推荐结论）：",
            "",
            "| 候选基金 | 主题 | 筛选得分 |",
            "|----------|------|---------:|",
        ]
        for item in recommendations:
            label = item.get("name") or item.get("fund_name") or item.get("code", "-")
            if item.get("code") and item.get("code") not in label:
                label = f"{label}（{item['code']}）"
            lines.append(
                f"| {label} | {item.get('theme', '-')} | {_as_float(item.get('score')):.2f} |"
            )
        return lines
    if recommendation_status == "skipped":
        return ["未启用候选筛选；本报告不自动生成推荐池。"]
    return ["候选筛选未形成可供 Agent 复核的对象。"]


def _render_workflow_focus(
    workflow_context: Dict,
    holdings_data: Dict,
    scores: Optional[List[Dict]] = None,
    news_data: Optional[List[Dict]] = None,
    agent_decisions: Optional[Dict] = None,
) -> str:
    del scores, news_data
    ctx = workflow_context or {}
    lines = [
        "## 三、定投执行与申购结算状态",
        "",
        f"> 数据口径日：{ctx.get('report_date', '-')}；运行日：{ctx.get('run_date', '-')}；"
        f"状态说明：{ctx.get('mode_reason', '未提供')}",
        "",
    ]
    if ctx.get("is_trade_day"):
        lines.extend(_render_trade_day_focus(ctx, holdings_data, agent_decisions or {}))
    else:
        lines.extend(_render_non_trade_day_focus(ctx, holdings_data))
    lines.extend(_render_execution_tables(ctx))
    return "\n".join(lines)


def _render_trade_day_focus(ctx: Dict, holdings_data: Dict, decisions: Dict) -> List[str]:
    lines = [
        "### 当日盈亏与贡献分布",
        "",
        "| 基金 | 当日盈亏 | 当日收益率 | 当日盈亏贡献 |",
        "|------|---------:|-----------:|-------------:|",
    ]
    funds = holdings_data.get("funds") or []
    total_abs = sum(abs(_as_float(item.get("day_profit"))) for item in funds)
    for fund in funds:
        day_profit = _as_float(fund.get("day_profit"))
        lines.append(
            f"| {fund.get('name', fund.get('code', '-'))} | {_format_colored_amount(day_profit)} | "
            f"{_format_colored_pct(fund.get('day_return_pct'))} | "
            f"{_format_profit_contribution(day_profit, total_abs)} |"
        )
    if not funds:
        lines.append("| 无持仓日收益证据 | - | - | - |")

    daily_analysis = (decisions.get("portfolio") or {}).get("daily_analysis")
    lines.extend(["", "#### 当日归因线索", ""])
    if daily_analysis:
        lines.append(str(daily_analysis))
    else:
        lines.append("> 当日归因需由 Agent 结合口径内新闻和净值证据最终完成。")

    top_news = ctx.get("top_news") or []
    if top_news:
        lines.extend(["", "#### 当日新闻线索", "", "| 日期 | 基金 | 标题 | 衰减辅助信号 |", "|------|------|------|-------------:|"])
        for item in top_news:
            lines.append(
                f"| {item.get('date', '-')} | {item.get('name', item.get('code', '-'))} | "
                f"{item.get('headline', '-')} | {_as_float(item.get('sentiment')):+.3f} |"
            )
    return lines + [""]


def _render_non_trade_day_focus(ctx: Dict, holdings_data: Dict) -> List[str]:
    lines = [
        "### 周期多维收益贡献",
        "",
        "| 基金 | 周期盈亏 | 贡献占比 |",
        "|------|---------:|---------:|",
    ]
    funds = holdings_data.get("funds") or []
    total_abs = sum(abs(_as_float(item.get("week_profit"))) for item in funds)
    for fund in funds:
        value = _as_float(fund.get("week_profit"))
        lines.append(
            f"| {fund.get('name', fund.get('code', '-'))} | {_format_colored_amount(value)} "
            f"| {_format_profit_contribution(value, total_abs)} |"
        )
    if not funds:
        lines.append("| 无周期收益证据 | - | - |")
    lines.extend(["", "> 非交易日仅呈现最近结算口径证据，不推断当日交易动作。", ""])
    return lines


def _render_execution_tables(ctx: Dict) -> List[str]:
    lines = [
        "### 定投执行与确认预估",
        "",
    ]
    dca_rows = ctx.get("dca_rows") or []
    if dca_rows:
        lines.extend([
            "| 基金 | 周期 | 金额 | 计划日 | 执行状态 | 净值确认日 | 收益可见时间 |",
            "|------|------|-----:|--------|----------|------------|--------------|",
        ])
        for row in dca_rows:
            lines.append(
                f"| {row.get('name', row.get('code', '-'))} | {row.get('frequency', '-')} "
                f"| ¥{_as_float(row.get('amount')):,.2f} | {row.get('scheduled_date', '-')} "
                f"| {row.get('status', '-')} | {row.get('nav_date') or row.get('settle_date') or '-'} "
                f"| {row.get('earnings_visible_after', '-')} |"
            )
    else:
        lines.append("未提供启用中的定投计划或本期无待展示的定投证据。")

    lines.extend(["", "### 申购与净值结算状态", ""])
    settlement_rows = ctx.get("settlement_rows") or ctx.get("qdii_rows") or []
    if not settlement_rows:
        lines.append("未提供持仓结算状态证据。")
        return lines
    lines.extend([
        "| 基金 | 类型 | 最新净值日期 | 净值披露状态 | 待确认金额 | 下一结算日 | 结算状态 |",
        "|------|------|--------------|--------------|-----------:|------------|----------|",
    ])
    for row in settlement_rows:
        lines.append(
            f"| {row.get('name', row.get('code', '-'))} | {row.get('fund_type') or '-'} "
            f"| {row.get('nav_date') or '-'} | {row.get('nav_status', '-')} "
            f"| ¥{_as_float(row.get('pending_amount')):,.2f} | {row.get('next_settle_date') or '-'} "
            f"| {row.get('settlement_status', '-')} |"
        )
    return lines


def _details(summary: str, body_lines: Iterable[str]) -> List[str]:
    return ["<details>", f"<summary>{summary}</summary>", "", *body_lines, "", "</details>", ""]


def _score_row(label: str, base, adjustment, final, basis) -> str:
    return (
        f"| {label} | {_score_value(base)} | {_signed_score(adjustment)} | "
        f"{_score_value(final)} | {basis or '-'} |"
    )


def _score_value(value) -> str:
    if value is None:
        return "待评定"
    number = _as_float(value)
    return f"{number:.0f}" if number.is_integer() else f"{number:.2f}"


def _signed_score(value) -> str:
    if value is None:
        return "待评定"
    number = _as_float(value)
    return f"{number:+.0f}" if number.is_integer() else f"{number:+.2f}"


def _format_optional_pct(value) -> str:
    if value is None or value == "":
        return "-"
    return f"{_as_float(value):.2f}%"


def _format_ratio_pct(value) -> str:
    if value is None or value == "":
        return "-"
    return f"{_as_float(value) * 100:.2f}%"


def _format_confidence(value) -> str:
    if value is None:
        return "未说明"
    number = _as_float(value)
    return f"{number * 100:.1f}%" if abs(number) <= 1 else f"{number:.1f}%"


def _format_money(value) -> str:
    if value is None or value == "":
        return "-"
    return f"¥{_as_float(value):+,.2f}"


def _negative_pct(value, default: float) -> str:
    number = _as_float(value, default)
    return f"{number:.2f}%" if number < 0 else f"-{number:.2f}%"


def _format_profit_contribution(value: float, denominator: float) -> str:
    """Show each signed contribution against absolute portfolio profit movement."""
    denominator = float(denominator or 0)
    if not denominator:
        return "+0.00%"
    return f"{float(value or 0) / denominator * 100:+.2f}%"


def _format_colored_amount(value) -> str:
    return f"¥{_as_float(value):+,.2f}"


def _format_colored_pct(value) -> str:
    return f"{_as_float(value):+.2f}%"


def _join_value(value) -> str:
    if value is None or value == "":
        return "未说明"
    if isinstance(value, (list, tuple, set)):
        return "；".join(str(item) for item in value) if value else "未说明"
    return str(value)


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _has_correlation_data(correlations: Any) -> bool:
    if isinstance(correlations, pd.DataFrame):
        return not correlations.empty
    return bool(correlations)
