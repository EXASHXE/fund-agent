"""报告模板片段 — 可复用的 Markdown 片段"""
from datetime import date


def report_header(scores_count: int) -> str:
    return f"""# 基金组合诊断报告
> 分析日期: {date.today().isoformat()}
> 分析基金数量: {scores_count} 只
"""


def portfolio_overview_table(portfolio_data: dict) -> str:
    """持仓总览表"""
    lines = []
    lines.append("## 一、持仓总览")
    lines.append("")
    lines.append(f"> 评估日期：{date.today().isoformat()}")
    lines.append("")
    lines.append("| 基金代码 | 基金名称 | 持有市值(¥) | 占比 | 累计收益(¥) | 累计收益率 | 年化收益率 | 定投状态 |")
    lines.append("|----------|---------|-----------|------|-----------|----------|-----------|---------|")

    total_value = portfolio_data.get("total_value", 0)
    for fund in portfolio_data.get("funds", []):
        pct = f"{fund['value'] / total_value * 100:.1f}%" if total_value else "N/A"
        lines.append(
            f"| {fund['code']} | {fund['name']} | {fund['value']:,.0f} "
            f"| {pct} | {fund['profit']:+,.0f} "
            f"| {fund['return_pct']:+.1f}% | {fund['annual_return']:+.1f}% "
            f"| {fund.get('dca_status', '未设置')} |"
        )

    total_cost = portfolio_data.get("total_cost", 0)
    total_profit = total_value - total_cost
    total_return = (total_profit / total_cost * 100) if total_cost else 0

    lines.append("")
    lines.append("**组合汇总**（含 0.15% 申购费）")
    lines.append(f"- 总投入：¥{total_cost:,.0f}")
    lines.append(f"- 总市值：¥{total_value:,.0f}")
    lines.append(f"- 总收益：¥{total_profit:+,.0f}")
    lines.append(f"- 总收益率：{total_return:+.2f}%")
    lines.append(f"- 持有基金数：{portfolio_data.get('fund_count', 0)} 只")
    lines.append("")

    return "\n".join(lines)


def risk_disclaimer() -> str:
    return """---

## 风险提示

- 本报告基于历史公共数据和统计模型自动生成，不构成任何形式的投资承诺或保证
- 历史业绩不代表未来表现，市场有风险，投资需谨慎
- 海外市场（QDII）基金额外面临汇率波动、交易时差和流动性风险
- 情景压力测试为理论假设模拟，实际市场可能出现超出假设范围的更极端波动
- 定投是长期策略，短期浮亏属正常现象，请确保有持续现金流支撑
- 投资者应结合自身风险承受能力、流动性需求和投资期限审慎决策
"""
