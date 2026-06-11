"""Workflow-level final report / explanation composer — v1.5 advisory quality.

Given fund_analysis output, optional decision_support output, and
EvidenceGraph diagnostics, produce a host-facing structured final
explanation. This layer does not use LLM, does not create decisions,
and only composes existing artifacts.

v1.5 adds:
  - direct_answer — 2-5 bullet answer to user's actual question
  - evidence_status (enhanced) — data sufficiency with blocker/warning/missing
  - portfolio_diagnosis — portfolio-level issues
  - action_boundary — analysis vs formal decision boundary
  - recommended_next_steps — safe next steps
  - chinese_summary — zh-CN natural language bullets
  - advisory_intent support — integrate intent classification into metadata
"""

from __future__ import annotations

from typing import Any

FORBIDDEN_EXECUTION_FIELDS = frozenset({
    "broker_order_id",
    "order_id",
    "order_status",
    "filled_quantity",
    "fill_price",
    "execution_venue",
    "submitted_at",
    "broker",
    "exchange_order_id",
})

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
    """Compose a host-facing structured final explanation from all workflow artifacts.

    Args:
        scenario_id: Fixture or user scenario identifier.
        fund_analysis_output: FundAnalysisSkill output dict.
        decision_support_output: DecisionSupportSkill output dict (None if not called).
        evidence_graph_diagnostics: WorkflowEvidenceGraphResult.to_dict().
        missing_data_diagnostics: Missing data details from evidence_gap_diagnostics.
        language: "en" or "zh-CN" — controls Chinese sections.
        advisory_intents: Classified advisory intents from AdvisoryIntent taxonomy.
    """
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

    report_status = _compute_report_status(fa_status, fa_artifacts, md)
    decision_status = _compute_decision_status(ds_has_decision, ds_artifacts)
    normalized_lang = _normalize_language(language)

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
    )

    safety_boundary = _build_safety_boundary(
        ds_has_decision=ds_has_decision,
        fa_artifacts=fa_artifacts,
        ds_artifacts=ds_artifacts,
        full_report_data={
            "fund_analysis_output": fa,
            "decision_support_output": ds,
        },
    )

    workflow_summary = {
        "scenario_id": scenario_id,
        "report_status": report_status,
        "decision_status": decision_status,
        "data_completeness_grade": _data_completeness_grade(fa_artifacts, md),
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
        chinese = _build_chinese_summary(
            fa_artifacts=fa_artifacts,
            ds_artifacts=ds_artifacts,
            ds_has_decision=ds_has_decision,
            decision_status=decision_status,
            eg=eg,
            md=md,
        )
        result["chinese_summary"] = chinese

    return result


# ── Language ────────────────────────────────────────────────────────────────


def _normalize_language(language: str) -> str:
    normalized = str(language).replace("_", "-")
    if normalized.lower() in {"zh-cn", "zh-hans-cn", "zh"}:
        return "zh-CN"
    return "en"


# ── Report status ───────────────────────────────────────────────────────────


def _compute_report_status(
    fa_status: str,
    fa_artifacts: dict[str, Any],
    md: dict[str, Any],
) -> str:
    if fa_status == "FAILED":
        return "FAILED"
    quality_gate = fa_artifacts.get("report_quality_gate", {})
    if isinstance(quality_gate, dict):
        if quality_gate.get("can_publish_professional_report") is False:
            return "PARTIAL"
    if md.get("critical_missing") or md.get("blockers"):
        return "PARTIAL"
    if md.get("missing_user_constraints") or md.get("missing_risk_preference"):
        return "PARTIAL"
    return "OK" if fa_status == "OK" else "PARTIAL"


def _compute_decision_status(
    ds_has_decision: bool,
    ds_artifacts: dict[str, Any],
) -> str:
    """Compute decision_status from decision_support output.

    Priority:
    1. If no decision_support output exists -> NO_FORMAL_DECISION.
    2. Check single-decision path first (decision dict).
    3. Then check multi-decision path (ledger/decisions).
    """
    if not ds_has_decision:
        return "NO_FORMAL_DECISION"

    decision = ds_artifacts.get("decision", {})
    decisions_list = ds_artifacts.get("decisions", [])
    is_multi = isinstance(decisions_list, list) and len(decisions_list) > 1

    if isinstance(decision, dict) and not is_multi:
        action = str(decision.get("action", "")).upper()
        blocked_by = decision.get("blocked_by", [])
        evidence_state = str(decision.get("evidence_state", ""))
        reason_codes = decision.get("decision_reason_codes", [])
        if action in ("HOLD", "WAIT", "PAUSE_DCA"):
            if blocked_by:
                return "BLOCKED"
            if evidence_state in ("DOWNGRADED", "INSUFFICIENT_EVIDENCE", "CONSTRAINT_BLOCKED", "BUDGET_BLOCKED"):
                return "DOWNGRADED"
            if any(rc in ("DOWNGRADED_ACTIVE_TO_HOLD", "INSUFFICIENT_EVIDENCE", "CONSTRAINT_BLOCKED", "BUDGET_BLOCKED")
                   for rc in (reason_codes or [])):
                return "DOWNGRADED"
            return "DOWNGRADED"
        if action in ("BUY", "SELL", "INCREASE", "REDUCE"):
            return "FORMAL_DECISION"
        return "NO_FORMAL_DECISION"

    if isinstance(ledger_dict := ds_artifacts.get("execution_ledger", {}), dict):
        summary = ledger_dict.get("ledger_summary", {})
        if isinstance(summary, dict):
            active = summary.get("active_decision_count", 0)
            blocked = summary.get("blocked_decision_count", 0)
            downgraded = summary.get("downgraded_decision_count", 0)
            if blocked > 0 and active == 0:
                return "BLOCKED"
            if blocked > 0 and active > 0:
                return "DOWNGRADED"
            if downgraded > 0:
                return "DOWNGRADED"
            if active > 0:
                return "FORMAL_DECISION"

    if isinstance(decisions_list, list) and decisions_list:
        has_active = any(
            str(d.get("action", "")).upper() in ("BUY", "SELL", "INCREASE", "REDUCE")
            for d in decisions_list if isinstance(d, dict)
        )
        has_blocked = any(
            d.get("blocked_by") for d in decisions_list if isinstance(d, dict)
        )
        if has_active:
            return "FORMAL_DECISION" if not has_blocked else "DOWNGRADED"
        return "BLOCKED" if has_blocked else "DOWNGRADED"

    return "NO_FORMAL_DECISION"


def _data_completeness_grade(
    fa_artifacts: dict[str, Any],
    md: dict[str, Any],
) -> str:
    data_comp = fa_artifacts.get("data_completeness", {})
    if isinstance(data_comp, dict):
        grade = data_comp.get("grade", "")
        if grade:
            return str(grade)
    if md.get("critical_missing"):
        return "POOR"
    return "FAIR"


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
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []

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
    ))

    # 2. Evidence status — enhanced
    sections.append(_build_evidence_status_section(
        eg=eg,
        fa_artifacts=fa_artifacts,
        ds_artifacts=ds_artifacts,
        ds_has_decision=ds_has_decision,
        decision_status=decision_status,
        decision_ready=decision_ready,
    ))

    # 3. Portfolio diagnosis
    sections.append(_build_portfolio_diagnosis_section(fa_artifacts=fa_artifacts))

    # 4. Workflow summary
    sections.append(_build_summary_section(
        scenario_id=scenario_id,
        fa_status=fa_status,
        decision_status=decision_status,
        decision_ready=decision_ready,
        fa_artifacts=fa_artifacts,
    ))

    # 5. Decision explanation (if applicable)
    if ds_has_decision:
        sections.append(_build_decision_section(ds_artifacts, decision_status))
    elif decision_status == "NO_FORMAL_DECISION":
        sections.append(_build_analysis_only_section(fa_artifacts))

    # 6. Action boundary
    sections.append(_build_action_boundary_section(
        ds_has_decision=ds_has_decision,
        decision_status=decision_status,
        fa_artifacts=fa_artifacts,
    ))

    # 7. Recommended next steps
    sections.append(_build_recommended_next_steps_section(
        fa_artifacts=fa_artifacts,
        ds_artifacts=ds_artifacts,
        ds_has_decision=ds_has_decision,
        decision_status=decision_status,
        md=md,
    ))

    # 8. Limitations
    sections.append(_build_limitations_section(
        md=md,
        fa_artifacts=fa_artifacts,
        decision_status=decision_status,
    ))

    return sections


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
) -> dict[str, Any]:
    bullets: list[str] = []

    has_fee_blocker = _has_fee_blocker(fa_artifacts)
    has_right_side_unconfirmed = _has_right_side_unconfirmed(fa_artifacts)
    has_missing_data = bool(md.get("critical_missing") or md.get("blockers"))
    has_profit_concern = _has_profit_concern(fa_artifacts)

    is_report_only = "FORMAL_TRADE_DECISION" not in intents and not ds_has_decision

    if decision_status == "BLOCKED":
        reasons = _collect_blocked_reasons(ds_artifacts, fa_artifacts)
        if reasons:
            bullets.append(f"Formal decision was evaluated and blocked: {', '.join(reasons[:3])}.")
        else:
            bullets.append("Formal decision was evaluated and blocked due to evidence or constraint issues.")

    elif decision_status == "DOWNGRADED":
        reasons = _collect_blocked_reasons(ds_artifacts, fa_artifacts)
        if reasons:
            bullets.append(f"Requested active action was downgraded to a passive posture: {', '.join(reasons[:3])}.")
        else:
            bullets.append("Requested active action was downgraded — evidence or constraints insufficient.")

    elif decision_status == "FORMAL_DECISION":
        bullets.append("Formal decision has been generated with evidence anchors. Review detail in decision explanation.")

    elif is_report_only:
        bullets.append("This is an analysis / report-only scenario. No formal trade decision was evaluated.")

    if has_fee_blocker:
        bullets.append("Short-holding redemption fee risk is prominent — active sell/reduce would trigger additional cost.")

    if has_right_side_unconfirmed:
        bullets.append("Right-side confirmation is missing — active add/buy is not yet advised; observe before acting.")

    if has_missing_data:
        bullets.append("Significant data is missing; recommendations are limited and should not be treated as actionable without data completion.")

    if has_profit_concern:
        bullets.append("Profit protection diagnostics are active — review partial trim options before adding to positions.")

    if not bullets:
        bullets.append("Analysis generated. Review report sections for detailed findings.")
        if not ds_has_decision:
            bullets.append("No formal decision was requested or evaluated.")

    return {
        "id": "direct_answer",
        "title": "Direct Answer",
        "bullets": bullets,
    }


# ── Section: evidence_status (enhanced) ─────────────────────────────────────


def _build_evidence_status_section(
    *,
    eg: dict[str, Any],
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    ds_has_decision: bool,
    decision_status: str,
    decision_ready: bool,
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

    # Concentration / overlap
    exposure = fa_artifacts.get("exposure_summary", {})
    if isinstance(exposure, dict):
        for key, val in exposure.items():
            if key in ("overlap_warning", "concentration_warning") and val:
                bullets.append(f"Exposure concern: {val}")
        if exposure.get("top_sector"):
            bullets.append(f"Top sector exposure: {exposure['top_sector']}")
        if exposure.get("top_industry"):
            bullets.append(f"Top industry exposure: {exposure['top_industry']}")

    # Cash / bond deployment
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

    # Profit protection
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

    # Drawdown / right-side
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

    # Fee / redemption
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

    # PnL summary
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


def _build_decision_section(ds_artifacts: dict[str, Any], decision_status: str) -> dict[str, Any]:
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


# ── Section: analysis-only (when no formal decision) ────────────────────────


def _build_analysis_only_section(fa_artifacts: dict[str, Any]) -> dict[str, Any]:
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
) -> dict[str, Any]:
    bullets: list[str] = []

    bullets.append("fund-agent does not execute broker orders. All output is analysis and audit artifacts only.")

    if ds_has_decision:
        bullets.append("Formal decision was produced by decision_support (the only authorized formal decision producer).")
        if decision_status == "BLOCKED":
            bullets.append("The formal decision was BLOCKED — do not treat as an execution signal.")
        elif decision_status == "DOWNGRADED":
            bullets.append("The formal decision was DOWNGRADED — active action was reduced to passive posture.")
        elif decision_status == "FORMAL_DECISION":
            bullets.append("A formal decision was generated with evidence anchors. Host should present to user for review.")
    else:
        bullets.append("No formal decision was produced. This is analysis-only output.")
        bullets.append("suggested_rebalance_plan from fund_analysis is analysis-only — not formal decisions.")

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
) -> dict[str, Any]:
    bullets: list[str] = []

    evidence_gap = fa_artifacts.get("evidence_gap_diagnostics", {})
    if isinstance(evidence_gap, dict):
        if evidence_gap.get("missing_recent_news"):
            bullets.append("Fetch recent fund/theme news and sentiment data to improve evidence quality.")
        if evidence_gap.get("missing_user_constraints"):
            bullets.append("Provide trading constraints (max_trade_pct, forbidden_actions, liquidity_reserve_pct).")
        if evidence_gap.get("missing_risk_preference"):
            bullets.append("Provide risk profile (conservative/balanced/aggressive) for calibrated advice.")
        if evidence_gap.get("missing_transaction_history"):
            bullets.append("Provide transaction history to enable cost basis and holding period analysis.")
        if evidence_gap.get("missing_benchmark"):
            bullets.append("Fetch benchmark history for relative performance assessment.")

        next_data = evidence_gap.get("next_data_to_fetch") or evidence_gap.get("recommended_next_data", [])
        if isinstance(next_data, list):
            for item in next_data:
                bullets.append(f"Recommended: {item}")

    if decision_status == "BLOCKED":
        bullets.append("Resolve blockers before re-evaluating formal decision.")
    elif decision_status == "DOWNGRADED":
        bullets.append("Address missing evidence and constraints to re-evaluate active action.")

    if _has_fee_blocker(fa_artifacts):
        bullets.append("Wait for short-holding period to expire or confirm exact redemption fee schedule.")

    if _has_right_side_unconfirmed(fa_artifacts):
        bullets.append("Wait for NAV/news/benchmark confirmation before considering add/buy.")
        bullets.append("Monitor: sustained NAV rebound, positive news catalyst, improving sentiment.")

    if not bullets:
        if ds_has_decision and decision_status == "FORMAL_DECISION":
            bullets.append("Review formal decision detail and present to user for approval.")
        else:
            bullets.append("Re-run analysis with updated data to track portfolio changes over time.")

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
) -> dict[str, Any]:
    bullets: list[str] = []

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

    fa_status_str = fa_artifacts.get("status", "")
    fa_warnings = fa_artifacts.get("warnings", [])
    if isinstance(fa_warnings, list) and fa_warnings:
        for w in fa_warnings[:3]:
            bullets.append(f"Warning: {w}")

    bullets.append("Safety: fund-agent does not execute broker orders. All formal decisions are audit artifacts only.")

    return {
        "id": "limitations",
        "title": "Limitations and Warnings",
        "bullets": bullets,
    }


# ── Chinese summary helpers ──────────────────────────────────────────────────


def _build_zh_blocked_reason(
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
) -> str:
    """Build a natural Chinese explanation for why a decision was blocked."""
    reasons: list[str] = []

    # Check analysis_plan blockers
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

    # Check decision blocked_by
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

    # Deduplicate
    seen: set[str] = set()
    unique: list[str] = []
    for r in reasons:
        if r not in seen:
            unique.append(r)
            seen.add(r)

    if unique:
        return f"已评估的正式决策被阻断（原因：{'、'.join(unique[:3])}），当前不应执行操作。"
    return "已评估的正式决策被阻断，当前不应执行操作。"


def _build_zh_downgraded_reason(
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


# ── Section: chinese_summary (zh-CN only) ───────────────────────────────────


def _build_chinese_summary(
    *,
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    ds_has_decision: bool,
    decision_status: str,
    eg: dict[str, Any],
    md: dict[str, Any],
) -> dict[str, Any]:
    """Build a natural Chinese summary suitable for direct user display."""
    bullets: list[str] = []

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
        "BLOCKED": _build_zh_blocked_reason(fa_artifacts, ds_artifacts),
        "DOWNGRADED": _build_zh_downgraded_reason(fa_artifacts, ds_artifacts),
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

    # Fee blocker — check both top-level and professional_diagnostics
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

    # Next steps
    if decision_status in ("BLOCKED", "DOWNGRADED"):
        bullets.append("建议补充缺失数据后重新评估正式决策。在阻断项清除之前，不建议执行主动操作。")

    if ds_has_decision and decision_status == "NO_FORMAL_DECISION":
        pass  # Already covered
    elif not ds_has_decision:
        bullets.append("本输出仅为分析报告，不包含正式交易决策。如需正式操作，请提供完整数据后调用 decision-support。")

    # Safety footer
    bullets.append("声明：fund-agent 不执行券商下单，所有输出为分析产物和审计痕迹。正式决策需经 decision_support 生成，并由用户审批。")

    return {
        "language": "zh-CN",
        "bullets": bullets,
    }


# ── Safety boundary ─────────────────────────────────────────────────────────


def _build_safety_boundary(
    *,
    ds_has_decision: bool,
    fa_artifacts: dict[str, Any],
    ds_artifacts: dict[str, Any],
    full_report_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis_only_sections: list[str] = []

    if fa_artifacts.get("suggested_rebalance_plan"):
        analysis_only_sections.append("suggested_rebalance_plan")
    if fa_artifacts.get("analysis_plan"):
        analysis_only_sections.append("analysis_plan")

    forbidden_found = []
    if full_report_data:
        forbidden_found = _find_forbidden_execution_fields(full_report_data)

    formal_source = "none"
    if ds_has_decision:
        formal_source = "decision_support"

    return {
        "no_broker_execution": len(forbidden_found) == 0,
        "forbidden_execution_fields_found": forbidden_found,
        "formal_decision_source": formal_source,
        "analysis_only_sections": analysis_only_sections,
    }


def _find_forbidden_execution_fields(data: Any, path: str = "") -> list[str]:
    """Recursively detect forbidden broker/order execution fields."""
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in FORBIDDEN_EXECUTION_FIELDS:
                found.append(f"{path}.{key}" if path else key)
            if isinstance(value, (dict, list)):
                new_path = f"{path}.{key}" if path else key
                found.extend(_find_forbidden_execution_fields(value, new_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                found.extend(_find_forbidden_execution_fields(item, f"{path}[{i}]"))
    return found


# ── Helper: conditional checks ──────────────────────────────────────────────


def _has_fee_blocker(fa_artifacts: dict[str, Any]) -> bool:
    redemption = fa_artifacts.get("redemption_fee_risk", {})
    if isinstance(redemption, dict) and redemption.get("has_blocker"):
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

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for r in reasons:
        if r not in seen:
            unique.append(r)
            seen.add(r)
    return unique


def _get_fund_names(fund_codes: list[str], fa_artifacts: dict[str, Any]) -> list[str]:
    names: list[str] = []
    fund_profiles = fa_artifacts.get("fund_profiles", {})
    if isinstance(fund_profiles, dict):
        for code in fund_codes:
            profile = fund_profiles.get(str(code), {})
            name = profile.get("name") or profile.get("fund_name", str(code))
            names.append(str(name))
    return names or [str(c) for c in fund_codes]
