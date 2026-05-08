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
                    f"| {fund['name']}（{code}） | ¥{fund['value']:,.0f} "
                    f"| {current_pct:.1f}% | {target_pct:.1f}% "
                    f"| ¥{adjust:+,.0f} | {action} |"
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
            lines.append(f"| **持仓市值** | ¥{fund_detail['current_value']:,.0f} |")
            lines.append(f"| **浮动盈亏** | ¥{fund_detail['profit']:+,.0f}（{fund_detail['return_pct']:+.1f}%）|")
        lines.append(f"| **止盈线** | +{s['stop_profit_pct']}% |")
        lines.append(f"| **止损线** | {s['stop_loss_pct']}% |")
        lines.append(f"| **行动逻辑** | {s['action_logic']} |")
        if s.get("annual_volatility"):
            lines.append(f"| **年化波动率** | {s['annual_volatility']:.1f}% |")
        if s.get("max_drawdown_3y"):
            lines.append(f"| **最大回撤(3年)** | {s['max_drawdown_3y']}% |")
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
                f"- 累计投入：¥{fund_detail['total_cost']:,.0f} "
                f"| 当前市值：¥{fund_detail['current_value']:,.0f} "
                f"| 浮动盈亏：¥{fund_detail['profit']:+,.0f}（{fund_detail['return_pct']:+.1f}%）"
                f"| 年化收益：{fund_detail['annual_return']:+.1f}%"
            )
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
                        f"| {i+1} | {d} | ¥{rec['amount']:.0f} "
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
                lines.append(f"- 累计投入：¥{fund_detail['total_cost']:,.0f} | 当前市值：¥{fund_detail['current_value']:,.0f}")
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
                f"| {st['fund_name']} | {st['estimated_drawdown_pct']:.1f}% |"
            )
        lines.append("")

    # === 新闻分析 ===
    if news_data:
        lines.append("---")
        lines.append("## 新闻资讯分析")
        lines.append("")
        for news_item in news_data:
            lines.append(f"### {news_item['fund_name']}（{news_item['fund_code']}）")
            lines.append(f"- 相关新闻数：{news_item.get('news_count', 0)} 条")
            lines.append(f"- 情绪均值：{news_item.get('sentiment_mean', 0):.2f}")

            # Display recent news titles
            news_list = news_item.get("news_list", [])
            if news_list:
                lines.append("")
                lines.append("**近期新闻：**")
                for n in news_list[:5]:
                    title = n.get("title", "").strip()
                    date_str = n.get("date", "")
                    label = n.get("sentiment_label", "neutral")
                    emoji = {"positive": "+", "negative": "-", "neutral": "○"}.get(label, "○")
                    if title:
                        lines.append(f"- {emoji} [{date_str}] {title[:80]}")
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
