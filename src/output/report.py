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
    unscores: List[Dict] = None,
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
        lines.append(f"| **行动逻辑** | {s['action_logic']} |")
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
        lines.append("### 情景压力测试")
        lines.append("")
        lines.append("| 情景 | 受影响基金 | 预估回撤 |")
        lines.append("|------|-----------|---------|")
        for st in stress_tests:
            lines.append(
                f"| {st['scenario_id']}: {st['scenario_desc']} "
                f"| {st['fund_name']} | {st['estimated_drawdown_pct']:.2f}% |"
            )
        lines.append("")

    # === 新闻资讯分析 ===
    if news_data:
        lines.append("---")
        lines.append("## 新闻资讯分析")
        lines.append("")
        lines.append(_render_news_section(news_data, scores))
        lines.append("")

    # === 推荐基金 ===
    if recommendations:
        lines.append("---")
        lines.append("## 推荐基金")
        lines.append("")
        lines.append("| # | 代码 | 名称 | 类型 | 与持仓平均相关 | 推荐理由 |")
        lines.append("|------|------|------|------|---------------|---------|")
        for i, rec in enumerate(recommendations):
            lines.append(
                f"| {i+1} | {rec.get('code', '')} | {rec.get('name', '')} "
                f"| {rec.get('type', '')} | {rec.get('avg_corr', 0):.2f} "
                f"| {rec.get('reason', '')} |"
            )
        lines.append("")

    # === 风险提示 ===
    lines.append(risk_disclaimer())

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
