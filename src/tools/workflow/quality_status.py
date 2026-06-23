"""Quality gate status split -- compute_quality_status.

Extracted from advisory_quality_gate.py for modularity. Computes split
status (pipeline / data_readiness / engineering / report_professional)
from a quality gate result and data completeness info.

No network, no LLM, no side effects.
"""

from __future__ import annotations

from typing import Any


def compute_quality_status(
    quality_gate_result: dict[str, Any],
    data_completeness: dict[str, Any] | None = None,
    fund_analysis_output: dict[str, Any] | None = None,
    final_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute split status from quality gate and data completeness.

    Returns:
    - pipeline_status: SUCCESS | PARTIAL | FAILED
    - data_readiness_status: COMPLETE | INCOMPLETE | BLOCKED_BY_MISSING_CORE_DATA
    - engineering_status: PASS | NEEDS_FIX | FAILED
    - report_professional_status: PROFESSIONAL | LIMITED_BY_DATA | NOT_USABLE
    - required_user_data: list of missing data fields
    """
    qg = quality_gate_result or {}
    checks = qg.get("checks", [])
    fail_count = qg.get("summary", {}).get("fail_count", 0)
    warn_count = qg.get("summary", {}).get("warn_count", 0)

    dc = data_completeness or {}
    grade = dc.get("grade", "D")
    score = dc.get("score", 0.0)
    missing_sections = dc.get("missing_sections", [])
    critical_missing = dc.get("critical_missing", [])

    pipeline_status = "PARTIAL" if fail_count > 0 or warn_count > 0 else "SUCCESS"

    core_missing = {"Portfolio Snapshot", "Current Value Or Nav"}
    has_core_missing = any(ms in core_missing for ms in critical_missing)

    if has_core_missing:
        data_readiness_status = "BLOCKED_BY_MISSING_CORE_DATA"
    elif grade in ("C", "D"):
        data_readiness_status = "INCOMPLETE"
    else:
        data_readiness_status = "COMPLETE"

    hard_failure_checks = {
        "fund_analysis_no_formal_decision",
        "no_broker_execution",
        "active_trade_anchor_gate",
    }

    engineering_failures = [c for c in checks if c.get("status") == "FAIL" and c.get("id") in hard_failure_checks]

    if engineering_failures:
        engineering_status = "FAILED"
    elif fail_count > 0:
        missing_data_related = [c for c in checks if c.get("status") == "FAIL" and "missing" in c.get("id", "").lower()]
        engineering_status = "PASS" if missing_data_related and not engineering_failures else "NEEDS_FIX"
    else:
        engineering_status = "PASS"

    if has_core_missing or grade == "D":
        report_professional_status = "NOT_USABLE"
    elif grade == "C" or missing_sections:
        report_professional_status = "LIMITED_BY_DATA"
    else:
        report_professional_status = "PROFESSIONAL"

    required_user_data: list[str] = []

    fa = fund_analysis_output or {}
    fa_artifacts = fa.get("artifacts", {})

    factor_snapshot = fa_artifacts.get("factor_snapshot", {})
    if factor_snapshot:
        dq = factor_snapshot.get("data_quality", {})
        if dq.get("current_value_missing_count", 0) > 0:
            required_user_data.append("current_value")
        if dq.get("cost_basis_missing_count", 0) > 0:
            required_user_data.append("cost_basis")
        if dq.get("units_missing_count", 0) > 0:
            required_user_data.append("units")
        if dq.get("nav_missing_count", 0) > 0:
            required_user_data.append("nav")

    if "Fund Profiles" in missing_sections:
        required_user_data.append("fund_profile")
    if "Nav History" in missing_sections:
        required_user_data.append("NAV_history")
    if "Holdings" in missing_sections:
        required_user_data.append("holdings")
    if "Risk Profile" in missing_sections:
        required_user_data.append("risk_profile")

    if factor_snapshot:
        uncertainty_note = factor_snapshot.get("data_quality", {}).get("uncertainty_note")
        if not uncertainty_note and data_readiness_status != "COMPLETE" and engineering_status == "PASS":
            engineering_status = "NEEDS_FIX"

    if engineering_status == "FAILED":
        pipeline_status = "FAILED"

    return {
        "pipeline_status": pipeline_status,
        "data_readiness_status": data_readiness_status,
        "engineering_status": engineering_status,
        "report_professional_status": report_professional_status,
        "required_user_data": list(set(required_user_data)),
        "data_completeness_grade": grade,
        "data_completeness_score": score,
        "quality_gate_passed": qg.get("passed", False),
        "quality_gate_fail_count": fail_count,
        "quality_gate_warn_count": warn_count,
    }
