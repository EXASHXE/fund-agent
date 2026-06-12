"""Chinese (zh-CN) report helpers.

Deterministic Chinese summary, blocker/downgraded reason builders,
and section title localization. No LLM.
"""

from __future__ import annotations

from typing import Any


ZH_CN_SECTION_TITLES: dict[str, str] = {
    "direct_answer": "直接回答",
    "evidence_status": "证据状态",
    "portfolio_diagnosis": "组合诊断",
    "decision_explanation": "决策说明",
    "action_boundary": "操作边界",
    "recommended_next_steps": "建议下一步",
    "summary": "摘要",
    "limitations": "限制与警告",
}


def build_zh_blocked_reason(
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
) -> str:
    """Build a natural Chinese explanation for why a decision was blocked."""
    reasons: list[str] = []

    analysis_plan = fa_artifacts.get("analysis_plan", {})
    if isinstance(analysis_plan, dict):
        blockers = analysis_plan.get("blockers", [])
        if isinstance(blockers, list):
            for b in blockers:
                b_str = str(b)
                if "redemption_fee" in b_str:
                    reasons.append("短期赎回费阻断")
                elif "right_side" in b_str:
                    reasons.append("右侧信号未确认")
                elif "event_hype" in b_str:
                    reasons.append("事件催化失效")
                elif "cash_deployment" in b_str:
                    reasons.append("现金部署未就绪")
                else:
                    reasons.append(b_str)

    decision = ds_artifacts.get("decision", {})
    if isinstance(decision, dict):
        blocked_by = decision.get("blocked_by", [])
        if isinstance(blocked_by, list):
            for b in blocked_by:
                b_str = str(b)
                if "redemption_fee" in b_str:
                    reasons.append("赎回费风险")
                elif "right_side" in b_str:
                    reasons.append("右侧确认缺失")
                elif "evidence" in b_str:
                    reasons.append("证据不足")
                elif "profit" in b_str:
                    reasons.append("盈利保护")
                elif "constraint" in b_str:
                    reasons.append("约束限制")
                else:
                    reasons.append(b_str)

    seen: set[str] = set()
    unique: list[str] = []
    for r in reasons:
        if r not in seen:
            unique.append(r)
            seen.add(r)

    if unique:
        return f"已评估的正式决策被阻断（原因：{'、'.join(unique[:3])}），当前不应执行操作。"
    return "已评估的正式决策被阻断，当前不应执行操作。"


def build_zh_downgraded_reason(
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
) -> str:
    """Build a natural Chinese explanation for why a decision was downgraded."""
    reasons: list[str] = []

    decision = ds_artifacts.get("decision", {})
    if isinstance(decision, dict):
        codes = decision.get("decision_reason_codes", [])
        if isinstance(codes, list):
            for c in codes:
                c_str = str(c)
                if "EVIDENCE_MISSING" in c_str:
                    reasons.append("证据缺失")
                elif "INSUFFICIENT_EVIDENCE" in c_str:
                    reasons.append("证据不足")
                elif "REDEMPTION_FEE" in c_str:
                    reasons.append("赎回费风险")
                elif "RIGHT_SIDE" in c_str:
                    reasons.append("右侧信号未确认")
                elif "PROFIT_PROTECTION" in c_str:
                    reasons.append("盈利保护")
                elif "CONSTRAINT" in c_str:
                    reasons.append("约束限制")
                elif "BUDGET" in c_str:
                    reasons.append("预算不足")
                elif "DOWNGRADED" in c_str:
                    reasons.append("已降级")

    seen: set[str] = set()
    unique: list[str] = []
    for r in reasons:
        if r not in seen:
            unique.append(r)
            seen.add(r)

    if unique:
        return f"主动操作请求已被降级为被动等待建议（原因：{'、'.join(unique[:3])}）。"
    return "主动操作请求已被降级为被动等待建议。"


def build_chinese_summary(
    *,
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    ds_has_decision: bool,
    decision_status: str,
    eg: dict[str, Any],
    md: dict[str, Any],
    intents: list[str] | None = None,
) -> dict[str, Any]:
    """Build a natural Chinese summary suitable for direct user display."""
    bullets: list[str] = []
    intent_set = set(intents or [])

    # Portfolio overview
    portfolio_summary = fa_artifacts.get("portfolio_summary", {})
    if isinstance(portfolio_summary, dict):
        total_value = portfolio_summary.get("total_value", "")
        position_count = portfolio_summary.get("position_count", 0)
        if total_value and position_count:
            bullets.append(f"当前组合总市值为 {total_value}，共持有 {position_count} 只基金。")

    # Decision status in Chinese
    status_map = {
        "FORMAL_DECISION": "已生成正式决策，包含证据锚点和具体操作指引。",
        "BLOCKED": build_zh_blocked_reason(fa_artifacts, ds_artifacts),
        "DOWNGRADED": build_zh_downgraded_reason(fa_artifacts, ds_artifacts),
        "NO_FORMAL_DECISION": "未生成正式决策，当前输出为分析报告。",
    }
    status_cn = status_map.get(decision_status, "决策状态：待定。")
    bullets.append(status_cn)

    # Evidence summary
    graph_stats = eg.get("graph", {}).get("stats", {})
    if isinstance(graph_stats, dict):
        total = graph_stats.get("total", 0)
        hard = graph_stats.get("hard", 0)
        soft = graph_stats.get("soft", 0)
        if total == 0:
            bullets.append("当前证据图为空，分析基于持仓快照基础数据。缺少 news/sentiment/benchmark/fee evidence。")
        else:
            parts = []
            if hard:
                parts.append(f"硬证据 {hard} 条")
            if soft:
                parts.append(f"软证据 {soft} 条")
            bullets.append(f"证据状态：{'，'.join(parts)}。共 {total} 条证据项。")

    # Fee blocker
    redemption = fa_artifacts.get("redemption_fee_risk", {})
    if not (isinstance(redemption, dict) and redemption):
        prof_diag = fa_artifacts.get("professional_diagnostics", {})
        if isinstance(prof_diag, dict):
            redemption = prof_diag.get("redemption_fee_risk", {})
    if isinstance(redemption, dict) and redemption.get("has_blocker"):
        affected = redemption.get("affected_funds", [])
        fund_names = _get_fund_names(affected, fa_artifacts)
        bullets.append(f"赎回费风险：{', '.join(fund_names) if fund_names else '部分持仓'} 存在短期赎回费阻断，当前不建议主动卖出或减仓。")
    elif isinstance(redemption, dict) and redemption.get("has_warning"):
        affected = redemption.get("affected_funds", [])
        fund_names = _get_fund_names(affected, fa_artifacts)
        bullets.append(f"赎回费提示：{', '.join(fund_names) if fund_names else '部分持仓'} 存在短期赎回费，请确认赎回费率。")

    # Right-side unconfirmed
    right_side = fa_artifacts.get("right_side_confirmation_diagnostics", {})
    if isinstance(right_side, dict):
        rs_items = right_side.get("items", [])
        if isinstance(rs_items, list):
            for item in rs_items:
                if isinstance(item, dict) and item.get("right_side_confirmed") is False:
                    fund = item.get("fund_code") or item.get("fund_name", "")
                    bullets.append(f"{fund}：右侧信号尚未确认，建议继续观察，不宜追涨或补仓。")

    # Profit protection
    profit = fa_artifacts.get("profit_protection_diagnostics", {})
    if isinstance(profit, dict):
        p_items = profit.get("items", [])
        if isinstance(p_items, list):
            for item in p_items:
                if isinstance(item, dict) and str(item.get("profit_level", "")) in ("high", "very_high"):
                    fund = item.get("fund_code") or item.get("fund_name", "")
                    action = item.get("suggested_analysis_action", "")
                    principal = item.get("principal_recovered", "")
                    if principal == "likely":
                        bullets.append(f"{fund}：盈利水平较高且本金可能已回收，可根据风险偏好考虑部分减仓控制风险，不建议一次性清仓。")
                    else:
                        bullets.append(f"{fund}：盈利水平较高（建议：{action}），本金回收状态未知，建议先确认交易记录再决策。")

    # Cash deployment
    cash = fa_artifacts.get("cash_deployment_diagnostics", {})
    if isinstance(cash, dict):
        c_summary = cash.get("summary", {})
        if isinstance(c_summary, dict):
            deployable = c_summary.get("estimated_deployable_cash") or c_summary.get("deployable_cash", 0)
            readiness = c_summary.get("deployment_readiness", "")
            if deployable and float(deployable) > 0:
                bullets.append(f"可部署资金：约 {deployable}。当前部署准备状态：{readiness}。建议先确认流动性储备需求后再部署。")

    bullets.extend(_build_intent_summary_bullets(intent_set, fa_artifacts))

    # Next steps
    if decision_status in ("BLOCKED", "DOWNGRADED"):
        bullets.append("建议补充缺失数据后重新评估正式决策。在阻断项清除之前，不建议执行主动操作。")

    if ds_has_decision and decision_status == "NO_FORMAL_DECISION":
        pass
    elif not ds_has_decision:
        bullets.append("本输出仅为分析报告，不包含正式交易决策。如需正式操作，请提供完整数据后调用 decision-support。")

    # Safety footer
    bullets.append("声明：fund-agent 不执行券商下单，所有输出为分析产物和审计痕迹。正式决策需经 decision_support 生成，并由用户审批。")

    return {
        "language": "zh-CN",
        "bullets": _dedupe_preserve_order(bullets),
    }


def _build_intent_summary_bullets(
    intent_set: set[str],
    fa_artifacts: dict[str, Any],
) -> list[str]:
    bullets: list[str] = []
    theme_text = _theme_text(fa_artifacts)

    if "PROFIT_PROTECTION" in intent_set:
        bullets.append("盈利保护：优先考虑部分减仓、回收本金或保护剩余利润，不建议把分析建议直接当成下单。")
    if "DRAWDOWN_RESPONSE" in intent_set or "RIGHT_SIDE_CONFIRMATION" in intent_set:
        bullets.append("回撤应对：不宜急着补仓，等待右侧确认；利好不涨反跌说明短期情绪偏弱。")
    if "SHORT_HOLDING_FEE_CHECK" in intent_set:
        bullets.append("短持有期检查：未满7天时应先看赎回费，不建议今天直接卖出。")
    if "OVERLAP_CONCENTRATION_CHECK" in intent_set:
        bullets.append("重合度检查：新增标普500的边际分散可能有限，与已有AI/QDII持仓存在重合。")
    if "CASH_DEPLOYMENT" in intent_set:
        bullets.append("资金部署：先保留安全垫，再区分可动用资金、短线战术预算和长期配置预算，不要把现金全部打满。")
    if "PORTFOLIO_REBALANCE" in intent_set:
        bullets.append("预算纪律：短线资金不超过10%，单一主题/消费电子不超过5%，现金和债券安全垫优先。")
    if "RISK_REDUCTION" in intent_set and any(term in theme_text for term in ("oil", "gas", "energy", "油气")):
        bullets.append("油气亏损仓位：不建议只因亏损直接清仓，可考虑降低风险暴露并确认主题趋势。")
    if any(term in theme_text for term in ("battery", "新能源", "电池")):
        bullets.append("电池/新能源仓位：收益回吐时先保护剩余利润，不一定一次性清仓。")
    if any(term in theme_text for term in ("short_bond", "money_market", "短债", "货币")):
        bullets.append("短债/现金替代：不要只看一天收益，应比较7日/30日表现并先看赎回成本。")
    if any(term in theme_text for term in ("dividend", "low_vol", "红利", "低波")):
        bullets.append("红利低波：不要因为低波就忽视短期追高，分批比一次性更稳。")

    return bullets


def localize_section_titles(sections: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    """Replace section titles with zh-CN equivalents when language is zh-CN."""
    if language != "zh-CN":
        return sections

    localized: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            localized.append(section)
            continue
        copied = dict(section)
        section_id = str(copied.get("id", ""))
        if section_id in ZH_CN_SECTION_TITLES:
            copied["title"] = ZH_CN_SECTION_TITLES[section_id]
        localized.append(copied)
    return localized


def _get_fund_names(fund_codes: list[str], fa_artifacts: dict[str, Any]) -> list[str]:
    names: list[str] = []
    fund_profiles = fa_artifacts.get("fund_profiles", {})
    if isinstance(fund_profiles, dict):
        for code in fund_codes:
            profile = fund_profiles.get(str(code), {})
            name = profile.get("name") or profile.get("fund_name", str(code))
            names.append(str(name))
    return names or [str(c) for c in fund_codes]


def _theme_text(fa_artifacts: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("fund_profiles", "portfolio_summary", "position_summary", "exposure_summary", "fund_analysis_report"):
        value = fa_artifacts.get(key)
        if isinstance(value, dict):
            parts.append(str(value))
    return " ".join(parts).lower()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
