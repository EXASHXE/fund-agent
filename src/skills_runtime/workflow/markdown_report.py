"""Deterministic markdown report renderer for zh-CN advisory reports.

Consumes existing final_report output and produces markdown sections.
No LLM generation. Deterministic renderer only.
"""

from __future__ import annotations

from typing import Any


REQUIRED_ZH_CN_SECTIONS = [
    ("direct_answer", "直接回答"),
    ("portfolio_overview", "组合概览"),
    ("current_risks", "当前主要风险"),
    ("position_diagnostics", "持仓诊断"),
    ("evidence_status", "证据状态"),
    ("data_gaps", "数据缺口与限制"),
    ("action_boundary", "操作边界"),
    ("suggested_next_steps", "建议下一步"),
    ("decision_explanation", "决策说明"),
    ("risk_disclaimer", "风险提示"),
]


def render_advisory_report_markdown(
    report: dict[str, Any],
    *,
    locale: str = "zh-CN",
) -> str:
    """Render deterministic zh-CN markdown from structured final_report output.

    If decision_support was not called, states this is report-only / soft advice.
    If decision_support was called and blocked, explains blockers.
    If formal decision exists, includes action table with evidence anchors.
    """
    if not isinstance(report, dict):
        return "# Error: invalid report input\n"

    sections = report.get("report_sections", [])
    if isinstance(sections, dict):
        sections = sections.get("report_sections", sections.get("sections", []))
    if not isinstance(sections, list):
        sections = []

    decision = report.get("decision")
    ledger = report.get("execution_ledger")
    quality_gate = report.get("quality_gate", {})
    analysis_mode = report.get("analysis_mode", "report_only")

    lines: list[str] = ["# 基金组合分析报告", ""]

    for section_id, section_title in REQUIRED_ZH_CN_SECTIONS:
        section_data = _find_section(sections, section_id)
        lines.append(f"## {_section_number(section_id)} {section_title}")
        lines.append("")
        lines.extend(_render_section_content(section_id, section_data, analysis_mode, decision, ledger))
        lines.append("")

    if quality_gate:
        lines.append("## 质量门控")
        lines.append("")
        gate_status = quality_gate.get("status", "unknown")
        lines.append(f"- 状态: {gate_status}")
        if quality_gate.get("issues"):
            for issue in quality_gate["issues"]:
                lines.append(f"- 问题: {issue}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*本报告由 fund-agent 确定性引擎生成，不构成投资建议。*")
    lines.append("*不包含经纪执行指令。*")

    return "\n".join(lines)


def _section_number(section_id: str) -> str:
    for i, (sid, _) in enumerate(REQUIRED_ZH_CN_SECTIONS, 1):
        if sid == section_id:
            return f"{i}."
    return ""


def _find_section(sections: list[dict[str, Any]], section_id: str) -> dict[str, Any] | None:
    for s in sections:
        if isinstance(s, dict) and s.get("id") == section_id:
            return s
    return None


def _render_section_content(
    section_id: str,
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    renderer = _SECTION_RENDERERS.get(section_id, _render_generic_section)
    return renderer(section_data, analysis_mode, decision, ledger)


def _render_direct_answer(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', bullet.get('content', str(bullet)))}")
    else:
        lines.append("- 组合分析报告已生成，请查看以下各节详情。")

    if analysis_mode == "report_only":
        lines.append("")
        lines.append("> 本报告为分析报告模式，不包含正式交易决策。")
    elif analysis_mode == "soft_action_advice":
        lines.append("")
        lines.append("> 本报告包含操作建议，但不包含正式交易决策。")
    return lines


def _render_portfolio_overview(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', str(bullet))}")
    else:
        lines.append("- 组合数据待补充。")
    return lines


def _render_current_risks(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', str(bullet))}")
    else:
        lines.append("- 风险评估待补充。")
    return lines


def _render_position_diagnostics(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', str(bullet))}")
    else:
        lines.append("- 持仓诊断待补充。")
    return lines


def _render_evidence_status(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', str(bullet))}")
    else:
        lines.append("- 证据状态待补充。")
    return lines


def _render_data_gaps(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', str(bullet))}")
    else:
        lines.append("- 数据缺口待补充。")
    return lines


def _render_action_boundary(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if analysis_mode == "report_only":
        lines.append("| 类别 | 说明 |")
        lines.append("|------|------|")
        lines.append("| 允许 | 分析报告、风险评估、数据诊断 |")
        lines.append("| 阻止 | 正式交易决策、经纪执行 |")
        lines.append("| 需更多数据 | 正式决策需要完整证据链 |")
    elif analysis_mode == "soft_action_advice":
        lines.append("| 类别 | 说明 |")
        lines.append("|------|------|")
        lines.append("| 允许 | 分析报告、操作建议、风险评估 |")
        lines.append("| 阻止 | 正式交易决策、经纪执行 |")
        lines.append("| 需更多数据 | 正式决策需要完整证据链 |")
    else:
        lines.append("| 类别 | 说明 |")
        lines.append("|------|------|")
        lines.append("| 允许 | 分析报告、操作建议、正式决策 |")
        lines.append("| 阻止 | 经纪执行 |")
        lines.append("| 需更多数据 | 活跃交易需要证据锚定 |")
    lines.append("")
    lines.append("> **不包含经纪执行指令**")
    return lines


def _render_suggested_next_steps(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', str(bullet))}")
    else:
        lines.append("- 建议补充完整数据后重新分析。")
    return lines


def _render_decision_explanation(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if analysis_mode == "report_only":
        lines.append("本报告为分析报告模式，**未调用决策支持**。")
        lines.append("")
        lines.append("如需正式交易决策，请在输入中设置 `analysis_mode: formal_trade_decision`。")
    elif analysis_mode == "soft_action_advice":
        lines.append("本报告包含操作建议，但**未生成正式交易决策**。")
        lines.append("")
        lines.append("如需正式交易决策，请在输入中设置 `analysis_mode: formal_trade_decision`。")
    elif decision is None:
        lines.append("正式决策未生成。可能原因：")
        lines.append("- 证据不足，无法生成正式决策")
        lines.append("- 决策支持被约束阻止")
        lines.append("- 数据缺口导致决策受阻")
    else:
        lines.append("正式决策已生成：")
        lines.append("")
        action = decision.get("action", "UNKNOWN")
        amount = decision.get("execution_amount", 0)
        fund_code = decision.get("fund_code", "")
        lines.append(f"- 操作: {action}")
        lines.append(f"- 基金: {fund_code}")
        lines.append(f"- 金额: {amount}")
        if decision.get("evidence_anchors"):
            lines.append("- 证据锚定:")
            for anchor in decision["evidence_anchors"]:
                lines.append(f"  - {anchor}")
        lines.append("")
        lines.append("> **不包含经纪执行指令**")
    return lines


def _render_risk_disclaimer(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    return [
        "- 本报告由确定性引擎生成，不构成投资建议",
        "- 基金过往业绩不代表未来表现",
        "- 投资有风险，入市需谨慎",
        "- 本系统不执行任何经纪操作",
        "- 数据可能存在延迟或缺失",
    ]


def _render_generic_section(
    section_data: dict[str, Any] | None,
    analysis_mode: str,
    decision: dict[str, Any] | None,
    ledger: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if section_data and section_data.get("bullets"):
        for bullet in section_data["bullets"]:
            if isinstance(bullet, str):
                lines.append(f"- {bullet}")
            elif isinstance(bullet, dict):
                lines.append(f"- {bullet.get('text', str(bullet))}")
    elif section_data and section_data.get("status") == "MISSING":
        lines.append("- 数据缺失，本节暂无内容。")
    return lines


_SECTION_RENDERERS: dict[str, Any] = {
    "direct_answer": _render_direct_answer,
    "portfolio_overview": _render_portfolio_overview,
    "current_risks": _render_current_risks,
    "position_diagnostics": _render_position_diagnostics,
    "evidence_status": _render_evidence_status,
    "data_gaps": _render_data_gaps,
    "action_boundary": _render_action_boundary,
    "suggested_next_steps": _render_suggested_next_steps,
    "decision_explanation": _render_decision_explanation,
    "risk_disclaimer": _render_risk_disclaimer,
}
