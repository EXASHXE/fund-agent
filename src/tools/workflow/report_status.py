"""Report status computation helpers.

Deterministic, pure functions for computing report_status, decision_status,
data completeness grade, and language normalization.
"""

from __future__ import annotations

from typing import Any


def normalize_language(language: str) -> str:
    """Normalize language string to 'en' or 'zh-CN'."""
    normalized = str(language).replace("_", "-")
    if normalized.lower() in {"zh-cn", "zh-hans-cn", "zh"}:
        return "zh-CN"
    return "en"


def compute_report_status(
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


def compute_decision_status(
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


def data_completeness_grade(
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
