"""Deterministic adapter: compose_personal_fund_report → render_advisory_report_markdown.

Converts the 27-section compose_personal_fund_report vocabulary to the 10-section
vocabulary expected by render_advisory_report_markdown. Pure, deterministic, no
network/provider/LLM/decision-support calls.
"""

from __future__ import annotations

from typing import Any


def adapt_personal_fund_report_to_advisory_markdown_report(
    final_report: dict[str, Any],
    *,
    analysis_mode: str = "report_only",
    decision: dict[str, Any] | None = None,
    execution_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert compose_personal_fund_report output to render_advisory_report_markdown shape.

    Mapping:
      direct_answer        ← executive_summary
      portfolio_overview   ← portfolio_snapshot + allocation_and_exposure
      current_risks        ← risk_flags + professional_diagnostics
      position_diagnostics ← pnl_and_cost_basis + position_contribution
      evidence_status      ← evidence_status + evidence_appendix
      data_gaps            ← missing_data + data_completeness_and_limitations + warnings
      action_boundary      ← action_watchlist + rebalance_plan (deterministic boundary)
      suggested_next_steps ← suggested_next_checks + research_query_plan
      decision_explanation ← analysis_mode / decision presence
      risk_disclaimer      ← explicit bullets (deterministic default)
    """
    if not isinstance(final_report, dict):
        final_report = {}

    source_sections: list[dict[str, Any]] = final_report.get("report_sections", [])
    if isinstance(source_sections, dict):
        source_sections = source_sections.get("report_sections", source_sections.get("sections", []))
    if not isinstance(source_sections, list):
        source_sections = []

    warnings: list[str] = _string_list(final_report.get("warnings", []))

    index: dict[str, dict[str, Any]] = {}
    for s in source_sections:
        if isinstance(s, dict) and s.get("id"):
            index[str(s["id"])] = s

    adapted_sections: list[dict[str, Any]] = []

    adapted_sections.append(_build_direct_answer(index, analysis_mode, decision))
    adapted_sections.append(_build_portfolio_overview(index))
    adapted_sections.append(_build_current_risks(index))
    adapted_sections.append(_build_position_diagnostics(index))
    adapted_sections.append(_build_evidence_status(index))
    adapted_sections.append(_build_data_gaps(index, warnings))
    adapted_sections.append(_build_action_boundary(index, analysis_mode))
    adapted_sections.append(_build_suggested_next_steps(index))
    adapted_sections.append(_build_decision_explanation(analysis_mode, decision, execution_ledger))
    adapted_sections.append(_build_risk_disclaimer())

    quality_gate = final_report.get("quality_gate", {})
    adapted_quality = {
        "status": _quality_gate_status(quality_gate),
        "issues": _quality_gate_issues(quality_gate),
    }

    return {
        "report_sections": adapted_sections,
        "analysis_mode": analysis_mode,
        "decision": decision,
        "execution_ledger": execution_ledger,
        "quality_gate": adapted_quality,
    }


def _find_section(index: dict[str, dict[str, Any]], section_id: str) -> dict[str, Any] | None:
    return index.get(section_id)


def _build_direct_answer(
    index: dict[str, dict[str, Any]],
    analysis_mode: str,
    decision: dict[str, Any] | None,
) -> dict[str, Any]:
    es = _find_section(index, "executive_summary")
    bullets: list[str] = list(_string_list(es.get("bullets") if es else []))
    status = str(es.get("status", "MISSING")) if es else "MISSING"
    data_sources: list[str] = list(_string_list(es.get("data_sources") if es else []))
    limitations: list[str] = list(_string_list((es.get("limitations") if es else None) or []))

    if status == "MISSING":
        limitations.append("Executive summary section is missing from composed report.")

    mode_note = ""
    if analysis_mode == "report_only":
        mode_note = "本报告为分析报告模式，不包含正式交易决策。"
    elif analysis_mode == "soft_action_advice":
        mode_note = "本报告包含操作建议，但不包含正式交易决策。"
    elif analysis_mode == "formal_trade_decision":
        if decision is not None:
            mode_note = "本报告包含正式交易决策。"
        else:
            mode_note = "请求正式交易决策模式，但决策尚未生成。"
    if mode_note:
        bullets.append(mode_note)

    return _adapted_section("direct_answer", status, bullets, data_sources, limitations)


def _build_portfolio_overview(index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    snapshot = _find_section(index, "portfolio_snapshot")
    allocation = _find_section(index, "allocation_and_exposure")

    bullets: list[str] = []
    data_sources: list[str] = []
    limitations: list[str] = []
    statuses: list[str] = []

    if snapshot:
        bullets.extend(_string_list(snapshot.get("bullets")))
        data_sources.extend(_string_list(snapshot.get("data_sources")))
        limitations.extend(_string_list(snapshot.get("limitations")))
        statuses.append(str(snapshot.get("status", "MISSING")))
    else:
        limitations.append("Portfolio snapshot section is missing.")
        statuses.append("MISSING")

    if allocation:
        bullets.extend(_string_list(allocation.get("bullets")))
        data_sources.extend(_string_list(allocation.get("data_sources")))
        limitations.extend(_string_list(allocation.get("limitations")))
        statuses.append(str(allocation.get("status", "MISSING")))
    else:
        limitations.append("Allocation and exposure section is missing.")
        statuses.append("MISSING")

    status = _worst_status(statuses)
    return _adapted_section("portfolio_overview", status, bullets, data_sources, limitations)


def _build_current_risks(index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    risk_flags = _find_section(index, "risk_flags")
    prof_diag = _find_section(index, "professional_diagnostics")

    bullets: list[str] = []
    data_sources: list[str] = []
    limitations: list[str] = []
    statuses: list[str] = []

    if risk_flags:
        bullets.extend(_string_list(risk_flags.get("bullets")))
        data_sources.extend(_string_list(risk_flags.get("data_sources")))
        limitations.extend(_string_list(risk_flags.get("limitations")))
        statuses.append(str(risk_flags.get("status", "MISSING")))
    else:
        limitations.append("Risk flags section is missing.")
        statuses.append("MISSING")

    if prof_diag:
        bullets.extend(_string_list(prof_diag.get("bullets")))
        data_sources.extend(_string_list(prof_diag.get("data_sources")))
        limitations.extend(_string_list(prof_diag.get("limitations")))
        statuses.append(str(prof_diag.get("status", "MISSING")))

    status = _worst_status(statuses)
    return _adapted_section("current_risks", status, bullets, data_sources, limitations)


def _build_position_diagnostics(index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pnl = _find_section(index, "pnl_and_cost_basis")
    pos = _find_section(index, "position_contribution")

    bullets: list[str] = []
    data_sources: list[str] = []
    limitations: list[str] = []
    statuses: list[str] = []

    if pnl:
        bullets.extend(_string_list(pnl.get("bullets")))
        data_sources.extend(_string_list(pnl.get("data_sources")))
        limitations.extend(_string_list(pnl.get("limitations")))
        statuses.append(str(pnl.get("status", "MISSING")))
    else:
        limitations.append("PnL and cost basis section is missing.")
        statuses.append("MISSING")

    if pos:
        bullets.extend(_string_list(pos.get("bullets")))
        data_sources.extend(_string_list(pos.get("data_sources")))
        limitations.extend(_string_list(pos.get("limitations")))
        statuses.append(str(pos.get("status", "MISSING")))

    status = _worst_status(statuses)
    return _adapted_section("position_diagnostics", status, bullets, data_sources, limitations)


def _build_evidence_status(index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev = _find_section(index, "evidence_status")
    appendix = _find_section(index, "evidence_appendix")

    bullets: list[str] = []
    data_sources: list[str] = []
    limitations: list[str] = []
    statuses: list[str] = []

    if ev:
        bullets.extend(_string_list(ev.get("bullets")))
        data_sources.extend(_string_list(ev.get("data_sources")))
        limitations.extend(_string_list(ev.get("limitations")))
        statuses.append(str(ev.get("status", "MISSING")))
    else:
        limitations.append("Evidence status section is missing.")
        statuses.append("MISSING")

    if appendix:
        bullets.extend(_string_list(appendix.get("bullets")))
        data_sources.extend(_string_list(appendix.get("data_sources")))
        limitations.extend(_string_list(appendix.get("limitations")))
        statuses.append(str(appendix.get("status", "MISSING")))

    status = _worst_status(statuses)
    return _adapted_section("evidence_status", status, bullets, data_sources, limitations)


def _build_data_gaps(index: dict[str, dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    missing = _find_section(index, "missing_data")
    completeness = _find_section(index, "data_completeness_and_limitations")

    bullets: list[str] = []
    data_sources: list[str] = []
    limitations: list[str] = []
    statuses: list[str] = []

    if missing:
        bullets.extend(_string_list(missing.get("bullets")))
        data_sources.extend(_string_list(missing.get("data_sources")))
        limitations.extend(_string_list(missing.get("limitations")))
        statuses.append(str(missing.get("status", "MISSING")))
    else:
        limitations.append("Missing data section is unavailable.")
        statuses.append("MISSING")

    if completeness:
        bullets.extend(_string_list(completeness.get("bullets")))
        data_sources.extend(_string_list(completeness.get("data_sources")))
        limitations.extend(_string_list(completeness.get("limitations")))
        statuses.append(str(completeness.get("status", "MISSING")))
    else:
        limitations.append("Data completeness and limitations section is missing.")
        statuses.append("MISSING")

    for w in warnings:
        if w not in bullets:
            bullets.append(f"Warning: {w}")

    status = _worst_status(statuses)
    return _adapted_section("data_gaps", status, bullets, data_sources, limitations)


def _build_action_boundary(
    index: dict[str, dict[str, Any]],
    analysis_mode: str,
) -> dict[str, Any]:
    watchlist = _find_section(index, "action_watchlist")
    rebalance = _find_section(index, "rebalance_plan")

    bullets: list[str] = []
    data_sources: list[str] = []
    limitations: list[str] = []
    statuses: list[str] = []

    if watchlist:
        bullets.extend(_string_list(watchlist.get("bullets")))
        data_sources.extend(_string_list(watchlist.get("data_sources")))
        limitations.extend(_string_list(watchlist.get("limitations")))
        statuses.append(str(watchlist.get("status", "MISSING")))

    if rebalance:
        bullets.extend(_string_list(rebalance.get("bullets")))
        data_sources.extend(_string_list(rebalance.get("data_sources")))
        limitations.extend(_string_list(rebalance.get("limitations")))
        statuses.append(str(rebalance.get("status", "MISSING")))

    boundary_lines: list[str] = [
        "确定性操作边界:",
        "- 允许: 分析报告、风险评估、数据诊断",
        "- 阻止: 正式交易决策、经纪执行",
        "- 不包含经纪执行指令",
    ]
    if analysis_mode in ("formal_trade_decision", "soft_action_advice"):
        boundary_lines = [
            "确定性操作边界:",
            "- 允许: 分析报告、操作建议、风险评估",
            "- 阻止: 经纪执行",
            "- 不包含经纪执行指令",
        ]

    bullets.extend(boundary_lines)

    status = "PARTIAL" if not statuses else _worst_status(statuses)
    return _adapted_section("action_boundary", status, bullets, data_sources, limitations)


def _build_suggested_next_steps(index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    next_checks = _find_section(index, "suggested_next_checks")
    research = _find_section(index, "research_query_plan")

    bullets: list[str] = []
    data_sources: list[str] = []
    limitations: list[str] = []
    statuses: list[str] = []

    if next_checks:
        bullets.extend(_string_list(next_checks.get("bullets")))
        data_sources.extend(_string_list(next_checks.get("data_sources")))
        limitations.extend(_string_list(next_checks.get("limitations")))
        statuses.append(str(next_checks.get("status", "MISSING")))
    else:
        limitations.append("Suggested next checks section is missing.")
        statuses.append("MISSING")

    if research:
        bullets.extend(_string_list(research.get("bullets")))
        data_sources.extend(_string_list(research.get("data_sources")))
        limitations.extend(_string_list(research.get("limitations")))
        statuses.append(str(research.get("status", "MISSING")))

    status = _worst_status(statuses)
    return _adapted_section("suggested_next_steps", status, bullets, data_sources, limitations)


def _build_decision_explanation(
    analysis_mode: str,
    decision: dict[str, Any] | None,
    execution_ledger: dict[str, Any] | None,
) -> dict[str, Any]:
    bullets: list[str] = []

    if analysis_mode == "report_only":
        bullets.append("本报告为分析报告模式，未调用决策支持。")
        bullets.append("如需正式交易决策，请在输入中设置 analysis_mode: formal_trade_decision。")
        status = "OK"
    elif analysis_mode == "soft_action_advice":
        bullets.append("本报告包含操作建议，但未生成正式交易决策。")
        bullets.append("如需正式交易决策，请在输入中设置 analysis_mode: formal_trade_decision。")
        status = "OK"
    elif analysis_mode == "formal_trade_decision":
        if decision is None:
            bullets.append("正式决策未生成。可能原因：")
            bullets.append("- 证据不足，无法生成正式决策")
            bullets.append("- 决策支持被约束阻止")
            bullets.append("- 数据缺口导致决策受阻")
            status = "PARTIAL"
        else:
            action = decision.get("action", "UNKNOWN")
            amount = decision.get("execution_amount", 0)
            fund_code = decision.get("fund_code", "")
            bullets.append(f"正式决策已生成: {action} {fund_code} 金额 {amount}")
            anchors = _string_list(decision.get("evidence_anchors") or [])
            if anchors:
                bullets.append("证据锚定:")
                bullets.extend([f"  - {a}" for a in anchors])
            bullets.append("不包含经纪执行指令")
            status = "OK"
    else:
        bullets.append(f"未知分析模式: {analysis_mode}")
        status = "MISSING"

    return _adapted_section("decision_explanation", status, bullets, ["analysis_mode"], [])


def _build_risk_disclaimer() -> dict[str, Any]:
    bullets = [
        "本报告由 fund-agent 确定性引擎生成，不构成投资建议",
        "基金过往业绩不代表未来表现",
        "投资有风险，入市需谨慎",
        "本系统不执行任何经纪操作",
        "数据可能存在延迟或缺失",
    ]
    return _adapted_section("risk_disclaimer", "OK", bullets, ["system"], [])


def _adapted_section(
    section_id: str,
    status: str,
    bullets: list[str],
    data_sources: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    valid_statuses = {"OK", "PARTIAL", "MISSING"}
    clean_status = status if status in valid_statuses else "MISSING"
    return {
        "id": section_id,
        "title": section_id,
        "status": clean_status,
        "bullets": _unique_strings(bullets),
        "data_sources": _unique_strings(data_sources),
        "limitations": _unique_strings(limitations),
    }


def _worst_status(statuses: list[str]) -> str:
    priority = {"MISSING": 3, "PARTIAL": 2, "OK": 1}
    worst = "OK"
    worst_prio = 0
    for s in statuses:
        p = priority.get(s, 0)
        if p > worst_prio:
            worst = s
            worst_prio = p
    return worst


def _quality_gate_status(quality_gate: dict[str, Any]) -> str:
    if not isinstance(quality_gate, dict):
        return "unknown"
    grade = str(quality_gate.get("grade", "D"))
    can_publish = quality_gate.get("can_publish_professional_report", False)
    if can_publish:
        return f"PASS (grade {grade})"
    return f"BLOCKED (grade {grade})"


def _quality_gate_issues(quality_gate: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if isinstance(quality_gate, dict):
        reason = quality_gate.get("reason")
        if isinstance(reason, str) and reason:
            issues.append(reason)
    return issues


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _unique_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
