"""Workflow-level final report / explanation composer.

Given fund_analysis output, optional decision_support output, and
EvidenceGraph diagnostics, produce a host-facing structured final
explanation. This layer does not use LLM, does not create decisions,
and only composes existing artifacts.

Purpose: help external hosts render the complete advisory result
clearly and deterministically.
"""

from __future__ import annotations

from typing import Any


def compose_advisory_workflow_report(
    *,
    scenario_id: str = "",
    fund_analysis_output: dict[str, Any] | None = None,
    decision_support_output: dict[str, Any] | None = None,
    evidence_graph_diagnostics: dict[str, Any] | None = None,
    missing_data_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a host-facing structured final explanation from all workflow artifacts.

    Args:
        scenario_id: Identifier for the advisory scenario.
        fund_analysis_output: Dict from SkillOutput.to_dict() of fund_analysis.
        decision_support_output: Dict from SkillOutput.to_dict() of decision_support (optional).
        evidence_graph_diagnostics: Dict from WorkflowEvidenceGraphResult.to_dict().
        missing_data_diagnostics: Dict of missing data details from fund_analysis.

    Returns:
        Structured final explanation dict.
    """
    fa = fund_analysis_output or {}
    fa_artifacts = fa.get("artifacts", {}) if isinstance(fa, dict) else {}
    ds = decision_support_output or {}
    ds_artifacts = ds.get("artifacts", {}) if isinstance(ds, dict) else {}
    eg = evidence_graph_diagnostics or {}
    md = missing_data_diagnostics or {}

    # Determine statuses
    fa_status = str(fa.get("status", "PARTIAL"))
    ds_has_decision = bool(ds_artifacts.get("decision") or ds_artifacts.get("execution_ledger"))
    analysis_plan = fa_artifacts.get("analysis_plan", {}) if isinstance(fa_artifacts, dict) else {}
    decision_ready = bool(analysis_plan.get("decision_support_ready", False))

    report_status = _compute_report_status(fa_status, fa_artifacts, md)
    decision_status = _compute_decision_status(ds_has_decision, decision_ready, ds_artifacts)

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
    decision_ready: bool,
    ds_artifacts: dict[str, Any],
) -> str:
    if not decision_ready:
        return "NO_FORMAL_DECISION"

    if not ds_has_decision:
        return "NO_FORMAL_DECISION"

    decision = ds_artifacts.get("decision", {})
    if isinstance(decision, dict):
        action = str(decision.get("action", "")).upper()
        if action in ("HOLD", "WAIT", "PAUSE_DCA"):
            if decision.get("blocked_by"):
                return "BLOCKED"
            return "DOWNGRADED"

    ledger = ds_artifacts.get("execution_ledger", {})
    if isinstance(ledger, dict):
        summary = ledger.get("ledger_summary", {})
        if isinstance(summary, dict):
            active = summary.get("active_decision_count", 0)
            blocked = summary.get("blocked_decision_count", 0)
            if blocked > 0 and active == 0:
                return "BLOCKED"
            if blocked > 0:
                return "DOWNGRADED"

    return "FORMAL_DECISION"


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
        sections.append(_build_decision_section(ds_artifacts))
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
        bullets.append("This report contains analysis only — no formal investment decisions.")
    elif decision_status == "FORMAL_DECISION":
        bullets.append("Formal investment decisions have been generated.")
    elif decision_status in ("DOWNGRADED", "BLOCKED"):
        bullets.append("Requested action was downgraded or blocked due to constraints or missing evidence.")

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


def _build_decision_section(ds_artifacts: dict[str, Any]) -> dict[str, Any]:
    bullets: list[str] = []

    decision = ds_artifacts.get("decision", {})
    if isinstance(decision, dict):
        action = decision.get("action", "N/A")
        amount = decision.get("execution_amount", 0)
        state = decision.get("evidence_state", "N/A")
        blocked = decision.get("blocked_by", [])
        bullets.append(f"Decision action: {action}")
        bullets.append(f"Execution amount: {amount}")
        bullets.append(f"Evidence state: {state}")
        if blocked:
            bullets.append(f"Blocked by: {', '.join(str(b) for b in blocked)}")

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
        if valid:
            bullets.append(f"Valid evidence anchors: {len(valid)}")
        if invalid:
            bullets.append(f"Invalid evidence anchors: {len(invalid)}")
        if missing:
            bullets.append(f"Missing evidence anchors: {len(missing)}")

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

    bullets.append("No formal investment decision was produced by this workflow.")
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

    if decision_status in ("DOWNGRADED", "BLOCKED"):
        bullets.append("Formal active action was downgraded or blocked. See decision explanation for details.")
    elif decision_status == "NO_FORMAL_DECISION":
        bullets.append("Decision support was either not requested or blocked by missing evidence/data.")

    fa_status = fa_artifacts.get("status", "")
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
) -> dict[str, Any]:
    analysis_only_sections: list[str] = []

    if fa_artifacts.get("suggested_rebalance_plan"):
        analysis_only_sections.append("suggested_rebalance_plan")
    if fa_artifacts.get("analysis_plan"):
        analysis_only_sections.append("analysis_plan")

    has_broker = False
    for candidate in fa_artifacts:
        if "broker" in str(candidate).lower() or "order" in str(candidate).lower():
            has_broker = True
    for candidate in ds_artifacts:
        if "broker" in str(candidate).lower() or "order" in str(candidate).lower():
            has_broker = True

    formal_source = "none"
    if ds_has_decision:
        formal_source = "decision_support"

    return {
        "no_broker_execution": not has_broker,
        "formal_decision_source": formal_source,
        "analysis_only_sections": analysis_only_sections,
    }
