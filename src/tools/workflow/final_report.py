"""Workflow-level final report / explanation composer.

Given fund_analysis output, optional decision_support output, and
EvidenceGraph diagnostics, produce a host-facing structured final
explanation. This layer does not use LLM, does not create decisions,
and only composes existing artifacts.
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


def compose_advisory_workflow_report(
    *,
    scenario_id: str = "",
    fund_analysis_output: dict[str, Any] | None = None,
    decision_support_output: dict[str, Any] | None = None,
    evidence_graph_diagnostics: dict[str, Any] | None = None,
    missing_data_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a host-facing structured final explanation from all workflow artifacts."""
    fa = fund_analysis_output or {}
    fa_artifacts = fa.get("artifacts", {}) if isinstance(fa, dict) else {}
    ds = decision_support_output or {}
    ds_artifacts = ds.get("artifacts", {}) if isinstance(ds, dict) else {}
    eg = evidence_graph_diagnostics or {}
    md = missing_data_diagnostics or {}

    fa_status = str(fa.get("status", "PARTIAL"))
    ds_has_decision = bool(ds_artifacts.get("decision") or ds_artifacts.get("execution_ledger"))
    analysis_plan = fa_artifacts.get("analysis_plan", {}) if isinstance(fa_artifacts, dict) else {}
    decision_ready = bool(analysis_plan.get("decision_support_ready", False))

    report_status = _compute_report_status(fa_status, fa_artifacts, md)
    decision_status = _compute_decision_status(ds_has_decision, ds_artifacts)

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

    return {
        "workflow_summary": {
            "scenario_id": scenario_id,
            "report_status": report_status,
            "decision_status": decision_status,
            "data_completeness_grade": _data_completeness_grade(fa_artifacts, md),
            "decision_support_ready": decision_ready,
        },
        "user_facing_sections": user_facing_sections,
        "safety_boundary": safety_boundary,
    }


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
    return "OK" if fa_status == "OK" else "PARTIAL"


def _compute_decision_status(
    ds_has_decision: bool,
    ds_artifacts: dict[str, Any],
) -> str:
    """Compute decision_status from decision_support output.

    Priority:
    1. If no decision_support output exists → NO_FORMAL_DECISION.
    2. Check single-decision path first (decision dict).
    3. Then check multi-decision path (ledger/decisions).
    """
    if not ds_has_decision:
        return "NO_FORMAL_DECISION"

    # Single-decision path — check first
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

    # Multi-decision path — check ledger summary
    ledger = ds_artifacts.get("execution_ledger", {})
    if isinstance(ledger, dict):
        summary = ledger.get("ledger_summary", {})
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

    # Multi-decision fallback: check decisions list
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
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []

    sections.append(_build_summary_section(
        scenario_id=scenario_id,
        fa_status=fa_status,
        decision_status=decision_status,
        decision_ready=decision_ready,
        fa_artifacts=fa_artifacts,
    ))

    sections.append(_build_evidence_section(
        eg=eg,
        fa_artifacts=fa_artifacts,
    ))

    if ds_has_decision:
        sections.append(_build_decision_section(ds_artifacts, decision_status))
    elif decision_status == "NO_FORMAL_DECISION":
        sections.append(_build_analysis_only_section(fa_artifacts))

    sections.append(_build_limitations_section(
        md=md,
        fa_artifacts=fa_artifacts,
        decision_status=decision_status,
    ))

    return sections


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


def _build_evidence_section(
    *,
    eg: dict[str, Any],
    fa_artifacts: dict[str, Any],
) -> dict[str, Any]:
    bullets: list[str] = []

    graph_stats = eg.get("graph", {}).get("stats", {})
    if isinstance(graph_stats, dict):
        bullets.append(f"Total evidence items: {graph_stats.get('total', 0)}")
        bullets.append(f"Hard evidence: {graph_stats.get('hard', 0)}")
        bullets.append(f"Soft evidence: {graph_stats.get('soft', 0)}")
        bullets.append(f"Hybrid evidence: {graph_stats.get('hybrid', 0)}")
        conflicts = graph_stats.get("conflicts", 0)
        if conflicts:
            bullets.append(f"Conflicts detected: {conflicts}")

    included = eg.get("included_evidence_count", 0)
    host_soft = eg.get("host_soft_evidence_count", 0)
    bullets.append(f"Evidence items from fund_analysis + host: {included}")
    bullets.append(f"Host soft evidence (news/sentiment): {host_soft}")

    warnings = eg.get("warnings", [])
    missing = eg.get("missing_or_invalid_evidence", [])
    if missing:
        bullets.append(f"Missing or invalid evidence items: {len(missing)}")
    if warnings:
        bullets.append(f"Evidence warnings: {len(warnings)}")

    evidence_gap = fa_artifacts.get("evidence_gap_diagnostics", {})
    if isinstance(evidence_gap, dict):
        gap_items = evidence_gap.get("items") or evidence_gap.get("details", [])
        if isinstance(gap_items, list):
            for gap in gap_items:
                if isinstance(gap, dict):
                    desc = gap.get("description") or gap.get("gap", "")
                    if desc:
                        bullets.append(f"Evidence gap: {desc}")

    return {
        "id": "evidence_status",
        "title": "Evidence Status",
        "bullets": bullets,
    }


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
        bullets.append(f"Decision action: {action}")
        bullets.append(f"Execution amount: {amount}")
        bullets.append(f"Evidence state: {state}")
        if blocked:
            bullets.append(f"Blocked by: {', '.join(str(b) for b in blocked)}")
        if reason_codes:
            bullets.append(f"Reason codes: {', '.join(str(r) for r in reason_codes[:5])}")

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

    # Recursive detection of forbidden execution fields
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
    """Recursively detect forbidden broker/order execution fields.

    Returns list of dotted paths where forbidden fields were found.
    """
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
