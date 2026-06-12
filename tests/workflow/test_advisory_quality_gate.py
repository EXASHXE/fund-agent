"""Tests for advisory quality gate — v1.6.2."""

from __future__ import annotations

import pytest

from src.tools.workflow.advisory_quality_gate import evaluate_advisory_quality_gate


def _make_passing_report(**overrides) -> dict:
    report = {
        "workflow_summary": {
            "report_status": "OK",
            "decision_status": "NO_FORMAL_DECISION",
        },
        "safety_boundary": {
            "no_broker_execution": True,
            "formal_decision_source": "none",
            "analysis_only_sections": [],
        },
        "user_facing_sections": [
            {
                "id": "direct_answer",
                "title": "Direct Answer",
                "bullets": ["建议持有", "风险可控"],
            },
            {
                "id": "action_boundary",
                "title": "Action Boundary",
                "bullets": [
                    "fund-agent does not execute broker orders",
                    "no formal decision was evaluated",
                ],
            },
        ],
        "chinese_summary": {
            "bullets": ["组合分析完成", "建议持有当前仓位"],
        },
        "language": "zh-CN",
    }
    report.update(overrides)
    return report


def _make_passing_fa() -> dict:
    return {
        "status": "OK",
        "artifacts": {},
        "evidence_items": [],
    }


def _gate(**kwargs) -> dict:
    defaults = {
        "fund_analysis_output": _make_passing_fa(),
        "evidence_graph": None,
        "decision_support_output": None,
        "final_report": _make_passing_report(),
        "expected_behavior": None,
        "language": "zh-CN",
    }
    defaults.update(kwargs)
    return evaluate_advisory_quality_gate(**defaults)


class TestFundAnalysisNoFormalDecision:
    def test_pass_when_clean(self):
        result = _gate()
        check = _find_check(result, "fund_analysis_no_formal_decision")
        assert check["status"] == "PASS"

    def test_fail_when_execution_ledger_present(self):
        fa = _make_passing_fa()
        fa["artifacts"]["execution_ledger"] = {"ledger_summary": {}}
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "fund_analysis_no_formal_decision")
        assert check["status"] == "FAIL"

    def test_fail_when_decision_present(self):
        fa = _make_passing_fa()
        fa["artifacts"]["decision"] = {"action": "BUY"}
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "fund_analysis_no_formal_decision")
        assert check["status"] == "FAIL"

    def test_fail_when_broker_field_in_fa(self):
        fa = _make_passing_fa()
        fa["artifacts"]["nested"] = {"broker_order_id": "abc123"}
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "fund_analysis_no_formal_decision")
        assert check["status"] == "FAIL"


class TestFormalSourceBoundary:
    def test_pass_when_consistent(self):
        result = _gate()
        check = _find_check(result, "formal_source_boundary")
        assert check["status"] == "PASS"

    def test_fail_when_formal_source_not_decision_support(self):
        report = _make_passing_report()
        report["workflow_summary"]["decision_status"] = "FORMAL_DECISION"
        report["safety_boundary"]["formal_decision_source"] = "fund_analysis"
        result = _gate(final_report=report)
        check = _find_check(result, "formal_source_boundary")
        assert check["status"] == "FAIL"

    def test_fail_when_ds_none_but_decision_status_not_no_formal(self):
        report = _make_passing_report()
        report["workflow_summary"]["decision_status"] = "FORMAL_DECISION"
        result = _gate(decision_support_output=None, final_report=report)
        check = _find_check(result, "formal_source_boundary")
        assert check["status"] == "FAIL"


class TestReportOnlyNoDecisionSupport:
    def test_pass_when_report_only(self):
        eb = {"decision_support_called": False}
        result = _gate(expected_behavior=eb)
        check = _find_check(result, "report_only_no_decision_support")
        assert check["status"] == "PASS"

    def test_fail_when_ds_output_present(self):
        eb = {"decision_support_called": False}
        ds = {"artifacts": {"decision": {"action": "HOLD"}}}
        result = _gate(decision_support_output=ds, expected_behavior=eb)
        check = _find_check(result, "report_only_no_decision_support")
        assert check["status"] == "FAIL"

    def test_fail_when_decision_status_not_no_formal(self):
        eb = {"decision_support_called": False}
        report = _make_passing_report()
        report["workflow_summary"]["decision_status"] = "BLOCKED"
        result = _gate(final_report=report, expected_behavior=eb)
        check = _find_check(result, "report_only_no_decision_support")
        assert check["status"] == "FAIL"

    def test_fail_when_formal_source_not_none(self):
        eb = {"decision_support_called": False}
        report = _make_passing_report()
        report["safety_boundary"]["formal_decision_source"] = "decision_support"
        result = _gate(final_report=report, expected_behavior=eb)
        check = _find_check(result, "report_only_no_decision_support")
        assert check["status"] == "FAIL"

    def test_not_applicable_when_ds_called_true(self):
        eb = {"decision_support_called": True}
        result = _gate(expected_behavior=eb)
        check = _find_check(result, "report_only_no_decision_support")
        assert check["status"] == "PASS"

    def test_not_applicable_when_expected_behavior_missing(self):
        result = _gate(expected_behavior=None)
        check = _find_check(result, "report_only_no_decision_support")
        assert check["status"] == "PASS"

    def test_not_applicable_when_key_missing(self):
        result = _gate(expected_behavior={})
        check = _find_check(result, "report_only_no_decision_support")
        assert check["status"] == "PASS"


class TestDecisionSupportRequiredArtifacts:
    def test_pass_when_no_ds(self):
        result = _gate()
        check = _find_check(result, "decision_support_required_artifacts")
        assert check["status"] == "PASS"

    def test_pass_when_artifacts_complete(self):
        ds = {
            "artifacts": {
                "execution_ledger": {"ledger_summary": {}},
                "evidence_anchor_diagnostics": {},
                "risk_constraint_conflicts": {},
                "decision": {"action": "HOLD"},
            },
        }
        result = _gate(decision_support_output=ds)
        check = _find_check(result, "decision_support_required_artifacts")
        assert check["status"] == "PASS"

    def test_fail_when_missing_required_artifacts(self):
        ds = {"artifacts": {"decision": {"action": "HOLD"}}}
        result = _gate(decision_support_output=ds)
        check = _find_check(result, "decision_support_required_artifacts")
        assert check["status"] == "FAIL"

    def test_fail_when_active_decision_missing_execution_amount(self):
        ds = {
            "artifacts": {
                "execution_ledger": {"ledger_summary": {}},
                "evidence_anchor_diagnostics": {},
                "risk_constraint_conflicts": {},
                "decision": {"action": "BUY"},
            },
        }
        result = _gate(decision_support_output=ds)
        check = _find_check(result, "decision_support_required_artifacts")
        assert check["status"] == "FAIL"


class TestActiveTradeAnchorGate:
    def test_pass_when_no_ds(self):
        result = _gate()
        check = _find_check(result, "active_trade_anchor_gate")
        assert check["status"] == "PASS"

    def test_pass_when_passive_action(self):
        ds = {"artifacts": {"decision": {"action": "HOLD"}}}
        result = _gate(decision_support_output=ds)
        check = _find_check(result, "active_trade_anchor_gate")
        assert check["status"] == "PASS"

    def test_pass_when_active_with_anchors(self):
        ds = {
            "artifacts": {
                "decision": {
                    "action": "BUY",
                    "rationale_anchor": "evidence_abc",
                    "execution_amount": 10000,
                },
                "evidence_anchor_diagnostics": {"has_evidence_anchors": True},
            },
        }
        eg = {"items": {"ev1": {}}}
        result = _gate(decision_support_output=ds, evidence_graph=eg)
        check = _find_check(result, "active_trade_anchor_gate")
        assert check["status"] == "PASS"

    def test_fail_when_active_buy_no_anchors(self):
        ds = {
            "artifacts": {
                "decision": {"action": "BUY"},
                "evidence_anchor_diagnostics": {"has_evidence_anchors": False},
            },
        }
        result = _gate(decision_support_output=ds)
        check = _find_check(result, "active_trade_anchor_gate")
        assert check["status"] == "FAIL"

    def test_pass_when_active_but_blocked(self):
        ds = {
            "artifacts": {
                "decision": {"action": "BUY", "blocked_by": ["insufficient_evidence"]},
                "evidence_anchor_diagnostics": {"has_evidence_anchors": False},
            },
        }
        result = _gate(decision_support_output=ds)
        check = _find_check(result, "active_trade_anchor_gate")
        assert check["status"] == "PASS"


class TestMissingDataDisclosed:
    def test_pass_when_no_missing_data(self):
        result = _gate()
        check = _find_check(result, "missing_data_disclosed")
        assert check["status"] == "PASS"

    def test_warn_when_missing_data_not_disclosed(self):
        fa = _make_passing_fa()
        fa["artifacts"]["evidence_gap_diagnostics"] = {"missing_nav": True}
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "missing_data_disclosed")
        assert check["status"] == "WARN"

    def test_pass_when_missing_data_disclosed(self):
        fa = _make_passing_fa()
        fa["artifacts"]["evidence_gap_diagnostics"] = {"missing_nav": True}
        report = _make_passing_report()
        report["user_facing_sections"].append({
            "id": "evidence_status",
            "bullets": ["部分数据缺失"],
        })
        result = _gate(fund_analysis_output=fa, final_report=report)
        check = _find_check(result, "missing_data_disclosed")
        assert check["status"] == "PASS"


class TestNoBrokerExecution:
    def test_pass_when_clean(self):
        result = _gate()
        check = _find_check(result, "no_broker_execution")
        assert check["status"] == "PASS"

    def test_fail_when_broker_field_in_fa(self):
        fa = _make_passing_fa()
        fa["broker_order_id"] = "abc"
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "no_broker_execution")
        assert check["status"] == "FAIL"

    def test_fail_when_nested_broker_field(self):
        report = _make_passing_report()
        report["nested"] = {"deep": {"order_status": "filled"}}
        result = _gate(final_report=report)
        check = _find_check(result, "no_broker_execution")
        assert check["status"] == "FAIL"

    def test_fail_when_broker_field_in_ds(self):
        ds = {"artifacts": {"execution_ledger": {"filled_quantity": 100}}}
        result = _gate(decision_support_output=ds)
        check = _find_check(result, "no_broker_execution")
        assert check["status"] == "FAIL"

    def test_fail_when_extended_fields_in_list(self):
        fa = _make_passing_fa()
        fa["items"] = [{"actual_fill": 100}]
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "no_broker_execution")
        assert check["status"] == "FAIL"


class TestActionBoundaryPresent:
    def test_pass_when_present_with_disclaimers(self):
        result = _gate()
        check = _find_check(result, "action_boundary_present")
        assert check["status"] == "PASS"

    def test_fail_when_missing(self):
        report = _make_passing_report()
        report["user_facing_sections"] = []
        result = _gate(final_report=report)
        check = _find_check(result, "action_boundary_present")
        assert check["status"] == "FAIL"

    def test_warn_when_no_broker_disclaimer(self):
        report = _make_passing_report()
        for section in report["user_facing_sections"]:
            if section.get("id") == "action_boundary":
                section["bullets"] = ["some generic text"]
        result = _gate(final_report=report)
        check = _find_check(result, "action_boundary_present")
        assert check["status"] == "WARN"


class TestZhDirectAnswerPresent:
    def test_pass_when_zh_complete(self):
        result = _gate(language="zh-CN")
        check = _find_check(result, "zh_direct_answer_present")
        assert check["status"] == "PASS"

    def test_pass_when_not_zh(self):
        result = _gate(language="en")
        check = _find_check(result, "zh_direct_answer_present")
        assert check["status"] == "PASS"

    def test_fail_when_zh_missing_chinese_summary(self):
        report = _make_passing_report()
        report["chinese_summary"] = {}
        result = _gate(final_report=report, language="zh-CN")
        check = _find_check(result, "zh_direct_answer_present")
        assert check["status"] == "FAIL"

    def test_fail_when_zh_chinese_summary_no_chinese(self):
        report = _make_passing_report()
        report["chinese_summary"] = {"bullets": ["no Chinese text here"]}
        result = _gate(final_report=report, language="zh-CN")
        check = _find_check(result, "zh_direct_answer_present")
        assert check["status"] == "FAIL"

    def test_fail_when_zh_missing_direct_answer(self):
        report = _make_passing_report()
        report["user_facing_sections"] = [
            {
                "id": "action_boundary",
                "bullets": ["fund-agent does not execute broker orders"],
            },
        ]
        result = _gate(final_report=report, language="zh-CN")
        check = _find_check(result, "zh_direct_answer_present")
        assert check["status"] == "FAIL"


class TestSuggestedRebalanceAnalysisOnly:
    def test_pass_when_no_rebalance_plan(self):
        result = _gate()
        check = _find_check(result, "suggested_rebalance_analysis_only")
        assert check["status"] == "PASS"

    def test_pass_when_analysis_only_disclosed(self):
        fa = _make_passing_fa()
        fa["artifacts"]["suggested_rebalance_plan"] = {"actions": ["reduce equity"]}
        report = _make_passing_report()
        report["safety_boundary"]["analysis_only_sections"] = ["suggested_rebalance_plan"]
        for section in report["user_facing_sections"]:
            if section.get("id") == "action_boundary":
                section["bullets"].append("suggested_rebalance_plan is analysis-only, not execution")
        result = _gate(fund_analysis_output=fa, final_report=report)
        check = _find_check(result, "suggested_rebalance_analysis_only")
        assert check["status"] == "PASS"

    def test_warn_when_not_in_analysis_only_sections(self):
        fa = _make_passing_fa()
        fa["artifacts"]["suggested_rebalance_plan"] = {"actions": ["reduce equity"]}
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "suggested_rebalance_analysis_only")
        assert check["status"] == "WARN"

    def test_fail_when_rebalance_has_broker_fields(self):
        fa = _make_passing_fa()
        fa["artifacts"]["suggested_rebalance_plan"] = {"broker_order_id": "abc"}
        report = _make_passing_report()
        report["safety_boundary"]["analysis_only_sections"] = ["suggested_rebalance_plan"]
        for section in report["user_facing_sections"]:
            if section.get("id") == "action_boundary":
                section["bullets"].append("suggested_rebalance_plan is analysis-only")
        result = _gate(fund_analysis_output=fa, final_report=report)
        check = _find_check(result, "suggested_rebalance_analysis_only")
        assert check["status"] == "FAIL"


class TestProviderDataProvenancePresent:
    def test_pass_when_no_provider_metadata(self):
        result = _gate()
        check = _find_check(result, "provider_data_provenance_present")
        assert check["status"] == "PASS"

    def test_pass_when_provenance_present(self):
        fa = _make_passing_fa()
        fa["provider_metadata"] = {
            "items": [
                {"provider": "akshare", "source": "akshare", "as_of": "2025-01-01"},
            ],
        }
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "provider_data_provenance_present")
        assert check["status"] == "PASS"

    def test_warn_when_provenance_missing(self):
        fa = _make_passing_fa()
        fa["provider_metadata"] = {
            "items": [
                {"provider": "akshare"},
            ],
        }
        result = _gate(fund_analysis_output=fa)
        check = _find_check(result, "provider_data_provenance_present")
        assert check["status"] == "WARN"

    def test_fail_when_provenance_required(self):
        fa = _make_passing_fa()
        fa["provider_metadata"] = {
            "items": [
                {"provider": "akshare"},
            ],
        }
        eb = {"requires_provider_provenance": True}
        result = _gate(fund_analysis_output=fa, expected_behavior=eb)
        check = _find_check(result, "provider_data_provenance_present")
        assert check["status"] == "FAIL"


class TestGateOverall:
    def test_passed_true_when_no_fails(self):
        result = _gate()
        assert result["passed"] is True
        assert result["summary"]["fail_count"] == 0

    def test_passed_false_when_any_fail(self):
        fa = _make_passing_fa()
        fa["artifacts"]["execution_ledger"] = {}
        result = _gate(fund_analysis_output=fa)
        assert result["passed"] is False
        assert result["summary"]["fail_count"] >= 1

    def test_summary_counts(self):
        result = _gate()
        total = result["summary"]["pass_count"] + result["summary"]["warn_count"] + result["summary"]["fail_count"]
        assert total == 11


def _find_check(result: dict, check_id: str) -> dict:
    for check in result["checks"]:
        if check["id"] == check_id:
            return check
    pytest.fail(f"check {check_id} not found")
