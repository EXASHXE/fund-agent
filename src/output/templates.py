"""报告模板片段 — 可复用的 Markdown 片段"""
from src.config.shared import effective_report_date


def report_header(scores_count: int) -> str:
    return f"""# 基金组合诊断报告
> 分析日期: {effective_report_date().isoformat()}
> 分析基金数量: {scores_count} 只
"""


def portfolio_overview_table(portfolio_data: dict) -> str:
    """持仓总览表"""
    lines = []
    lines.append("## 一、持仓总览")
    lines.append("")
    lines.append(f"> 评估日期：{effective_report_date().isoformat()}")
    lines.append("")
    lines.append("| 基金代码 | 基金名称 | 持有市值(¥) | 占比 | 成本价 | 累计收益(¥) | 累计收益率 | 年化收益率 | 待确认(¥) | 定投状态 |")
    lines.append("|----------|---------|-----------|------|------|-----------|----------|-----------|----------|---------|")

    total_value = portfolio_data.get("total_value", 0)
    for fund in portfolio_data.get("funds", []):
        pct = f"{fund['value'] / total_value * 100:.2f}%" if total_value else "N/A"
        avg_cost = f"{fund.get('avg_cost', 0):.4f}" if fund.get('avg_cost') else "-"
        pending = fund.get("pending_amount", 0)
        lines.append(
            f"| {fund['code']} | {fund['name']} | {fund['value']:,.2f} "
            f"| {pct} | {avg_cost} | {fund['profit']:+,.2f} "
            f"| {fund['return_pct']:+.2f}% | {fund['annual_return']:+.2f}% "
            f"| {pending:,.2f} "
            f"| {fund.get('dca_status', '未设置')} |"
        )

    total_cost = portfolio_data.get("total_cost", 0)
    total_profit = total_value - total_cost
    total_return = (total_profit / total_cost * 100) if total_cost else 0
    total_pending = portfolio_data.get("total_pending", 0)

    lines.append("")
    lines.append("**组合汇总**（含 0.15% 申购费）")
    lines.append(f"- 总投入：¥{total_cost:,.2f}")
    lines.append(f"- 总市值：¥{total_value:,.2f}")
    lines.append(f"- 总收益：¥{total_profit:+,.2f}")
    lines.append(f"- 总收益率：{total_return:+.2f}%")
    lines.append(f"- 待确认金额：¥{total_pending:,.2f}")
    lines.append(f"- 持有基金数：{portfolio_data.get('fund_count', 0)} 只")
    lines.append("")

    calibration_warnings = portfolio_data.get("calibration_warnings") or []
    if calibration_warnings:
        lines.append("**份额校准提示**")
        lines.append("")
        lines.append("| 基金代码 | 基金名称 | 真实份额 | 流水模拟份额 | 偏差 | 说明 |")
        lines.append("|----------|---------|---------:|-------------:|-----:|------|")
        for item in calibration_warnings:
            rej = item.get("rejected", {})
            lines.append(
                f"| {item.get('code', '')} | {item.get('name', '')} "
                f"| {rej.get('actual_shares', 0):,.2f} "
                f"| {rej.get('computed_shares', 0):,.2f} "
                f"| {rej.get('delta_pct', 0):.2f}% "
                f"| 已按配置真实份额展示，流水需补齐或校准 |"
            )
        lines.append("")

    ledger_warnings = portfolio_data.get("ledger_warnings") or []
    if ledger_warnings:
        has_pending = any(w.get("is_dca_pending") for w in ledger_warnings)
        lines.append("**流水对账提示**")
        lines.append("")
        if has_pending:
            lines.append("| 基金代码 | 基金名称 | 真实成本(¥) | 流水合计(¥) | 差额(¥) | 待确认(¥) | 说明 |")
            lines.append("|----------|---------|------------:|------------:|--------:|----------:|------|")
            for item in ledger_warnings:
                pending_amt = item.get("pending_amount", 0)
                lines.append(
                    f"| {item.get('code', '')} | {item.get('name', '')} "
                    f"| {item.get('actual_cost', 0):,.2f} "
                    f"| {item.get('purchase_amount', 0):,.2f} "
                    f"| {item.get('delta', 0):+,.2f} "
                    f"| {pending_amt:,.2f} "
                    f"| {item.get('reason', '')} |"
                )
        else:
            lines.append("| 基金代码 | 基金名称 | 真实成本(¥) | 流水合计(¥) | 差额(¥) | 说明 |")
            lines.append("|----------|---------|------------:|------------:|--------:|------|")
            for item in ledger_warnings:
                lines.append(
                    f"| {item.get('code', '')} | {item.get('name', '')} "
                    f"| {item.get('actual_cost', 0):,.2f} "
                    f"| {item.get('purchase_amount', 0):,.2f} "
                    f"| {item.get('delta', 0):+,.2f} "
                    f"| {item.get('reason', '')} |"
                )
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
