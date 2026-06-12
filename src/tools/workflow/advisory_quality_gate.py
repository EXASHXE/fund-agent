"""Advisory quality gate — deterministic workflow safety and quality checks.

Evaluates fund_analysis, evidence_graph, decision_support, and final_report
outputs against 11 required checks. Returns a structured pass/fail/warn result.

No network calls, no LLM, no secrets, no chain-of-thought.
"""

from __future__ import annotations

import re
from typing import Any

from .report_safety import FORBIDDEN_EXECUTION_FIELDS, find_forbidden_execution_fields

_EXTENDED_FORBIDDEN_FIELDS = FORBIDDEN_EXECUTION_FIELDS | frozenset({
    "actual_fill",
    "filled_at",
    "trade_confirmation_id",
})


def evaluate_advisory_quality_gate(
    fund_analysis_output: dict,
    evidence_graph: dict | None = None,
    decision_support_output: dict | None = None,
    final_report: dict | None = None,
    expected_behavior: dict | None = None,
    language: str | None = None,
) -> dict:
    checks: list[dict] = []

    fa = fund_analysis_output or {}
    eg = evidence_graph or {}
    ds = decision_support_output
    fr = final_report or {}
    eb = expected_behavior or {}

    checks.append(_check_fund_analysis_no_formal_decision(fa))
    checks.append(_check_formal_source_boundary(fr, ds))
    checks.append(_check_report_only_no_decision_support(fr, ds, eb))
    checks.append(_check_decision_support_required_artifacts(ds))
    checks.append(_check_active_trade_anchor_gate(ds, eg))
    checks.append(_check_missing_data_disclosed(fa, fr))
    checks.append(_check_no_broker_execution(fa, eg, ds, fr))
    checks.append(_check_action_boundary_present(fr, ds))
    checks.append(_check_zh_direct_answer_present(fr, language))
    checks.append(_check_suggested_rebalance_analysis_only(fa, fr))
    checks.append(_check_provider_data_provenance_present(fa, eg, fr, eb))

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    warn_count = sum(1 for c in checks if c["status"] == "WARN")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {
        "passed": fail_count == 0,
        "checks": checks,
        "summary": {
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
        },
    }


def _make_check(check_id: str, status: str, message: str, details: dict | None = None) -> dict:
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "details": details or {},
    }


def _check_fund_analysis_no_formal_decision(fa: dict) -> dict:
    fa_artifacts = fa.get("artifacts", {}) if isinstance(fa, dict) else {}
    forbidden_keys = {"decision", "decisions", "execution_ledger", "ExecutionLedger"}
    found = [k for k in forbidden_keys if k in fa_artifacts]
    broker_fields = _find_extended_forbidden(fa)
    if found:
        return _make_check(
            "fund_analysis_no_formal_decision",
            "FAIL",
            f"fund_analysis output contains forbidden formal decision keys: {found}",
            {"found_keys": found},
        )
    if broker_fields:
        return _make_check(
            "fund_analysis_no_formal_decision",
            "FAIL",
            f"fund_analysis output contains broker/order execution fields: {broker_fields}",
            {"found_fields": broker_fields},
        )
    return _make_check(
        "fund_analysis_no_formal_decision",
        "PASS",
        "fund_analysis output contains no formal Decision, ExecutionLedger, or broker execution fields",
    )


def _check_formal_source_boundary(fr: dict, ds: dict | None) -> dict:
    summary = fr.get("workflow_summary", {}) if isinstance(fr, dict) else {}
    safety = fr.get("safety_boundary", {}) if isinstance(fr, dict) else {}
    decision_status = str(summary.get("decision_status", ""))
    formal_source = str(safety.get("formal_decision_source", ""))

    if decision_status in ("FORMAL_DECISION", "BLOCKED", "DOWNGRADED"):
        if formal_source != "decision_support":
            return _make_check(
                "formal_source_boundary",
                "FAIL",
                f"decision_status={decision_status} but formal_decision_source={formal_source}, expected decision_support",
                {"decision_status": decision_status, "formal_decision_source": formal_source},
            )
    if ds is None and decision_status not in ("NO_FORMAL_DECISION", ""):
        return _make_check(
            "formal_source_boundary",
            "FAIL",
            f"decision_support_output is None but decision_status={decision_status}, expected NO_FORMAL_DECISION",
            {"decision_status": decision_status},
        )
    return _make_check(
        "formal_source_boundary",
        "PASS",
        "formal decision source boundary is consistent",
    )


def _check_report_only_no_decision_support(fr: dict, ds: dict | None, eb: dict) -> dict:
    ds_called = eb.get("decision_support_called")
    if ds_called is not False:
        return _make_check(
            "report_only_no_decision_support",
            "PASS",
            "expected_behavior.decision_support_called is not False, check not applicable",
        )
    summary = fr.get("workflow_summary", {}) if isinstance(fr, dict) else {}
    safety = fr.get("safety_boundary", {}) if isinstance(fr, dict) else {}
    decision_status = str(summary.get("decision_status", ""))
    formal_source = str(safety.get("formal_decision_source", ""))

    if ds is not None:
        return _make_check(
            "report_only_no_decision_support",
            "FAIL",
            "report-only scenario has decision_support_output present",
            {"decision_support_output": "present"},
        )
    if decision_status != "NO_FORMAL_DECISION":
        return _make_check(
            "report_only_no_decision_support",
            "FAIL",
            f"report-only scenario has decision_status={decision_status}, expected NO_FORMAL_DECISION",
            {"decision_status": decision_status},
        )
    if formal_source != "none":
        return _make_check(
            "report_only_no_decision_support",
            "FAIL",
            f"report-only scenario has formal_decision_source={formal_source}, expected none",
            {"formal_decision_source": formal_source},
        )
    return _make_check(
        "report_only_no_decision_support",
        "PASS",
        "report-only scenario has no decision_support, NO_FORMAL_DECISION, and formal_source=none",
    )


def _check_decision_support_required_artifacts(ds: dict | None) -> dict:
    if ds is None:
        return _make_check(
            "decision_support_required_artifacts",
            "PASS",
            "no decision_support output, check not applicable",
        )
    ds_artifacts = ds.get("artifacts", {}) if isinstance(ds, dict) else {}
    missing: list[str] = []

    has_ledger = bool(ds_artifacts.get("execution_ledger"))
    has_decision = bool(ds_artifacts.get("decision") or ds_artifacts.get("decisions"))
    if not has_ledger and not has_decision:
        missing.append("execution_ledger or decision")

    ledger = ds_artifacts.get("execution_ledger", {})
    if isinstance(ledger, dict):
        if "ledger_summary" not in ledger:
            missing.append("ledger_summary")

    if "evidence_anchor_diagnostics" not in ds_artifacts:
        missing.append("evidence_anchor_diagnostics")
    if "risk_constraint_conflicts" not in ds_artifacts:
        missing.append("risk_constraint_conflicts")

    decision = ds_artifacts.get("decision", {})
    if isinstance(decision, dict) and decision.get("action", "") in ("BUY", "SELL", "INCREASE", "REDUCE"):
        if "execution_amount" not in decision:
            missing.append("execution_amount in decision")
        if "rationale_anchor" not in decision:
            missing.append("rationale_anchor in decision")

    if missing:
        return _make_check(
            "decision_support_required_artifacts",
            "FAIL",
            f"decision_support output missing required artifacts: {missing}",
            {"missing": missing},
        )
    return _make_check(
        "decision_support_required_artifacts",
        "PASS",
        "decision_support output contains all required artifacts",
    )


def _check_active_trade_anchor_gate(ds: dict | None, eg: dict) -> dict:
    if ds is None:
        return _make_check(
            "active_trade_anchor_gate",
            "PASS",
            "no decision_support output, check not applicable",
        )
    ds_artifacts = ds.get("artifacts", {}) if isinstance(ds, dict) else {}
    decision = ds_artifacts.get("decision", {})
    if not isinstance(decision, dict):
        return _make_check(
            "active_trade_anchor_gate",
            "PASS",
            "no single decision artifact, check not applicable",
        )
    action = str(decision.get("action", "")).upper()
    if action not in ("BUY", "SELL", "INCREASE", "REDUCE"):
        return _make_check(
            "active_trade_anchor_gate",
            "PASS",
            f"action={action} is not an active trade action, check not applicable",
        )
    blocked_by = decision.get("blocked_by", [])
    if blocked_by:
        return _make_check(
            "active_trade_anchor_gate",
            "PASS",
            f"active action {action} is blocked, gate not violated",
        )
    anchor_diag = ds_artifacts.get("evidence_anchor_diagnostics", {})
    if isinstance(anchor_diag, dict):
        has_anchors = anchor_diag.get("has_evidence_anchors", True)
        if has_anchors is False:
            return _make_check(
                "active_trade_anchor_gate",
                "FAIL",
                f"active {action} decision allowed without evidence anchors",
                {"action": action, "has_evidence_anchors": False},
            )
    rationale_anchor = decision.get("rationale_anchor")
    if not rationale_anchor:
        eg_items = eg.get("items", {})
        if not eg_items:
            return _make_check(
                "active_trade_anchor_gate",
                "FAIL",
                f"active {action} decision allowed without evidence anchors or rationale_anchor",
                {"action": action, "rationale_anchor": None, "evidence_graph_items": 0},
            )
    return _make_check(
        "active_trade_anchor_gate",
        "PASS",
        f"active {action} decision has evidence anchors",
    )


def _check_missing_data_disclosed(fa: dict, fr: dict) -> dict:
    fa_artifacts = fa.get("artifacts", {}) if isinstance(fa, dict) else {}
    missing_indicators: list[str] = []

    for key in ("evidence_gap_diagnostics", "missing_inputs", "limitations"):
        val = fa_artifacts.get(key)
        if val:
            missing_indicators.append(key)

    warnings = fa.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        missing_indicators.append("warnings")

    if not missing_indicators:
        return _make_check(
            "missing_data_disclosed",
            "PASS",
            "no missing data indicators found in fund_analysis output",
        )

    fr_text = _flatten_report_text(fr)
    fr_structured = fr.get("workflow_summary", {}) if isinstance(fr, dict) else {}
    has_disclosure = False

    for field in ("evidence_status", "limitations", "missing_data"):
        if field in fr_structured:
            has_disclosure = True
        for section in fr.get("user_facing_sections", []):
            if isinstance(section, dict) and section.get("id") == field:
                has_disclosure = True

    disclosure_phrases = ("missing", "incomplete", "partial", "limitation", "gap", "缺失", "不完整", "部分", "限制", "证据不足")
    for phrase in disclosure_phrases:
        if phrase in fr_text.lower() or phrase in fr_text:
            has_disclosure = True
            break

    if not has_disclosure:
        return _make_check(
            "missing_data_disclosed",
            "WARN",
            f"fund_analysis has missing data indicators ({missing_indicators}) but final_report does not clearly disclose",
            {"missing_indicators": missing_indicators},
        )
    return _make_check(
        "missing_data_disclosed",
        "PASS",
        "missing data indicators are disclosed in final_report",
    )


def _check_no_broker_execution(fa: dict, eg: dict, ds: dict | None, fr: dict) -> dict:
    all_found: list[dict] = []
    for label, data in (("fund_analysis", fa), ("evidence_graph", eg), ("final_report", fr)):
        found = _find_extended_forbidden(data)
        if found:
            all_found.append({"location": label, "fields": found})
    if ds is not None:
        found = _find_extended_forbidden(ds)
        if found:
            all_found.append({"location": "decision_support", "fields": found})

    if all_found:
        return _make_check(
            "no_broker_execution",
            "FAIL",
            f"broker/order execution fields found: {all_found}",
            {"violations": all_found},
        )
    return _make_check(
        "no_broker_execution",
        "PASS",
        "no broker/order execution fields found in any workflow output",
    )


def _check_action_boundary_present(fr: dict, ds: dict | None) -> dict:
    if not isinstance(fr, dict):
        return _make_check(
            "action_boundary_present",
            "FAIL",
            "final_report is missing or not a dict",
        )
    sections = fr.get("user_facing_sections", [])
    boundary_section = None
    for section in sections:
        if isinstance(section, dict) and section.get("id") == "action_boundary":
            boundary_section = section
            break

    if boundary_section is None:
        return _make_check(
            "action_boundary_present",
            "FAIL",
            "final_report missing action_boundary section",
        )

    bullets = boundary_section.get("bullets", [])
    text = " ".join(str(b) for b in bullets)

    has_no_broker = any(kw in text for kw in ("不执行券商下单", "does not execute broker", "no broker execution", "not execute", "不执行"))
    if not has_no_broker:
        return _make_check(
            "action_boundary_present",
            "WARN",
            "action_boundary section exists but may not clearly state no broker execution",
            {"bullets_count": len(bullets)},
        )

    summary = fr.get("workflow_summary", {}) if isinstance(fr, dict) else {}
    decision_status = str(summary.get("decision_status", ""))

    if decision_status == "NO_FORMAL_DECISION":
        has_no_formal = any(kw in text for kw in ("no formal decision", "未进行正式决策", "no formal", "report-only", "仅报告"))
        if not has_no_formal:
            return _make_check(
                "action_boundary_present",
                "WARN",
                "report-only action_boundary may not clarify no formal decision was evaluated",
            )
    elif decision_status in ("FORMAL_DECISION", "BLOCKED", "DOWNGRADED"):
        has_audit = any(kw in text for kw in ("audit", "审计", "not execution", "不是执行", "advisory", "建议"))
        if not has_audit:
            return _make_check(
                "action_boundary_present",
                "WARN",
                "formal flow action_boundary may not clarify decision is audit artifact, not execution",
            )

    return _make_check(
        "action_boundary_present",
        "PASS",
        "action_boundary section present with appropriate disclaimers",
    )


def _check_zh_direct_answer_present(fr: dict, language: str | None) -> dict:
    fr_lang = fr.get("language", "") if isinstance(fr, dict) else ""
    effective_lang = language or fr_lang
    is_zh = False
    if effective_lang:
        from .report_status import normalize_language
        is_zh = normalize_language(effective_lang) == "zh-CN"

    if not is_zh:
        return _make_check(
            "zh_direct_answer_present",
            "PASS",
            "language is not zh-CN, check not applicable",
        )

    sections = fr.get("user_facing_sections", []) if isinstance(fr, dict) else []
    direct_answer = None
    for section in sections:
        if isinstance(section, dict) and section.get("id") == "direct_answer":
            direct_answer = section
            break

    if direct_answer is None:
        return _make_check(
            "zh_direct_answer_present",
            "FAIL",
            "zh-CN final_report missing direct_answer section",
        )

    chinese_summary = fr.get("chinese_summary", {}) if isinstance(fr, dict) else {}
    if not chinese_summary:
        return _make_check(
            "zh_direct_answer_present",
            "FAIL",
            "zh-CN final_report missing chinese_summary",
        )

    cs_bullets = chinese_summary.get("bullets", []) if isinstance(chinese_summary, dict) else []
    cs_text = " ".join(str(b) for b in cs_bullets)
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", cs_text))

    if not has_chinese:
        return _make_check(
            "zh_direct_answer_present",
            "FAIL",
            "zh-CN final_report chinese_summary does not contain Chinese text",
        )

    da_bullets = direct_answer.get("bullets", []) if isinstance(direct_answer, dict) else []
    da_text = " ".join(str(b) for b in da_bullets)
    da_has_chinese = bool(re.search(r"[\u4e00-\u9fff]", da_text))

    if not da_has_chinese:
        return _make_check(
            "zh_direct_answer_present",
            "WARN",
            "zh-CN direct_answer section does not contain Chinese text",
        )

    return _make_check(
        "zh_direct_answer_present",
        "PASS",
        "zh-CN final_report has direct_answer and chinese_summary with Chinese text",
    )


def _check_suggested_rebalance_analysis_only(fa: dict, fr: dict) -> dict:
    fa_artifacts = fa.get("artifacts", {}) if isinstance(fa, dict) else {}
    rebalance_plan = fa_artifacts.get("suggested_rebalance_plan")
    if not rebalance_plan:
        return _make_check(
            "suggested_rebalance_analysis_only",
            "PASS",
            "no suggested_rebalance_plan in fund_analysis output",
        )

    safety = fr.get("safety_boundary", {}) if isinstance(fr, dict) else {}
    analysis_only = safety.get("analysis_only_sections", [])
    if "suggested_rebalance_plan" not in analysis_only:
        return _make_check(
            "suggested_rebalance_analysis_only",
            "WARN",
            "suggested_rebalance_plan present but not listed in safety_boundary.analysis_only_sections",
        )

    sections = fr.get("user_facing_sections", []) if isinstance(fr, dict) else []
    boundary_text = ""
    for section in sections:
        if isinstance(section, dict) and section.get("id") == "action_boundary":
            boundary_text = " ".join(str(b) for b in section.get("bullets", []))
            break

    has_analysis_only = any(kw in boundary_text for kw in ("analysis-only", "仅分析", "分析用途", "not execution", "advisory only"))
    if not has_analysis_only:
        return _make_check(
            "suggested_rebalance_analysis_only",
            "WARN",
            "suggested_rebalance_plan present but action_boundary may not clarify it is analysis-only",
        )

    broker_in_rebalance = _find_extended_forbidden(rebalance_plan)
    if broker_in_rebalance:
        return _make_check(
            "suggested_rebalance_analysis_only",
            "FAIL",
            f"suggested_rebalance_plan contains broker/order execution fields: {broker_in_rebalance}",
            {"found_fields": broker_in_rebalance},
        )

    return _make_check(
        "suggested_rebalance_analysis_only",
        "PASS",
        "suggested_rebalance_plan is analysis-only and disclosed in action_boundary",
    )


def _check_provider_data_provenance_present(fa: dict, eg: dict, fr: dict, eb: dict) -> dict:
    provider_metadata = fa.get("provider_metadata") or eg.get("provider_metadata")
    if not provider_metadata:
        return _make_check(
            "provider_data_provenance_present",
            "PASS",
            "no provider_metadata in workflow inputs, check not applicable",
        )

    if not isinstance(provider_metadata, dict):
        return _make_check(
            "provider_data_provenance_present",
            "WARN",
            "provider_metadata is not a dict",
        )

    items = provider_metadata.get("items", [])
    if not items:
        return _make_check(
            "provider_data_provenance_present",
            "PASS",
            "provider_metadata has no items",
        )

    missing_provenance: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("provider", item.get("name", "unknown"))
        has_source = bool(item.get("source") or item.get("provenance") or item.get("as_of"))
        if not has_source:
            missing_provenance.append(name)

    requires_provenance = eb.get("requires_provider_provenance", False)
    if missing_provenance:
        status = "FAIL" if requires_provenance else "WARN"
        return _make_check(
            "provider_data_provenance_present",
            status,
            f"provider items missing source/provenance/as_of: {missing_provenance}",
            {"missing_provenance": missing_provenance},
        )

    return _make_check(
        "provider_data_provenance_present",
        "PASS",
        "all provider items have source/provenance/as_of metadata",
    )


def _find_extended_forbidden(data: Any) -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in _EXTENDED_FORBIDDEN_FIELDS:
                found.append(key)
            if isinstance(value, (dict, list)):
                found.extend(_find_extended_forbidden(value))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                found.extend(_find_extended_forbidden(item))
    return found


def _flatten_report_text(fr: dict) -> str:
    parts: list[str] = []
    for section in fr.get("user_facing_sections", []):
        if isinstance(section, dict):
            for bullet in section.get("bullets", []):
                parts.append(str(bullet))
    chinese = fr.get("chinese_summary", {})
    if isinstance(chinese, dict):
        for bullet in chinese.get("bullets", []):
            parts.append(str(bullet))
    return " ".join(parts)
