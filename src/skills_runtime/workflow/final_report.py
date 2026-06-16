"""Deterministic advisory workflow final report/explanation composer.

Given fund_analysis output, optional decision_support output, and
EvidenceGraph diagnostics, produce a host-facing structured final
explanation. No LLM, no network, no MCP, no decision creation.
"""

from __future__ import annotations

from typing import Any

FORBIDDEN_EXECUTION_FIELDS = frozenset(
    {
        "broker_order_id",
        "order_id",
        "order_status",
        "filled_quantity",
        "fill_price",
        "execution_venue",
        "submitted_at",
        "broker",
        "exchange_order_id",
    }
)


def compose_advisory_workflow_report(
    *,
    scenario_id: str = "",
    fund_analysis_artifacts: dict[str, Any] | None = None,
    decision_support_artifacts: dict[str, Any] | None = None,
    evidence_bridge_result: dict[str, Any] | None = None,
    fund_analysis_status: str = "OK",
) -> dict[str, Any]:
    """Compose a deterministic workflow-level final explanation.

    Args:
        scenario_id: Identifier for the advisory scenario.
        fund_analysis_artifacts: Artifacts from FundAnalysisSkill output.
        decision_support_artifacts: Artifacts from DecisionSupportSkill output,
            or None if decision_support was not called.
        evidence_bridge_result: Result from evidence_bridge.build_evidence_graph_from_workflow.
        fund_analysis_status: Status from FundAnalysisSkill output.

    Returns:
        Structured dict with workflow_summary, user_facing_sections,
        and safety_boundary.
    """
    fa = fund_analysis_artifacts or {}
    ds = decision_support_artifacts or {}
    bridge = evidence_bridge_result or {}

    report_status = _compute_report_status(fund_analysis_status, fa)
    decision_status = _compute_decision_status(ds, fa)
    data_completeness_grade = _extract_data_completeness_grade(fa)
    decision_support_ready = _extract_decision_support_ready(fa)

    workflow_summary = {
        "scenario_id": scenario_id,
        "report_status": report_status,
        "decision_status": decision_status,
        "data_completeness_grade": data_completeness_grade,
        "decision_support_ready": decision_support_ready,
    }

    user_facing_sections = [
        _build_summary_section(fa, ds, report_status, decision_status),
        _build_evidence_status_section(fa, bridge),
        _build_decision_explanation_section(ds, fa),
        _build_limitations_section(fa, bridge, decision_status),
    ]

    safety_boundary = {
        "no_broker_execution": True,
        "formal_decision_source": _formal_decision_source(ds),
        "analysis_only_sections": _analysis_only_sections(fa),
    }

    return {
        "workflow_summary": workflow_summary,
        "user_facing_sections": user_facing_sections,
        "safety_boundary": safety_boundary,
    }


def _compute_report_status(fa_status: str, fa: dict[str, Any]) -> str:
    if fa_status == "FAILED":
        return "BLOCKED"
    data_completeness = fa.get("data_completeness", {})
    grade = data_completeness.get("grade", "D")
    if grade in ("C", "D"):
        return "PARTIAL"
    return "OK"


def _compute_decision_status(ds: dict[str, Any], fa: dict[str, Any]) -> str:
    if not ds:
        plan = fa.get("analysis_plan", {})
        if not plan.get("decision_support_ready", False):
            return "NO_FORMAL_DECISION"
        return "NO_FORMAL_DECISION"

    decision = ds.get("decision", {})
    if isinstance(decision, dict):
        action = str(decision.get("action", "")).upper()
        blocked_by = decision.get("blocked_by", [])
        evidence_state = str(decision.get("evidence_state", "")).upper()

        if blocked_by or evidence_state in ("CONSTRAINT_BLOCKED", "BUDGET_BLOCKED"):
            return "BLOCKED"
        if evidence_state == "DOWNGRADED":
            return "DOWNGRADED"
        if action in ("HOLD", "WAIT", "PAUSE_DCA"):
            if "DOWNGRADED_ACTIVE_TO_HOLD" in decision.get("decision_reason_codes", []):
                return "DOWNGRADED"
            return "NO_FORMAL_DECISION"
        if action in ("BUY", "SELL", "INCREASE", "REDUCE"):
            return "FORMAL_DECISION"

    decisions = ds.get("decisions", [])
    if isinstance(decisions, list) and decisions:
        has_active = any(
            str(d.get("action", "")).upper() in ("BUY", "SELL", "INCREASE", "REDUCE")
            for d in decisions
            if isinstance(d, dict)
        )
        has_blocked = any(
            d.get("blocked_by") or str(d.get("evidence_state", "")).upper() in ("CONSTRAINT_BLOCKED", "BUDGET_BLOCKED")
            for d in decisions
            if isinstance(d, dict)
        )
        has_downgraded = any(
            "DOWNGRADED_ACTIVE_TO_HOLD" in d.get("decision_reason_codes", []) for d in decisions if isinstance(d, dict)
        )
        if has_active:
            if has_blocked:
                return "DOWNGRADED"
            return "FORMAL_DECISION"
        if has_downgraded:
            return "DOWNGRADED"
        if has_blocked:
            return "BLOCKED"
        return "NO_FORMAL_DECISION"

    return "NO_FORMAL_DECISION"


def _extract_data_completeness_grade(fa: dict[str, Any]) -> str:
    dc = fa.get("data_completeness", {})
    return dc.get("grade", "D") if isinstance(dc, dict) else "D"


def _extract_decision_support_ready(fa: dict[str, Any]) -> bool:
    plan = fa.get("analysis_plan", {})
    return bool(plan.get("decision_support_ready", False)) if isinstance(plan, dict) else False


def _build_summary_section(
    fa: dict[str, Any],
    ds: dict[str, Any],
    report_status: str,
    decision_status: str,
) -> dict[str, Any]:
    bullets: list[str] = []

    ps = fa.get("portfolio_summary", {})
    if isinstance(ps, dict):
        total_value = ps.get("total_value")
        if total_value:
            bullets.append(f"Portfolio total value: {total_value}")

    risk_flags = fa.get("risk_flags", [])
    if isinstance(risk_flags, list) and risk_flags:
        bullets.append(f"Risk flags identified: {len(risk_flags)}")

    pp = fa.get("profit_protection_diagnostics", {})
    if isinstance(pp, dict):
        items = pp.get("items", [])
        high_profit = [i for i in items if isinstance(i, dict) and i.get("profit_level") in ("high", "very_high")]
        if high_profit:
            bullets.append(f"High/very-high profit positions: {len(high_profit)}")

    if report_status == "PARTIAL":
        bullets.append("Report is partial due to missing data sections")

    if decision_status == "FORMAL_DECISION":
        bullets.append("Formal decision produced by decision_support")
    elif decision_status == "BLOCKED":
        bullets.append("Formal decision blocked due to constraints or insufficient evidence")
    elif decision_status == "DOWNGRADED":
        bullets.append("Requested active action downgraded to passive action")
    else:
        bullets.append("No formal decision produced (analysis-only or insufficient data)")

    return {
        "id": "summary",
        "title": "Advisory Workflow Summary",
        "bullets": bullets,
    }


def _build_evidence_status_section(
    fa: dict[str, Any],
    bridge: dict[str, Any],
) -> dict[str, Any]:
    bullets: list[str] = []

    gap = fa.get("evidence_gap_diagnostics", {})
    if isinstance(gap, dict):
        missing = [k for k, v in gap.items() if v is True and k != "details"]
        if missing:
            bullets.append(f"Missing evidence categories: {', '.join(missing)}")
        else:
            bullets.append("All evidence categories present")

    included = bridge.get("included_evidence_count", 0)
    host_soft = bridge.get("host_soft_evidence_count", 0)
    bullets.append(f"Evidence items in graph: {included}")
    if host_soft:
        bullets.append(f"Host-provided soft evidence items: {host_soft}")

    invalid = bridge.get("missing_or_invalid_evidence", [])
    if invalid:
        bullets.append(f"Invalid/missing evidence entries: {len(invalid)}")

    return {
        "id": "evidence_status",
        "title": "Evidence Status",
        "bullets": bullets,
    }


def _build_decision_explanation_section(
    ds: dict[str, Any],
    fa: dict[str, Any],
) -> dict[str, Any]:
    bullets: list[str] = []

    if not ds:
        plan = fa.get("analysis_plan", {})
        if isinstance(plan, dict):
            blockers = plan.get("blockers", [])
            if blockers:
                bullets.append(f"Decision support blocked by: {', '.join(blockers)}")
            else:
                bullets.append("Decision support not requested for this scenario")
        return {
            "id": "decision_explanation",
            "title": "Decision Explanation",
            "bullets": bullets or ["No formal decision was produced"],
        }

    decision = ds.get("decision", {})
    if isinstance(decision, dict):
        action = decision.get("action", "UNKNOWN")
        bullets.append(f"Final action: {action}")
        reason_codes = decision.get("decision_reason_codes", [])
        if reason_codes:
            bullets.append(f"Reason codes: {', '.join(reason_codes)}")
        blocked_by = decision.get("blocked_by", [])
        if blocked_by:
            bullets.append(f"Blocked by: {', '.join(blocked_by)}")
        evidence_state = decision.get("evidence_state", "")
        if evidence_state:
            bullets.append(f"Evidence state: {evidence_state}")

    ledger = ds.get("execution_ledger", {})
    if isinstance(ledger, dict):
        summary = ledger.get("ledger_summary", {})
        if isinstance(summary, dict):
            active = summary.get("active_decision_count", 0)
            passive = summary.get("passive_decision_count", 0)
            downgraded = summary.get("downgraded_decision_count", 0)
            blocked = summary.get("blocked_decision_count", 0)
            if active:
                bullets.append(f"Active decisions: {active}")
            if passive:
                bullets.append(f"Passive decisions: {passive}")
            if downgraded:
                bullets.append(f"Downgraded decisions: {downgraded}")
            if blocked:
                bullets.append(f"Blocked decisions: {blocked}")

    anchor_diag = ds.get("evidence_anchor_diagnostics", {})
    if isinstance(anchor_diag, dict):
        limitations = anchor_diag.get("limitations", [])
        if limitations:
            bullets.extend([f"Anchor limitation: {lim}" for lim in limitations[:3]])

    risk_conflicts = ds.get("risk_constraint_conflicts", {})
    if isinstance(risk_conflicts, dict):
        items = risk_conflicts.get("items", [])
        if items:
            bullets.append(f"Risk constraint conflicts: {len(items)}")

    return {
        "id": "decision_explanation",
        "title": "Decision Explanation",
        "bullets": bullets,
    }


def _build_limitations_section(
    fa: dict[str, Any],
    bridge: dict[str, Any],
    decision_status: str,
) -> dict[str, Any]:
    bullets: list[str] = []

    limitations = fa.get("report_limitations", [])
    if isinstance(limitations, list):
        for lim in limitations[:5]:
            if isinstance(lim, str):
                bullets.append(lim)

    bridge_warnings = bridge.get("warnings", [])
    for w in bridge_warnings[:3]:
        bullets.append(f"Evidence bridge warning: {w}")

    if decision_status in ("BLOCKED", "DOWNGRADED"):
        bullets.append("Active action was blocked or downgraded; no execution should follow")

    bullets.append("This report is analysis-only and does not constitute broker order execution")

    return {
        "id": "limitations",
        "title": "Limitations and Safety Boundaries",
        "bullets": bullets,
    }


def _formal_decision_source(ds: dict[str, Any]) -> str:
    if ds:
        return "decision_support"
    return "none"


def _analysis_only_sections(fa: dict[str, Any]) -> list[str]:
    sections: list[str] = []
    if fa.get("suggested_rebalance_plan"):
        sections.append("suggested_rebalance_plan")
    if fa.get("profit_protection_diagnostics"):
        sections.append("profit_protection_diagnostics")
    if fa.get("right_side_confirmation_diagnostics"):
        sections.append("right_side_confirmation_diagnostics")
    if fa.get("cash_deployment_diagnostics"):
        sections.append("cash_deployment_diagnostics")
    return sections


def check_no_forbidden_execution_fields(output: dict[str, Any]) -> list[str]:
    """Recursively check that no forbidden broker/execution fields exist."""
    violations: list[str] = []
    _check_dict(output, "", violations)
    return violations


def _check_dict(data: dict[str, Any], path: str, violations: list[str]) -> None:
    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key
        if key in FORBIDDEN_EXECUTION_FIELDS:
            violations.append(f"Forbidden field found: {current_path}")
        if isinstance(value, dict):
            _check_dict(value, current_path, violations)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    _check_dict(item, f"{current_path}[{i}]", violations)
