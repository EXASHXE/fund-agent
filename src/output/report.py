"""
Markdown 报告生成 — 完整诊断报告输出。
"""
from datetime import date
from typing import Dict, List
import pandas as pd

from src.analysis.scorer import FundAnalyzer
from src.output.templates import (
    report_header, portfolio_overview_table, risk_disclaimer
)


def generate_report(
    analyzer: FundAnalyzer,
    scores: List[Dict],
    correlations: pd.DataFrame,
    stress_tests: List[Dict],
    holdings_data: Dict = None,
    news_data: List[Dict] = None,
    recommendations: List[Dict] = None,
    recommendation_status: str = None,
    unscores: List[Dict] = None,
    workflow_context: Dict = None,
    inter_recommendation_correlations: Dict = None,
) -> str:
    """生成完整的 Markdown 诊断报告。"""
    lines = []

    all_funds = list(scores)
    if unscores:
        all_funds = all_funds + unscores

    lines.append(report_header(len(all_funds)))

    # === 持仓总览 ===
    if holdings_data:
        lines.append(portfolio_overview_table(holdings_data))
    else:
        lines.append("## 综合评分概览")
        lines.append("")
        lines.append("| 基金 | 代码 | 完整度 | 宏观 | 中观 | 微观 | 综合 | 等级 | 操作建议 |")
        lines.append("|------|------|--------|------|------|------|------|------|---------|")
        for s in scores:
            meso = str(s["meso_score"]) if s["meso_score"] is not None else "N/A"
            lines.append(
                f"| {s['fund_name']} | {s['fund_code']} | {s['data_completeness']} "
                f"| {s['macro_score']} | {meso} | {s['micro_score']} "
                f"| **{s['composite_score']}** | {s['score_level_emoji']} "
                f"| {s['recommendation']} |"
            )
        lines.append("")

    if workflow_context:
        lines.append(_render_workflow_focus(workflow_context, holdings_data, scores, news_data))

    # === 资金分配总览 ===
    if holdings_data:
        total_value = holdings_data.get("total_value", 0)
        if total_value > 0:
            lines.append("---")
            lines.append("## 资金分配与仓位调整")
            lines.append("")
            lines.append("| 基金 | 当前市值(¥) | 当前占比 | 建议占比 | 调整金额(¥) | 操作 |")
            lines.append("|------|-----------|---------|---------|-----------|------|")
            for fund in holdings_data.get("funds", []):
                current_pct = fund["value"] / total_value * 100 if total_value else 0
                code = fund["code"]
                # Match with score
                score = next((s for s in scores if s["fund_code"] == code), None)
                if score:
                    if score["score_level"] == "green":
                        target_pct = min(25, current_pct + 5)
                        action = "逢低加仓"
                    elif score["score_level"] == "yellow":
                        target_pct = current_pct
                        action = "持有"
                    elif score["score_level"] == "orange":
                        target_pct = max(5, current_pct * 0.5)
                        action = "减仓50%"
                    else:
                        target_pct = 0
                        action = "止损清仓"
                    adjust = (target_pct - current_pct) / 100 * total_value
                else:
                    target_pct = current_pct
                    adjust = 0
                    action = "数据不足"
                lines.append(
                    f"| {fund['name']}（{code}） | ¥{fund['value']:,.2f} "
                    f"| {current_pct:.2f}% | {target_pct:.2f}% "
                    f"| ¥{adjust:+,.2f} | {action} |"
                )
            lines.append("")

    # === 单基金诊断 ===
    lines.append("---")
    lines.append("## 单基金诊断")
    lines.append("")

    for s in scores:
        lines.append(f"### {s['fund_name']}（{s['fund_code']}）")
        lines.append(f"- **数据完整度**：{s['data_completeness']}")
        lines.append(f"- **综合评分**：{s['composite_score']}/100（{s['score_level_emoji']}）")
        lines.append("")

        meso = str(s["meso_score"]) if s["meso_score"] is not None else "N/A"
        meso_basis = s.get("meso_basis", "") or "中观数据缺失"

        lines.append("| 维度 | 得分 | 满分 | 权重 | 关键依据 |")
        lines.append("|------|------|------|------|---------|")
        lines.append(f"| 宏观 | {s['macro_score']} | 20 | 20% | {s['macro_basis']} |")
        lines.append(f"| 中观 | {meso} | 30 | 30% | {meso_basis} |")
        lines.append(f"| 微观 | {s['micro_score']} | 50 | 50% | {s['micro_basis']} |")
        lines.append("")

        # 操作建议 + 具体金额
        fund_detail = None
        if holdings_data and "by_fund" in holdings_data:
            fund_detail = holdings_data["by_fund"].get(s["fund_code"])

        lines.append("| 项目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| **结论** | {s['recommendation']} |")
        if fund_detail:
            lines.append(f"| **持仓市值** | ¥{fund_detail['current_value']:,.2f} |")
            lines.append(f"| **浮动盈亏** | ¥{fund_detail['profit']:+,.2f}（{fund_detail['return_pct']:+.2f}%）|")
        lines.append(f"| **止盈线** | +{s['stop_profit_pct']:.2f}% |")
        lines.append(f"| **止损线** | {s['stop_loss_pct']:.2f}% |")
        if s.get("previous_score") is not None:
            lines.append(
                f"| **评分趋势** | 本次 {s['composite_score']}；上次 {s['previous_score']} "
                f"({s.get('score_delta', 0):+d})；历史峰值 {s.get('peak_score')}，"
                f"较峰值回落 {s.get('drop_from_peak', 0)} 分 |"
            )
        lines.append(f"| **行动逻辑** | {s['action_logic']} |")
        if s.get("agent_review_required"):
            lines.append("| **评分性质** | 规则初稿；接入 skill 的 agent 需结合新闻、大盘和持仓成本做最终校准 |")
        if s.get("annual_volatility"):
            lines.append(f"| **年化波动率** | {s['annual_volatility']:.2f}% |")
        if s.get("max_drawdown_3y"):
            lines.append(f"| **最大回撤(3年)** | {s['max_drawdown_3y']:.2f}% |")
        if s.get("sharpe_1y"):
            lines.append(f"| **夏普比率(1年)** | {s['sharpe_1y']:.2f} |")
        if s.get("manager"):
            lines.append(f"| **基金经理** | {s['manager']} |")

        # 持仓趋势
        if fund_detail:
            lines.append("")
            lines.append("#### 持仓趋势分析")
            lines.append("")
            lines.append(
                f"- 累计投入：¥{fund_detail['total_cost']:,.2f} "
                f"| 当前市值：¥{fund_detail['current_value']:,.2f} "
                f"| 浮动盈亏：¥{fund_detail['profit']:+,.2f}（{fund_detail['return_pct']:+.2f}%）"
            )
            days = fund_detail.get("days_held", 0)
            if days >= 365:
                lines.append(f"- 年化收益：{fund_detail['annual_return']:+.2f}% (XIRR)")
            else:
                lines.append(f"- 年化收益：短期不适用（持有 {days} 天 < 1 年）")
            if fund_detail.get("dca_avg_cost", 0) > 0:
                lines.append(f"- 定投成本均线：¥{fund_detail['dca_avg_cost']:.4f}")

                if fund_detail.get("dca_records"):
                    lines.append("")
                    lines.append("**定投明细**（含0.15%申购费）")
                    lines.append("")
                    lines.append("| 期数 | 日期 | 金额 | 手续费 | 买入净值 | 获得份额 | 累计份额 | 该期收益率 |")
                    lines.append("|------|------|------|------|---------|---------|---------|----------|")
                for i, rec in enumerate(fund_detail["dca_records"][:20]):
                    d = rec['date']
                    if hasattr(d, 'isoformat'):
                        d = d.isoformat()
                    lines.append(
                        f"| {i+1} | {d} | ¥{rec['amount']:,.2f} "
                        f"| ¥{rec.get('fee', 0):.2f} | {rec['nav']:.4f} | {rec['shares']:.4f} "
                        f"| {rec['cum_shares']:.4f} | {rec.get('period_return', 'N/A')} |"
                    )
        lines.append("")

    # === D级基金提示 ===
    if unscores:
        lines.append("---")
        lines.append("## 数据不足基金")
        lines.append("")
        for u in unscores:
            lines.append(f"### {u['name']}（{u['code']}）")
            lines.append(f"- **数据完整度**：D")
            lines.append(f"- **原因**：{u.get('error', '核心数据获取失败')}")
            lines.append(f"- **建议**：检查基金代码是否正确，或基金是否已清盘/暂停申购。部分新成立基金可能无足够历史数据。")
            fund_detail = None
            if holdings_data and "by_fund" in holdings_data:
                fund_detail = holdings_data["by_fund"].get(u["code"])
            if fund_detail and fund_detail["current_value"] > 0:
                lines.append(f"- 累计投入：¥{fund_detail['total_cost']:,.2f} | 当前市值：¥{fund_detail['current_value']:,.2f}")
            lines.append("")

    # === 相关性矩阵 ===
    if not correlations.empty:
        lines.append("---")
        lines.append("## 组合层面分析")
        lines.append("")
        lines.append("### 持仓相关性矩阵")
        lines.append("")

        # 添加名称映射
        name_map = {}
        for s in all_funds:
            name_map[s.get("fund_code", s.get("code", ""))] = s.get("fund_name", s.get("name", ""))
        if scores:
            for s in scores:
                name_map[s["fund_code"]] = s["fund_name"]

        codes = list(correlations.columns)
        header = "| 基金代码 | " + " | ".join(c for c in codes) + " |"
        lines.append(header)
        lines.append("|" + "------|" + "|".join("------" for _ in codes) + "|")
        for c1 in codes:
            row = f"| {c1} | "
            vals = []
            for c2 in codes:
                if c1 == c2:
                    vals.append("1.00")
                else:
                    r = correlations.loc[c1, c2]
                    marker = " ⚠️" if abs(r) > 0.85 else ""
                    vals.append(f"{r:.2f}{marker}")
            row += " | ".join(vals) + " |"
            lines.append(row)
        lines.append("")
        lines.append("> ⚠️ 标记表示 Pearson r > 0.85，提示高度相关，存在重复敞口。")

        # 高相关警告
        high_corr_pairs = []
        for i, c1 in enumerate(codes):
            for c2 in list(codes)[i+1:]:
                r = correlations.loc[c1, c2]
                if abs(r) > 0.85:
                    n1 = name_map.get(c1, c1)
                    n2 = name_map.get(c2, c2)
                    high_corr_pairs.append(f"**{n1}** ↔ **{n2}** (r={r:.2f})")
        if high_corr_pairs:
            lines.append("")
            lines.append("**高相关性预警：**")
            for pair in high_corr_pairs:
                lines.append(f"- {pair}，建议合并或降低其中一只仓位")

    # === 压力测试 ===
    if stress_tests:
        lines.append("")
        lines.append("### 压力测试风险线索")
        lines.append("")
        lines.append("| 风险线索 | 受影响基金 | 初始回撤假设 | 风险驱动 |")
        lines.append("|----------|-----------|-------------|----------|")
        for st in stress_tests:
            lines.append(
                f"| {st['scenario_id']}: {st['scenario_desc']} "
                f"| {st['fund_name']} | {st['estimated_drawdown_pct']:.2f}% "
                f"| {st.get('risk_driver', '待 agent 结合当前局势判断')} |"
            )
        lines.append("")
        lines.append("> 上表是基于持仓暴露生成的压力测试初稿，不是最终结论；agent 需结合当前宏观、行业新闻和仓位金额重估冲击幅度。")
        lines.append("")

    # === 新闻资讯分析 ===
    lines.append("---")
    lines.append("## 新闻资讯分析")
    lines.append("")
    lines.append(_render_news_section(news_data or [], scores))
    lines.append("")

    # === 推荐基金 ===
    lines.append("---")
    lines.append("## 推荐基金")
    lines.append("")
    if recommendations:
        lines.append("| # | 代码 | 名称 | 主题 | 综合分 | 近1月 | 持仓相似度 | 分散度 | 推荐理由 |")
        lines.append("|------|------|------|------|------|------|-----------|--------|---------|")
        for i, rec in enumerate(recommendations):
            ret_1m = rec.get("return_1m")
            ret_text = f"{ret_1m:+.2f}%" if isinstance(ret_1m, (int, float)) else "N/A"
            lines.append(
                f"| {i+1} | {rec.get('code', '')} | {rec.get('name', '')} "
                f"| {rec.get('theme', rec.get('type', ''))} "
                f"| {rec.get('score', 0):.3f} | {ret_text} "
                f"| {rec.get('max_similarity', 0):.2f} "
                f"| {rec.get('diversification_score', 0):.2f} "
                f"| {rec.get('reason', '')} |"
            )
        lines.append("")
        if inter_recommendation_correlations and inter_recommendation_correlations.get("warnings"):
            lines.append("> 推荐候选已做内部相似度约束；高相关矩阵不展示，避免把内部筛选工具误读为投资结论。")
            lines.append("")
    else:
        if recommendation_status == "skipped":
            lines.append("- 本次分析跳过推荐模块。若从 UI 生成报告，请取消“跳过推荐”；CLI 请不要传 `--skip-recommend`。")
        else:
            lines.append("- 本次未生成推荐候选。可能原因：新闻热点不足、AKShare 候选基金接口无结果、网络受限或候选与持仓过滤后为空。")
        lines.append("")

    # === 风险提示 ===
    lines.append(risk_disclaimer())

    return "\n".join(lines)


def _render_workflow_focus(
    workflow_context: Dict,
    holdings_data: Dict = None,
    scores: List[Dict] = None,
    news_data: List[Dict] = None,
) -> str:
    lines = ["---", "## 完整工作流分析", ""]
    lines.append(
        f"> 运行日期：{workflow_context.get('run_date')}；"
        f"报告口径日：{workflow_context.get('report_date')}；"
        f"{workflow_context.get('mode_reason', '')}。"
    )
    lines.append("")
    lines.append(_render_trade_day_focus(workflow_context, holdings_data, scores, news_data))
    lines.append("")
    lines.append(_render_non_trade_day_focus(workflow_context, holdings_data, scores, news_data))
    return "\n".join(lines)


def _render_trade_day_focus(
    workflow_context: Dict,
    holdings_data: Dict = None,
    scores: List[Dict] = None,
    news_data: List[Dict] = None,
) -> str:
    lines = ["### 交易相关跟踪", ""]

    qdii_rows = workflow_context.get("qdii_rows") or []
    if qdii_rows:
        lines.append("### QDII 结算状态")
        lines.append("")
        lines.append("| 基金代码 | 基金名称 | 净值日期 | 当前净值 | 真实份额 | 流水模拟份额 | 待确认(¥) | 状态 |")
        lines.append("|----------|---------|----------|---------:|---------:|-------------:|----------:|------|")
        for row in qdii_rows:
            lines.append(
                f"| {row['code']} | {row['name']} | {row.get('nav_date') or '-'} "
                f"| {row.get('current_nav', 0):.4f} "
                f"| {row.get('shares', 0):,.2f} "
                f"| {row.get('simulated_shares', 0):,.2f} "
                f"| {row.get('pending_amount', 0):,.2f} "
                f"| {row.get('settlement_status', '')} |"
            )
        pending_rows = [
            (row, event)
            for row in qdii_rows
            for event in row.get("pending_events", [])
        ]
        if pending_rows:
            lines.append("")
            lines.append("| 待确认基金 | 申购日 | 交易日 | 预计确认日 | 金额(¥) |")
            lines.append("|------------|--------|--------|------------|--------:|")
            for row, event in pending_rows:
                lines.append(
                    f"| {row['name']}（{row['code']}） | {event.get('purchase_date', '')} "
                    f"| {event.get('trade_date', '')} | {event.get('settle_date', '')} "
                    f"| {event.get('amount', 0):,.2f} |"
                )
        lines.append("")

    dca_rows = workflow_context.get("dca_rows") or []
    if dca_rows:
        lines.append("### 定投执行与确认预估")
        lines.append("")
        lines.append("| 基金代码 | 基金名称 | 策略 | 金额(¥) | 下次/当日定投 | 状态 | 交易日 | 净值日 | 预计确认 | 预计收益可见 |")
        lines.append("|----------|---------|------|--------:|---------------|------|--------|--------|----------|--------------|")
        for row in dca_rows:
            lines.append(
                f"| {row['code']} | {row['name']} | {row['frequency']} "
                f"| {row['amount']:,.2f} | {row.get('scheduled_date', '')} "
                f"| {row.get('status', '')} | {row.get('trade_date', '')} "
                f"| {row.get('nav_date', '')} | {row.get('settle_date', '')} "
                f"| {row.get('earnings_visible_after', '')} |"
            )
        lines.append("")

    lines.append("### 大盘环境与当日根因")
    lines.append("")
    lines.append(_render_market_brief(scores, news_data))
    lines.append("")
    lines.append(_render_daily_reasoning(workflow_context, holdings_data, scores))
    lines.append("")
    return "\n".join(lines)


def _render_non_trade_day_focus(
    workflow_context: Dict,
    holdings_data: Dict = None,
    scores: List[Dict] = None,
    news_data: List[Dict] = None,
) -> str:
    lines = ["### 组合复盘与质量检查", ""]

    funds = sorted(
        (holdings_data or {}).get("funds", []),
        key=lambda x: x.get("week_profit") if x.get("week_profit") is not None else x.get("profit", 0),
        reverse=True,
    )
    if funds:
        has_week_data = any(f.get("week_profit") is not None for f in funds)
        total_profit = sum(
            (f.get("week_profit") if f.get("week_profit") is not None else 0)
            for f in funds
        ) if has_week_data else sum(f.get("profit", 0) for f in funds)
        lines.append("#### 本周收益与基金贡献")
        lines.append("")
        profit_label = "本周收益(¥)" if has_week_data else "当前累计收益(¥)"
        lines.append(f"| 基金代码 | 基金名称 | {profit_label} | 收益贡献 | 当前占比 |")
        lines.append("|----------|---------|------------:|---------:|---------:|")
        total_value = (holdings_data or {}).get("total_value", 0)
        for fund in funds:
            profit_value = fund.get("week_profit") if fund.get("week_profit") is not None else fund.get("profit", 0)
            contribution = profit_value / total_profit * 100 if total_profit else 0
            position = fund.get("value", 0) / total_value * 100 if total_value else 0
            lines.append(
                f"| {fund['code']} | {fund['name']} | {profit_value:+,.2f} "
                f"| {contribution:+.2f}% | {position:.2f}% |"
            )
        lines.append("")

    lines.append("#### 风险暴露与再平衡")
    lines.append("")
    lines.append(_render_rebalance_brief(holdings_data, scores))
    lines.append("")

    lines.append("#### 定投质量分析")
    lines.append("")
    lines.append(_render_dca_quality(workflow_context, holdings_data, scores))
    lines.append("")
    return "\n".join(lines)


def _render_market_brief(scores: List[Dict], news_data: List[Dict]) -> str:
    scores = scores or []
    news_data = news_data or []
    avg_score = sum(s.get("composite_score", 0) for s in scores) / len(scores) if scores else 0
    qdii_count = sum(1 for s in scores if "QDII" in s.get("fund_type", ""))
    sentiments = [n.get("sentiment_mean", 0.5) for n in news_data if n.get("sentiment_mean") is not None]
    avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0.5
    mood = "偏正面" if avg_sent > 0.55 else "偏谨慎" if avg_sent < 0.45 else "中性"
    return (
        f"- 组合平均评分：{avg_score:.1f}/100；QDII 覆盖 {qdii_count} 只。\n"
        f"- 新闻情绪均值：{avg_sent:.2f}（{mood}）。\n"
        "- 今日重点先看净值口径、QDII 确认状态和 pending 金额，再解读涨跌原因。"
    )


def _render_daily_reasoning(workflow_context: Dict, holdings_data: Dict, scores: List[Dict]) -> str:
    top_news = workflow_context.get("top_news") or []
    if not top_news:
        return "- 暂无足够新闻数据解释当日资产变化；优先参考基金净值更新和持仓行业暴露。"
    lines = []
    for item in top_news[:5]:
        sentiment = item.get("sentiment", 0.5)
        tone = "利好/支撑" if sentiment > 0.55 else "利空/拖累" if sentiment < 0.45 else "中性"
        lines.append(
            f"- {item.get('name')}（{item.get('code')}）：{tone}，"
            f"{item.get('date', '')} {item.get('headline', '')[:80]}"
        )
    return "\n".join(lines)


def _render_rebalance_brief(holdings_data: Dict, scores: List[Dict]) -> str:
    if not holdings_data:
        return "- 暂无持仓数据。"
    total_value = holdings_data.get("total_value", 0)
    score_map = {s.get("fund_code"): s for s in scores or []}
    lines = []
    for fund in sorted(holdings_data.get("funds", []), key=lambda x: x.get("value", 0), reverse=True):
        pct = fund.get("value", 0) / total_value * 100 if total_value else 0
        score = score_map.get(fund["code"], {})
        level = score.get("score_level", "unknown")
        if pct > 30:
            action = "单基金占比偏高，优先控制新增资金"
        elif level in ("orange", "red"):
            action = "评分偏弱，周末复盘是否降低仓位或暂停定投"
        else:
            action = "维持观察"
        lines.append(f"- {fund['name']}（{fund['code']}）：占比 {pct:.2f}%，{action}。")
    return "\n".join(lines)


def _render_dca_quality(workflow_context: Dict, holdings_data: Dict, scores: List[Dict]) -> str:
    rows = workflow_context.get("dca_rows") or []
    if not rows:
        return "- 当前没有启用定投策略。"
    score_map = {s.get("fund_code"): s for s in scores or []}
    lines = []
    for row in rows:
        score = score_map.get(row["code"], {})
        composite = score.get("composite_score")
        if composite is None:
            advice = "数据不足，先维持小额或暂停新增。"
        elif composite >= 60:
            advice = "评分尚可，定投可维持；回撤加深时可考虑小幅增额。"
        elif composite >= 45:
            advice = "评分中性偏弱，维持但不建议加码。"
        else:
            advice = "评分偏弱，建议暂停或降低定投金额。"
        lines.append(
            f"- {row['name']}（{row['code']}）：{row['frequency']} ¥{row['amount']:,.2f}，"
            f"下次 {row.get('scheduled_date', '')}，{advice}"
        )
    return "\n".join(lines)


def _render_news_section(news_data: List[Dict], scores: List[Dict]) -> str:
    """渲染新闻资讯分析板块。"""
    result = []

    # --- 市场情绪总览 ---
    total_news = sum(n.get("news_count", 0) for n in news_data)
    sentiments = [n.get("sentiment_mean", 0.5) for n in news_data if n.get("sentiment_mean")]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.5

    result.append("### 市场情绪总览")
    result.append("")
    if not news_data:
        result.append("- 未运行到有效新闻结果。请检查新闻接口、网络或分析日志。")
        return "\n".join(result)

    if avg_sentiment > 0.55:
        market_mood = "偏乐观"
        advice = "市场整体情绪积极，可适度保持仓位，关注利好兑现后的回调风险。"
    elif avg_sentiment < 0.45:
        market_mood = "偏悲观"
        advice = "市场整体情绪谨慎，可关注恐慌性下跌中的布局机会，控制仓位等待企稳信号。"
    else:
        market_mood = "中性"
        advice = "市场情绪平衡，维持当前策略，根据各基金评分差异化操作。"

    result.append(f"- **总新闻数**：{total_news} 条")
    result.append(f"- **整体情绪均值**：{avg_sentiment:.2f}（{market_mood}）")
    result.append(f"- **综合判断**：{advice}")
    result.append("")

    # --- 逐基金新闻分析 ---
    result.append("### 逐基金新闻分析")
    result.append("")

    for news_item in news_data:
        code = news_item.get("fund_code", "")
        name = news_item.get("fund_name", code)

        score = next((s for s in scores if s.get("fund_code") == code), None)
        score_emoji = score.get("score_level_emoji", "") if score else ""

        result.append(f"#### {name}（{code}）{score_emoji}")
        result.append("")

        # 情绪统计
        n_count = news_item.get("news_count", 0)
        sent_mean = news_item.get("sentiment_mean", 0.5)
        daily_aggs = news_item.get("daily_aggregates", [])

        pos_rate = 0
        neg_rate = 0
        if daily_aggs:
            latest = daily_aggs[-1]
            pos_rate = latest.get("positive_rate", 0) * 100
            neg_rate = latest.get("negative_rate", 0) * 100
            top_kw = latest.get("top_keywords", [])[:5]

        result.append(f"| 指标 | 数值 |")
        result.append(f"|------|------|")
        result.append(f"| 相关新闻数 | {n_count} 条 |")
        result.append(f"| 情绪均值 | {sent_mean:.2f} |")
        result.append(f"| 正面率 | {pos_rate:.0f}% |")
        result.append(f"| 负面率 | {neg_rate:.0f}% |")
        if daily_aggs and top_kw:
            result.append(f"| 热门关键词 | {'、'.join(top_kw)} |")
        result.append("")

        if news_item.get("status") == "empty":
            result.append(f"- {news_item.get('message', '未获取到相关新闻。')}")
            result.append("")
            continue

        if news_item.get("agent_news_context"):
            result.append("> 新闻情绪为规则初稿；agent 需要结合重仓公司、产业链位置和最新事件做最终研判。")
            result.append("")

        # 情绪趋势（最近 7 天）
        if daily_aggs and len(daily_aggs) >= 2:
            result.append("**情绪趋势：**")
            trend_words = []
            for da in daily_aggs[-7:]:
                d = da.get("date", "")
                sm = da.get("sentiment_mean", 0.5)
                if sm > 0.55:
                    bar = "█" * max(1, int((sm - 0.5) * 20)) + "↗"
                elif sm < 0.45:
                    bar = "█" * max(1, int((0.5 - sm) * 20)) + "↘"
                else:
                    bar = "— →"
                trend_words.append(f"  {d}: {sm:.2f} {bar}")
            result.extend(trend_words)
            result.append("")

        # 情绪解读
        if sent_mean > 0.55:
            interpretation = "近期相关新闻偏正面，市场对该基金关注度高、舆论环境良好，有助于短期净值表现。"
        elif sent_mean < 0.45:
            interpretation = "近期相关新闻偏负面，需警惕情绪传导至净值的风险。若持仓中已有盈利，可考虑设好止损；定投可适当降低单期金额。"
        else:
            interpretation = "近期新闻情绪中性，无明显利好或利空信号。关注后续是否有行业催化事件。"

        result.append(f"**解读：**{interpretation}")
        result.append("")

        # 近期新闻精选
        news_list = news_item.get("news_list", [])
        if news_list:
            result.append("**近期新闻精选：**")
            for n in news_list[:5]:
                title = n.get("title", "").strip()
                date_str = n.get("date", "")
                label = n.get("sentiment_label", "neutral")
                emoji = {"positive": "+", "negative": "-", "neutral": "○"}.get(label, "○")
                if title:
                    result.append(f"- {emoji} [{date_str}] {title[:80]}")
            result.append("")

        # 新闻-净值相关性（如可用）
        corr_val = news_item.get("correlation", 0)
        if abs(corr_val) > 0.3:
            corr_desc = "正相关" if corr_val > 0 else "负相关"
            result.append(f"- 新闻情绪与净值相关性：{corr_val:.2f}（{corr_desc}），新闻情绪对基金净值有一定关联。")
            result.append("")

    return "\n".join(result)
