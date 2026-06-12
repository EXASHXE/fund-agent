"""Workflow-level final report / explanation composer — v1.5.1 advisory quality.

Given fund_analysis output, optional decision_support output, and
EvidenceGraph diagnostics, produce a host-facing structured final
explanation. This layer does not use LLM, does not create decisions,
and only composes existing artifacts.

v1.5.1 adds:
  - Modularized into report_status, report_safety, report_zh sub-modules
  - SOFT_ACTION_ADVICE intent support
  - zh-CN section title localization and Chinese bullets for key sections
  - Enhanced action_boundary and recommended_next_steps Chinese text
"""

from __future__ import annotations

from typing import Any

from .report_status import (
    compute_decision_status,
    compute_report_status,
    data_completeness_grade,
    normalize_language,
)
from .report_safety import (
    FORBIDDEN_EXECUTION_FIELDS,
    build_safety_boundary,
    find_forbidden_execution_fields,
)
from .report_zh import (
    ZH_CN_SECTION_TITLES,
    build_chinese_summary,
    build_zh_blocked_reason,
    build_zh_downgraded_reason,
    localize_section_titles,
)


def compose_advisory_workflow_report(
    *,
    scenario_id: str = "",
    fund_analysis_output: dict[str, Any] | None = None,
    decision_support_output: dict[str, Any] | None = None,
    evidence_graph_diagnostics: dict[str, Any] | None = None,
    missing_data_diagnostics: dict[str, Any] | None = None,
    language: str = "en",
    advisory_intents: list[str] | None = None,
) -> dict[str, Any]:
    """Compose a host-facing structured final explanation from all workflow artifacts."""
    fa = fund_analysis_output or {}
    fa_artifacts = fa.get("artifacts", {}) if isinstance(fa, dict) else {}
    ds = decision_support_output or {}
    ds_artifacts = ds.get("artifacts", {}) if isinstance(ds, dict) else {}
    eg = evidence_graph_diagnostics or {}
    md = missing_data_diagnostics or {}
    intents = advisory_intents or []

    fa_status = str(fa.get("status", "PARTIAL"))
    ds_has_decision = bool(ds_artifacts.get("decision") or ds_artifacts.get("execution_ledger"))
    analysis_plan = fa_artifacts.get("analysis_plan", {}) if isinstance(fa_artifacts, dict) else {}
    decision_ready = bool(analysis_plan.get("decision_support_ready", False))

    report_status = compute_report_status(fa_status, fa_artifacts, md)
    decision_status = compute_decision_status(ds_has_decision, ds_artifacts)
    normalized_lang = normalize_language(language)

    user_facing_sections = _build_user_facing_sections(
        scenario_id=scenario_id,
        fa_artifacts=fa_artifacts,
        ds_artifacts=ds_artifacts,
        ds_has_decision=ds_has_decision,
        eg=eg,
        md=md,
        fa_status=fa_status,
        decision_status=decision_status,
        decision_ready=decision_ready,
        intents=intents,
        language=normalized_lang,
    )

    safety_boundary = build_safety_boundary(
        ds_has_decision=ds_has_decision,
        fa_artifacts=fa_artifacts,
        full_report_data={
            "fund_analysis_output": fa,
            "decision_support_output": ds,
        },
    )

    workflow_summary = {
        "scenario_id": scenario_id,
        "report_status": report_status,
        "decision_status": decision_status,
        "data_completeness_grade": data_completeness_grade(fa_artifacts, md),
        "decision_support_ready": decision_ready,
        "advisory_intents": intents,
    }

    result: dict[str, Any] = {
        "workflow_summary": workflow_summary,
        "user_facing_sections": user_facing_sections,
        "safety_boundary": safety_boundary,
    }

    # Chinese summary when language is zh-CN
    if normalized_lang == "zh-CN":
        chinese = build_chinese_summary(
            fa_artifacts=fa_artifacts,
            ds_artifacts=ds_artifacts,
            ds_has_decision=ds_has_decision,
            decision_status=decision_status,
            eg=eg,
            md=md,
            intents=intents,
        )
        result["chinese_summary"] = chinese

    return result


# ── User-facing sections builder ────────────────────────────────────────────


def _build_user_facing_sections(
    *,
    scenario_id: str,
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    ds_has_decision: bool,
    eg: dict[str, Any],
    md: dict[str, Any],
    fa_status: str,
    decision_status: str,
    decision_ready: bool,
    intents: list[str],
    language: str = "en",
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    is_zh = language == "zh-CN"

    # 1. Direct Answer — always first
    sections.append(_build_direct_answer_section(
        fa_artifacts=fa_artifacts,
        ds_artifacts=ds_artifacts,
        ds_has_decision=ds_has_decision,
        decision_status=decision_status,
        fa_status=fa_status,
        decision_ready=decision_ready,
        intents=intents,
        md=md,
        language=language,
    ))

    # 2. Evidence status
    sections.append(_build_evidence_status_section(
        eg=eg,
        fa_artifacts=fa_artifacts,
        ds_artifacts=ds_artifacts,
        ds_has_decision=ds_has_decision,
        decision_status=decision_status,
        decision_ready=decision_ready,
        language=language,
    ))

    # 3. Portfolio diagnosis
    sections.append(_build_portfolio_diagnosis_section(
        fa_artifacts=fa_artifacts,
        language=language,
    ))

    # 4. Summary
    sections.append(_build_summary_section(
        scenario_id=scenario_id,
        fa_status=fa_status,
        decision_status=decision_status,
        decision_ready=decision_ready,
        fa_artifacts=fa_artifacts,
        language=language,
    ))

    # 5. Decision explanation
    if ds_has_decision:
        sections.append(_build_decision_section(ds_artifacts, decision_status, language=language))
    elif decision_status == "NO_FORMAL_DECISION":
        sections.append(_build_analysis_only_section(fa_artifacts, language=language))

    # 6. Action boundary
    sections.append(_build_action_boundary_section(
        ds_has_decision=ds_has_decision,
        decision_status=decision_status,
        fa_artifacts=fa_artifacts,
        language=language,
    ))

    # 7. Recommended next steps
    sections.append(_build_recommended_next_steps_section(
        fa_artifacts=fa_artifacts,
        ds_artifacts=ds_artifacts,
        ds_has_decision=ds_has_decision,
        decision_status=decision_status,
        md=md,
        language=language,
    ))

    # 8. Limitations
    sections.append(_build_limitations_section(
        md=md,
        fa_artifacts=fa_artifacts,
        decision_status=decision_status,
        language=language,
    ))

    # Localize section titles for zh-CN
    return localize_section_titles(sections, language)


# ── Section: direct_answer ──────────────────────────────────────────────────


def _build_direct_answer_section(
    *,
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    ds_has_decision: bool,
    decision_status: str,
    fa_status: str,
    decision_ready: bool,
    intents: list[str],
    md: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    bullets: list[str] = []
    is_zh = language == "zh-CN"

    has_fee_blocker = _has_fee_blocker(fa_artifacts)
    has_right_side_unconfirmed = _has_right_side_unconfirmed(fa_artifacts)
    has_missing_data = bool(md.get("critical_missing") or md.get("blockers"))
    has_profit_concern = _has_profit_concern(fa_artifacts)
    is_report_only = "FORMAL_TRADE_DECISION" not in intents and not ds_has_decision
    is_soft_advice = "SOFT_ACTION_ADVICE" in intents and not ds_has_decision

    if decision_status == "BLOCKED":
        reasons = _collect_blocked_reasons(ds_artifacts, fa_artifacts)
        if is_zh:
            if reasons:
                bullets.append(f"正式决策已评估但被阻断：{', '.join(reasons[:3])}。当前不应执行操作。")
            else:
                bullets.append("正式决策已评估但被阻断，因证据或约束条件不足。当前不应执行操作。")
        else:
            if reasons:
                bullets.append(f"Formal decision was evaluated and blocked: {', '.join(reasons[:3])}.")
            else:
                bullets.append("Formal decision was evaluated and blocked due to evidence or constraint issues.")

    elif decision_status == "DOWNGRADED":
        reasons = _collect_blocked_reasons(ds_artifacts, fa_artifacts)
        if is_zh:
            if reasons:
                bullets.append(f"主动操作请求已被降级为被动等待建议：{', '.join(reasons[:3])}。")
            else:
                bullets.append("主动操作请求已被降级为被动等待建议，证据或约束条件不足。")
        else:
            if reasons:
                bullets.append(f"Requested active action was downgraded to a passive posture: {', '.join(reasons[:3])}.")
            else:
                bullets.append("Requested active action was downgraded — evidence or constraints insufficient.")

    elif decision_status == "FORMAL_DECISION":
        if is_zh:
            bullets.append("已生成正式决策，包含证据锚点。请查看决策说明了解详情。")
        else:
            bullets.append("Formal decision has been generated with evidence anchors. Review detail in decision explanation.")

    elif is_report_only:
        if is_zh:
            bullets.append("此为分析/报告场景，未评估正式交易决策。")
        else:
            bullets.append("This is an analysis / report-only scenario. No formal trade decision was evaluated.")

    if is_soft_advice:
        if is_zh:
            bullets.append("您请求了操作建议但未明确要求正式决策。以下输出为分析建议，不构成正式操作指令。")
        else:
            bullets.append("You requested action guidance without a formal decision. Output is advisory only, not execution instructions.")

    if has_fee_blocker:
        if is_zh:
            bullets.append("短期赎回费风险显著 — 主动卖出/减仓将产生额外费用。")
        else:
            bullets.append("Short-holding redemption fee risk is prominent — active sell/reduce would trigger additional cost.")

    if has_right_side_unconfirmed:
        if is_zh:
            bullets.append("右侧确认信号缺失 — 当前不建议主动加仓/买入，建议继续观察。")
        else:
            bullets.append("Right-side confirmation is missing — active add/buy is not yet advised; observe before acting.")

    if has_missing_data:
        if is_zh:
            bullets.append("存在显著数据缺失，建议在补充数据后再做决策，当前分析结果不应被视为可执行建议。")
        else:
            bullets.append("Significant data is missing; recommendations are limited and should not be treated as actionable without data completion.")

    if has_profit_concern:
        if is_zh:
            bullets.append("盈利保护诊断已激活 — 在考虑加仓前，建议先评估部分减仓控制风险。")
        else:
            bullets.append("Profit protection diagnostics are active — review partial trim options before adding to positions.")

    if is_zh:
        bullets.extend(_build_zh_direct_answer_intent_bullets(intents, fa_artifacts))

    if not bullets:
        if is_zh:
            bullets.append("分析已生成。请查看报告各节获取详细结果。")
            if not ds_has_decision:
                bullets.append("未请求或未评估正式决策。")
        else:
            bullets.append("Analysis generated. Review report sections for detailed findings.")
            if not ds_has_decision:
                bullets.append("No formal decision was requested or evaluated.")

    return {
        "id": "direct_answer",
        "title": "Direct Answer",
        "bullets": bullets,
    }


def _build_zh_direct_answer_intent_bullets(
    intents: list[str],
    fa_artifacts: dict[str, Any],
) -> list[str]:
    bullets: list[str] = []
    intent_set = set(intents)
    themes = _theme_text(fa_artifacts)
    has_fee_blocker = _has_fee_blocker(fa_artifacts)
    has_right_side_unconfirmed = _has_right_side_unconfirmed(fa_artifacts)
    has_profit_concern = _has_profit_concern(fa_artifacts)

    if "PROFIT_PROTECTION" in intent_set and has_profit_concern:
        bullets.append(
            "优先考虑部分减仓来回收本金，利润是真实的，但不等于必须一次性清仓；不要把分析建议直接当成下单。"
        )

    if "SHORT_HOLDING_FEE_CHECK" in intent_set or has_fee_blocker:
        bullets.append("未满7天等短持有期会触发赎回费，不建议今天直接卖出。")

    if "DRAWDOWN_RESPONSE" in intent_set or "RIGHT_SIDE_CONFIRMATION" in intent_set:
        bullets.append("不宜急着补仓，也不建议因为两天反弹直接追回；先等待右侧确认和风险预算匹配。")
        bullets.append("利好不涨反跌说明短期情绪偏弱，剩余仓位可继续观察。")

    if "OVERLAP_CONCENTRATION_CHECK" in intent_set:
        bullets.append("新增标普500的边际分散可能有限，与已有AI/QDII持仓存在重合；不等于不能买，但收益弹性可能被已有持仓覆盖。")

    if "CASH_DEPLOYMENT" in intent_set:
        bullets.append("先区分安全垫和可动用资金，不要把现金全部打满；避免追高涨幅过大的AI方向。")

    if "RISK_REDUCTION" in intent_set and any(term in themes for term in ("oil", "gas", "energy", "油气")):
        bullets.append("不建议只因亏损直接清仓，可以考虑降低风险暴露；需要确认油气主题基本面/趋势。")

    if "PROFIT_PROTECTION" in intent_set and any(term in themes for term in ("battery", "新能源", "电池")):
        bullets.append("这是收益回吐问题，重点是保护剩余利润，不一定一次性清仓。")

    if "PORTFOLIO_REBALANCE" in intent_set:
        bullets.append("短线资金不超过10%，单一主题/消费电子不超过5%，先保留现金和债券安全垫。")

    if any(term in themes for term in ("short_bond", "money_market", "cash", "短债", "货币")):
        bullets.append("不要只看一天收益，先比较7日/30日表现，并检查赎回成本。")

    if any(term in themes for term in ("dividend", "low_vol", "红利", "低波")):
        bullets.append("不要因为低波就忽视短期追高，分批比一次性更稳。")

    return _dedupe_preserve_order(bullets)


# ── Section: evidence_status ─────────────────────────────────────────────────


def _build_evidence_status_section(
    *,
    eg: dict[str, Any],
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    ds_has_decision: bool,
    decision_status: str,
    decision_ready: bool,
    language: str = "en",
) -> dict[str, Any]:
    bullets: list[str] = []
    sufficient: list[str] = []
    missing: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    graph_stats = eg.get("graph", {}).get("stats", {})
    if isinstance(graph_stats, dict):
        total = graph_stats.get("total", 0)
        hard = graph_stats.get("hard", 0)
        soft = graph_stats.get("soft", 0)
        hybrid = graph_stats.get("hybrid", 0)
        if total > 0:
            sufficient.append(f"Total evidence items: {total}")
            if hard:
                sufficient.append(f"Hard evidence (confidence=1.0): {hard}")
            if soft:
                sufficient.append(f"Soft evidence (news/sentiment): {soft}")
            if hybrid:
                sufficient.append(f"Hybrid evidence (corroborated): {hybrid}")
        else:
            missing.append("No evidence items available in the evidence graph.")

    included = eg.get("included_evidence_count", 0)
    host_soft = eg.get("host_soft_evidence_count", 0)

    eg_warnings = eg.get("warnings", [])
    eg_missing = eg.get("missing_or_invalid_evidence", [])
    if eg_missing:
        missing.append(f"Missing or invalid evidence items: {len(eg_missing)}")
    if eg_warnings:
        warnings.append(f"Evidence warnings: {len(eg_warnings)}")

    evidence_gap = fa_artifacts.get("evidence_gap_diagnostics", {})
    if isinstance(evidence_gap, dict):
        gap_items = evidence_gap.get("items") or evidence_gap.get("details", [])
        if isinstance(gap_items, list):
            for gap in gap_items:
                if isinstance(gap, dict):
                    desc = gap.get("description") or gap.get("gap", "")
                    if desc:
                        missing.append(f"Evidence gap: {desc}")

        if evidence_gap.get("missing_recent_news"):
            missing.append("Missing: recent fund or theme news")
        if evidence_gap.get("missing_user_constraints"):
            missing.append("Missing: user trading constraints")
        if evidence_gap.get("missing_risk_preference"):
            missing.append("Missing: risk preference / tolerance")
        if evidence_gap.get("missing_transaction_history"):
            missing.append("Missing: transaction history")
        if evidence_gap.get("missing_benchmark"):
            missing.append("Missing: benchmark data")

    if decision_status == "BLOCKED":
        blocker_reasons = _collect_blocked_reasons(ds_artifacts, fa_artifacts)
        blockers.extend(blocker_reasons[:5])

    groups: list[dict[str, Any]] = []
    if sufficient:
        groups.append({"level": "sufficient", "items": sufficient})
    if missing:
        groups.append({"level": "missing", "items": missing})
    if blockers:
        groups.append({"level": "blocker", "items": blockers})
    if warnings:
        groups.append({"level": "warning", "items": warnings})

    for group in groups:
        label = group["level"]
        for item in group["items"]:
            bullets.append(f"[{label}] {item}")

    bullets.append(f"Evidence from fund_analysis + host: {included} items")
    bullets.append(f"Host soft evidence (news/sentiment): {host_soft}")
    bullets.append(f"Decision support ready: {decision_ready}")

    return {
        "id": "evidence_status",
        "title": "Evidence Status",
        "bullets": bullets,
    }


# ── Section: portfolio_diagnosis ────────────────────────────────────────────


def _build_portfolio_diagnosis_section(
    *,
    fa_artifacts: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    bullets: list[str] = []

    portfolio_summary = fa_artifacts.get("portfolio_summary", {})
    if isinstance(portfolio_summary, dict):
        total_value = portfolio_summary.get("total_value", "")
        if total_value:
            bullets.append(f"Total portfolio value: {total_value}")
        position_count = portfolio_summary.get("position_count", 0)
        if position_count:
            bullets.append(f"Number of positions: {position_count}")

    exposure = fa_artifacts.get("exposure_summary", {})
    if isinstance(exposure, dict):
        for key, val in exposure.items():
            if key in ("overlap_warning", "concentration_warning") and val:
                bullets.append(f"Exposure concern: {val}")
        if exposure.get("top_sector"):
            bullets.append(f"Top sector exposure: {exposure['top_sector']}")
        if exposure.get("top_industry"):
            bullets.append(f"Top industry exposure: {exposure['top_industry']}")

    cash_diag = fa_artifacts.get("cash_deployment_diagnostics", {})
    if isinstance(cash_diag, dict):
        summary = cash_diag.get("summary", {})
        if isinstance(summary, dict):
            cash_ratio = summary.get("cash_ratio")
            if cash_ratio is not None:
                bullets.append(f"Cash / cash-like ratio: {cash_ratio}")
            deployable = summary.get("estimated_deployable_cash") or summary.get("deployable_cash", 0)
            if deployable is not None:
                bullets.append(f"Deployable cash: {deployable}")
            readiness = summary.get("deployment_readiness")
            if readiness:
                bullets.append(f"Cash deployment readiness: {readiness}")
            buffer_status = summary.get("cash_buffer_status")
            if buffer_status:
                bullets.append(f"Cash buffer status: {buffer_status}")

    profit_diag = fa_artifacts.get("profit_protection_diagnostics", {})
    if isinstance(profit_diag, dict):
        items = profit_diag.get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    fund = item.get("fund_code") or item.get("fund_name", "")
                    level = item.get("profit_level", "")
                    action = item.get("suggested_analysis_action", "")
                    if level in ("high", "very_high"):
                        bullets.append(f"Profit protection: {fund} ({level}, suggested: {action})")

    right_side = fa_artifacts.get("right_side_confirmation_diagnostics", {})
    if isinstance(right_side, dict):
        rs_items = right_side.get("items", [])
        if isinstance(rs_items, list):
            for item in rs_items:
                if isinstance(item, dict):
                    fund = item.get("fund_code") or item.get("fund_name", "")
                    drawdown = item.get("drawdown_level", "")
                    confirmed = item.get("right_side_confirmed")
                    if drawdown:
                        status = "unconfirmed" if confirmed is False else "confirmed" if confirmed else "unknown"
                        bullets.append(f"Right-side confirmation: {fund} (drawdown: {drawdown}, {status})")

    redemption = fa_artifacts.get("redemption_fee_risk", {})
    if isinstance(redemption, dict):
        if redemption.get("has_blocker"):
            affected = redemption.get("affected_funds", [])
            if affected:
                bullets.append(f"Redemption fee blocker for: {', '.join(str(f) for f in affected)}")
        elif redemption.get("has_warning"):
            affected = redemption.get("affected_funds", [])
            if affected:
                bullets.append(f"Redemption fee warning for: {', '.join(str(f) for f in affected)}")

    pnl = fa_artifacts.get("pnl_summary", {})
    if isinstance(pnl, dict):
        unrealized = pnl.get("total_unrealized_pnl")
        if unrealized is not None:
            bullets.append(f"Total unrealized PnL: {unrealized}")
        realized = pnl.get("total_realized_pnl")
        if realized is not None:
            bullets.append(f"Total realized PnL: {realized}")

    if not bullets:
        bullets.append("Portfolio diagnosis: insufficient data to assess portfolio-level issues.")

    return {
        "id": "portfolio_diagnosis",
        "title": "Portfolio Diagnosis",
        "bullets": bullets,
    }


# ── Section: summary ────────────────────────────────────────────────────────


def _build_summary_section(
    *,
    scenario_id: str,
    fa_status: str,
    decision_status: str,
    decision_ready: bool,
    fa_artifacts: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    bullets: list[str] = []

    portfolio_summary = fa_artifacts.get("portfolio_summary", {})
    if isinstance(portfolio_summary, dict):
        total_value = portfolio_summary.get("total_value", "")
        if total_value:
            bullets.append(f"Total portfolio value: {total_value}")
        position_count = portfolio_summary.get("position_count", 0)
        if position_count:
            bullets.append(f"Number of positions: {position_count}")

    analysis_plan = fa_artifacts.get("analysis_plan", {})
    if isinstance(analysis_plan, dict):
        blockers = analysis_plan.get("blockers", [])
        if blockers:
            bullets.append(f"Blockers detected: {', '.join(str(b) for b in blockers)}")

    bullets.append(f"Fund analysis status: {fa_status}")
    bullets.append(f"Decision support ready: {decision_ready}")
    bullets.append(f"Formal decision status: {decision_status}")

    if decision_status == "NO_FORMAL_DECISION":
        bullets.append("No formal decision was evaluated.")
    elif decision_status == "FORMAL_DECISION":
        bullets.append("Formal investment decisions have been generated.")
    elif decision_status == "BLOCKED":
        bullets.append("A formal decision was evaluated and blocked.")
    elif decision_status == "DOWNGRADED":
        bullets.append("A requested active action was downgraded.")

    return {
        "id": "summary",
        "title": f"Advisory Workflow Summary — {scenario_id}",
        "bullets": bullets,
    }


# ── Section: decision explanation ───────────────────────────────────────────


def _build_decision_section(ds_artifacts: dict[str, Any], decision_status: str, language: str = "en") -> dict[str, Any]:
    bullets: list[str] = []

    if decision_status == "BLOCKED":
        bullets.append("A formal decision was evaluated and blocked.")

    decision = ds_artifacts.get("decision", {})
    if isinstance(decision, dict):
        action = decision.get("action", "N/A")
        amount = decision.get("execution_amount", 0)
        state = decision.get("evidence_state", "N/A")
        blocked = decision.get("blocked_by", [])
        reason_codes = decision.get("decision_reason_codes", [])
        requested = decision.get("requested_action")
        bullets.append(f"Decision action: {action}")
        if requested and str(requested).upper() != str(action).upper():
            bullets.append(f"Requested action: {requested} (final: {action})")
        bullets.append(f"Execution amount: {amount}")
        bullets.append(f"Evidence state: {state}")
        if blocked:
            bullets.append(f"Blocked by: {', '.join(str(b) for b in blocked)}")
        if reason_codes:
            bullets.append(f"Reason codes: {', '.join(str(r) for r in reason_codes[:8])}")

    ledger = ds_artifacts.get("execution_ledger", {})
    if isinstance(ledger, dict):
        summary = ledger.get("ledger_summary", {})
        if isinstance(summary, dict):
            bullets.append(f"Total decisions: {summary.get('decision_count', 0)}")
            bullets.append(f"Active decisions: {summary.get('active_decision_count', 0)}")
            bullets.append(f"Passive decisions: {summary.get('passive_decision_count', 0)}")
            downgraded = summary.get("downgraded_decision_count", 0)
            blocked_count = summary.get("blocked_decision_count", 0)
            if downgraded:
                bullets.append(f"Downgraded decisions: {downgraded}")
            if blocked_count:
                bullets.append(f"Blocked decisions: {blocked_count}")

    anchor_diag = ds_artifacts.get("evidence_anchor_diagnostics", {})
    if isinstance(anchor_diag, dict):
        valid = anchor_diag.get("valid_anchor_refs", [])
        invalid = anchor_diag.get("invalid_anchor_refs", [])
        missing = anchor_diag.get("missing_anchor_refs", [])
        coverage = anchor_diag.get("trade_anchor_coverage", [])
        if valid:
            bullets.append(f"Valid evidence anchors: {len(valid)}")
        if invalid:
            bullets.append(f"Invalid evidence anchors: {len(invalid)}")
        if missing:
            bullets.append(f"Missing evidence anchors: {len(missing)}")
        if coverage:
            for tc in coverage:
                if isinstance(tc, dict):
                    bullets.append(f"Trade {tc.get('trade_id', '?')}: coverage={tc.get('coverage', '?')}")

    risk_conflicts = ds_artifacts.get("risk_constraint_conflicts", {})
    if isinstance(risk_conflicts, dict):
        rsummary = risk_conflicts.get("summary", {})
        if isinstance(rsummary, dict):
            if rsummary.get("has_blocking_conflict"):
                bullets.append("Risk/constraint conflicts: blocking conflicts present")
            if rsummary.get("has_capping_conflict"):
                bullets.append("Risk/constraint conflicts: amount capped by constraints")

    return {
        "id": "decision_explanation",
        "title": "Decision Explanation",
        "bullets": bullets,
    }


# ── Section: analysis-only ──────────────────────────────────────────────────


def _build_analysis_only_section(fa_artifacts: dict[str, Any], language: str = "en") -> dict[str, Any]:
    bullets: list[str] = []

    bullets.append("No formal decision was evaluated.")
    bullets.append("This output contains analysis-only recommendations and observations.")
    bullets.append("Any suggested trades in the analysis are advisory only and do not constitute execution instructions.")

    analysis_plan = fa_artifacts.get("analysis_plan", {})
    if isinstance(analysis_plan, dict):
        plan_blockers = analysis_plan.get("blockers", [])
        if plan_blockers:
            bullets.append(f"Analysis blockers present: {', '.join(str(b) for b in plan_blockers)}")

    suggested_rebalance = fa_artifacts.get("suggested_rebalance_plan", {})
    if isinstance(suggested_rebalance, dict):
        suggested_trades = suggested_rebalance.get("suggested_trades") or suggested_rebalance.get("trades", [])
        if isinstance(suggested_trades, list) and suggested_trades:
            bullets.append(f"Analysis-only suggested trades present ({len(suggested_trades)} suggestions — not formal decisions)")

    return {
        "id": "decision_explanation",
        "title": "Decision Explanation",
        "bullets": bullets,
    }


# ── Section: action_boundary ────────────────────────────────────────────────


def _build_action_boundary_section(
    *,
    ds_has_decision: bool,
    decision_status: str,
    fa_artifacts: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    bullets: list[str] = []
    is_zh = language == "zh-CN"

    if is_zh:
        bullets.append("fund-agent 不执行券商下单。所有输出均为分析产物和审计痕迹。")
    else:
        bullets.append("fund-agent does not execute broker orders. All output is analysis and audit artifacts only.")

    if ds_has_decision:
        if is_zh:
            bullets.append("正式决策由 decision_support（唯一授权的正式决策产生者）生成。")
            if decision_status == "BLOCKED":
                bullets.append("正式决策已被阻断 — 请勿将其视为执行信号。")
            elif decision_status == "DOWNGRADED":
                bullets.append("正式决策已被降级 — 主动操作已降为被动等待姿势。")
            elif decision_status == "FORMAL_DECISION":
                bullets.append("已生成含有证据锚点的正式决策。请展示给用户审核。")
        else:
            bullets.append("Formal decision was produced by decision_support (the only authorized formal decision producer).")
            if decision_status == "BLOCKED":
                bullets.append("The formal decision was BLOCKED — do not treat as an execution signal.")
            elif decision_status == "DOWNGRADED":
                bullets.append("The formal decision was DOWNGRADED — active action was reduced to passive posture.")
            elif decision_status == "FORMAL_DECISION":
                bullets.append("A formal decision was generated with evidence anchors. Host should present to user for review.")
    else:
        if is_zh:
            bullets.append("未产生正式决策，此为纯分析输出。")
            bullets.append("fund_analysis 中的 suggested_rebalance_plan 仅为分析建议 — 不构成正式决策。")
            bullets.append("调用方不得将分析建议转化为券商下单，除非经 decision_support 审批。")
        else:
            bullets.append("No formal decision was produced. This is analysis-only output.")
            bullets.append("suggested_rebalance_plan from fund_analysis is analysis-only — not formal decisions.")
            bullets.append("Host must not convert analysis-only suggestions into broker orders without decision_support approval.")

    if ds_has_decision and not is_zh:
        bullets.append("Host must not convert analysis-only suggestions into broker orders without decision_support approval.")

    return {
        "id": "action_boundary",
        "title": "Action Boundary",
        "bullets": bullets,
    }


# ── Section: recommended_next_steps ─────────────────────────────────────────


def _build_recommended_next_steps_section(
    *,
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    ds_has_decision: bool,
    decision_status: str,
    md: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    bullets: list[str] = []
    is_zh = language == "zh-CN"

    evidence_gap = fa_artifacts.get("evidence_gap_diagnostics", {})
    if isinstance(evidence_gap, dict):
        if evidence_gap.get("missing_recent_news"):
            if is_zh:
                bullets.append("获取近期基金/主题新闻和情绪数据，以改善证据质量。")
            else:
                bullets.append("Fetch recent fund/theme news and sentiment data to improve evidence quality.")
        if evidence_gap.get("missing_user_constraints"):
            if is_zh:
                bullets.append("提供交易约束参数（max_trade_pct, forbidden_actions, liquidity_reserve_pct）。")
            else:
                bullets.append("Provide trading constraints (max_trade_pct, forbidden_actions, liquidity_reserve_pct).")
        if evidence_gap.get("missing_risk_preference"):
            if is_zh:
                bullets.append("提供风险偏好（conservative/balanced/aggressive）以获得校准建议。")
            else:
                bullets.append("Provide risk profile (conservative/balanced/aggressive) for calibrated advice.")
        if evidence_gap.get("missing_transaction_history"):
            if is_zh:
                bullets.append("提供交易历史记录以支持成本基础与持有期分析。")
            else:
                bullets.append("Provide transaction history to enable cost basis and holding period analysis.")
        if evidence_gap.get("missing_benchmark"):
            if is_zh:
                bullets.append("获取基准指数历史数据以进行相对表现评估。")
            else:
                bullets.append("Fetch benchmark history for relative performance assessment.")

        next_data = evidence_gap.get("next_data_to_fetch") or evidence_gap.get("recommended_next_data", [])
        if isinstance(next_data, list):
            for item in next_data:
                bullets.append(f"Recommended: {item}")

    if decision_status == "BLOCKED":
        if is_zh:
            bullets.append("请解决阻断项后再重新评估正式决策。")
        else:
            bullets.append("Resolve blockers before re-evaluating formal decision.")
    elif decision_status == "DOWNGRADED":
        if is_zh:
            bullets.append("请补充缺失证据和约束条件，以便重新评估主动操作。")
        else:
            bullets.append("Address missing evidence and constraints to re-evaluate active action.")

    if _has_fee_blocker(fa_artifacts):
        if is_zh:
            bullets.append("等待短期持有期到期，或确认准确的赎回费率表。")
        else:
            bullets.append("Wait for short-holding period to expire or confirm exact redemption fee schedule.")

    if _has_right_side_unconfirmed(fa_artifacts):
        if is_zh:
            bullets.append("等待 NAV/新闻/基准确认信号后再考虑加仓或买入。")
            bullets.append("持续监控：净值持续反弹、正面新闻催化、情绪改善。")
        else:
            bullets.append("Wait for NAV/news/benchmark confirmation before considering add/buy.")
            bullets.append("Monitor: sustained NAV rebound, positive news catalyst, improving sentiment.")

    if not bullets:
        if ds_has_decision and decision_status == "FORMAL_DECISION":
            if is_zh:
                bullets.append("请查看正式决策详情并展示给用户审批。")
            else:
                bullets.append("Review formal decision detail and present to user for approval.")
        else:
            if is_zh:
                bullets.append("使用最新数据重新运行分析，以跟踪组合变化。")
            else:
                bullets.append("Re-run analysis with updated data to track portfolio changes over time.")

    if is_zh:
        bullets.append("如需正式交易决策请使用 decision_support — fund_analysis 输出仅为分析参考。")
    else:
        bullets.append("Use decision_support for any formal trade decisions — fund_analysis output is analysis-only.")

    return {
        "id": "recommended_next_steps",
        "title": "Recommended Next Steps",
        "bullets": bullets,
    }


# ── Section: limitations ───────────────────────────────────────────────────


def _build_limitations_section(
    *,
    md: dict[str, Any],
    fa_artifacts: dict[str, Any],
    decision_status: str,
    language: str = "en",
) -> dict[str, Any]:
    bullets: list[str] = []
    is_zh = language == "zh-CN"

    report_quality = fa_artifacts.get("report_quality_gate", {})
    if isinstance(report_quality, dict):
        grade = report_quality.get("grade", "")
        if grade:
            bullets.append(f"Report quality grade: {grade}")
        limitations = report_quality.get("limitations", [])
        if isinstance(limitations, list):
            for lim in limitations:
                bullets.append(str(lim))
        if report_quality.get("can_publish_professional_report") is False:
            bullets.append("Limited report: cannot publish as professional report due to data quality.")
        if report_quality.get("can_publish_limited_report") is True:
            bullets.append("A limited report can be published with explicit limitations.")

    if md.get("critical_missing"):
        bullets.append(f"Critical missing data: {md['critical_missing']}")
    missing_fields = md.get("missing_fields", [])
    if missing_fields:
        bullets.append(f"Missing data fields: {', '.join(str(f) for f in missing_fields)}")

    if decision_status == "BLOCKED":
        bullets.append("A formal decision was evaluated and blocked. See decision explanation for details.")
    elif decision_status == "DOWNGRADED":
        bullets.append("A requested active action was downgraded. See decision explanation for details.")
    elif decision_status == "NO_FORMAL_DECISION":
        bullets.append("Decision support was either not requested or no formal decision was evaluated.")

    fa_warnings = fa_artifacts.get("warnings", [])
    if isinstance(fa_warnings, list) and fa_warnings:
        for w in fa_warnings[:3]:
            bullets.append(f"Warning: {w}")

    if is_zh:
        bullets.append("安全声明：fund-agent 不执行券商下单。所有正式决策仅为审计痕迹。")
    else:
        bullets.append("Safety: fund-agent does not execute broker orders. All formal decisions are audit artifacts only.")

    return {
        "id": "limitations",
        "title": "Limitations and Warnings",
        "bullets": bullets,
    }


# ── Helper: conditional checks ──────────────────────────────────────────────


def _has_fee_blocker(fa_artifacts: dict[str, Any]) -> bool:
    redemption = fa_artifacts.get("redemption_fee_risk", {})
    if isinstance(redemption, dict) and redemption.get("has_blocker"):
        return True
    prof_diag = fa_artifacts.get("professional_diagnostics", {})
    if isinstance(prof_diag, dict):
        rf = prof_diag.get("redemption_fee_risk", {})
        if isinstance(rf, dict) and rf.get("has_blocker"):
            return True
    analysis_plan = fa_artifacts.get("analysis_plan", {})
    if isinstance(analysis_plan, dict):
        blockers = analysis_plan.get("blockers", [])
        if isinstance(blockers, list):
            return any("redemption_fee" in str(b).lower() for b in blockers)
    return False


def _has_right_side_unconfirmed(fa_artifacts: dict[str, Any]) -> bool:
    right_side = fa_artifacts.get("right_side_confirmation_diagnostics", {})
    if isinstance(right_side, dict):
        items = right_side.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("right_side_confirmed") is False:
                    if item.get("applicability") != "not_applicable":
                        return True
    analysis_plan = fa_artifacts.get("analysis_plan", {})
    if isinstance(analysis_plan, dict):
        blockers = analysis_plan.get("blockers", [])
        if isinstance(blockers, list):
            return any("right_side" in str(b).lower() for b in blockers)
    return False


def _has_profit_concern(fa_artifacts: dict[str, Any]) -> bool:
    profit = fa_artifacts.get("profit_protection_diagnostics", {})
    if isinstance(profit, dict):
        items = profit.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and str(item.get("profit_level", "")) in ("high", "very_high"):
                    return True
    return False


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


def _collect_blocked_reasons(
    ds_artifacts: dict[str, Any],
    fa_artifacts: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []

    decision = ds_artifacts.get("decision", {})
    if isinstance(decision, dict):
        blocked = decision.get("blocked_by", [])
        if isinstance(blocked, list):
            reasons.extend(str(b) for b in blocked if b)
        codes = decision.get("decision_reason_codes", [])
        if isinstance(codes, list):
            reasons.extend(str(c) for c in codes if c)

    decisions_list = ds_artifacts.get("decisions", [])
    if isinstance(decisions_list, list):
        for d in decisions_list:
            if isinstance(d, dict):
                blocked = d.get("blocked_by", [])
                if isinstance(blocked, list):
                    reasons.extend(str(b) for b in blocked if b)
                codes = d.get("decision_reason_codes", [])
                if isinstance(codes, list):
                    reasons.extend(str(c) for c in codes if c)

    seen: set[str] = set()
    unique: list[str] = []
    for r in reasons:
        if r not in seen:
            unique.append(r)
            seen.add(r)
    return unique
