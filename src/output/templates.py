"""报告模板片段 — 可复用的 Markdown 片段"""
from src.config.shared import effective_report_date


def is_qdii_fund(name: str = "", fund_type: str = "") -> bool:
    """检测结构化 QDII 类型，名称只允许显式的 QDII 标识兜底。"""
    type_value = getattr(fund_type, "value", fund_type)
    if str(type_value or "").strip().lower() == "qdii":
        return True
    return "QDII" in str(name or "").upper()


def qdii_hint(name: str = "", fund_type: str = "") -> str:
    """返回海外净值披露风险提示，不声称当前净值一定为估算值。"""
    return " ⚠️*(海外净值披露可能滞后)*" if is_qdii_fund(name, fund_type) else ""


def report_header(scores_count: int) -> str:
    return f"""# 基金组合诊断报告
> 分析日期: {effective_report_date().isoformat()}
> 分析基金数量: {scores_count} 只
"""


def portfolio_overview_table(portfolio_data: dict) -> str:
    """持仓总览表"""
    lines = []
    lines.append(f"> 评估日期：{effective_report_date().isoformat()}")
    lines.append("")
    lines.append("| 基金代码 | 基金名称 | 持有市值(¥) | 占比 | 成本价 | 累计收益(¥) | 累计收益率 | 年化收益率 | 待确认(¥) | 定投状态 |")
    lines.append("|----------|---------|-----------|------|------|-----------|----------|-----------|----------|---------|")

    total_value = portfolio_data.get("total_value", 0)
    for fund in portfolio_data.get("funds", []):
        value = fund.get("value", 0) or 0
        pct = f"{value / total_value * 100:.2f}%" if total_value else "N/A"
        avg_cost = f"{fund.get('avg_cost', 0):.4f}" if fund.get('avg_cost') else "-"
        pending = fund.get("pending_amount", 0)
        profit = f"{fund['profit']:+,.2f}" if fund.get("profit") is not None else "-"
        return_pct = f"{fund['return_pct']:+.2f}%" if fund.get("return_pct") is not None else "-"
        annual_return = f"{fund['annual_return']:+.2f}%" if fund.get("annual_return") is not None else "-"
        lines.append(
            f"| {fund['code']} | {fund['name']}{qdii_hint(fund.get('name', ''), fund.get('fund_type', ''))} | {value:,.2f} "
            f"| {pct} | {avg_cost} | {profit} "
            f"| {return_pct} | {annual_return} "
            f"| {pending:,.2f} "
            f"| {fund.get('dca_status', '未设置')} |"
        )

    total_pending = portfolio_data.get("total_pending", 0)

    lines.append("")
    lines.append("**组合汇总**（含 0.15% 申购费）")
    lines.append(f"- 总市值：¥{total_value:,.2f}")
    if portfolio_data.get("total_cost") is not None:
        total_cost = portfolio_data["total_cost"]
        total_profit = portfolio_data.get("total_profit", total_value - total_cost)
        total_return = portfolio_data.get(
            "total_return_pct",
            (total_profit / total_cost * 100) if total_cost else 0,
        )
        lines.append(f"- 总投入：¥{total_cost:,.2f}")
        lines.append(f"- 总收益：¥{total_profit:+,.2f}")
        lines.append(f"- 总收益率：{total_return:+.2f}%")
    else:
        lines.append("- 总投入 / 总收益 / 总收益率：数据未提供")
    lines.append(f"- 待确认金额：¥{total_pending:,.2f}")
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
