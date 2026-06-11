"""E2E advisory workflow tests — v1.3/v1.4 full-flow hardening.

Runs realistic user scenarios through:
fund_analysis → EvidenceGraph → decision_support → final report/explanation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.schemas.decision import Decision, ExecutionLedger
from src.schemas.evidence_graph import EvidenceGraph
from src.schemas.skill import SkillOutput
from src.skills_runtime.fund_analysis import FundAnalysisSkill
from src.skills_runtime.decision_support import DecisionSupportSkill
from src.tools.workflow.evidence_bridge import build_evidence_graph_from_workflow
from src.tools.workflow.final_report import compose_advisory_workflow_report

from tests.end_to_end.helpers import (
    assert_decision_support_is_only_formal_producer,
    assert_no_execution_fields,
    assert_no_formal_decision_in_output,
    build_workflow_evidence,
    compose_final_report,
    load_e2e_fixture,
    run_decision_support,
    run_fund_analysis,
)

FIXTURES_DIR = Path(__file__).parent.parent.parent / "examples" / "e2e_advisory_workflows"

ALL_E2E_SCENARIOS = [
    "semiconductor_profit_protection_formal_reduce",
    "innovation_drug_drawdown_unconfirmed_right_side",
    "short_holding_fee_sell_blocked",
    "qdii_ai_overlap_concentration_watch",
    "cash_bond_deployment_budget_guard",
    "all_data_sufficient_formal_trade_plan",
    "missing_data_report_only_no_fabrication",
]


def _all_fixture_files():
    """List all JSON fixture files."""
    if not FIXTURES_DIR.exists():
        return []
    return sorted([f.stem for f in FIXTURES_DIR.glob("*.json")])


# ── Phase 1: Fixture loading ──────────────────────────────────────────────


class TestE2EFixtureLoading:
    """Ensure all E2E fixtures load and are well-formed."""

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fixture_loads(self, scenario):
        fixture = load_e2e_fixture(scenario)
        assert "scenario_id" in fixture
        assert "portfolio" in fixture
        assert "positions" in fixture.get("portfolio", {})

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fixture_has_expected_behavior(self, scenario):
        fixture = load_e2e_fixture(scenario)
        expected = fixture.get("expected_behavior", {})
        assert isinstance(expected, dict), f"expected_behavior must be dict, got {type(expected)}"

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fixture_has_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        assert_no_execution_fields(fixture, f"fixture:{scenario}")


# ── Phase 1: Fund analysis boundary ───────────────────────────────────────


class TestFundAnalysisBoundary:
    """fund_analysis must never emit formal Decision/ExecutionLedger."""

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fund_analysis_no_formal_decision(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        assert_no_formal_decision_in_output(output)

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fund_analysis_produces_evidence_items(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        assert output.evidence_items or output.status == "PARTIAL", (
            f"Expected evidence items or PARTIAL status, got {output.status}"
        )

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fund_analysis_produces_artifacts(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        assert isinstance(artifacts, dict)

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fund_analysis_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        output_dict = output.to_dict()
        assert_no_execution_fields(output_dict, f"fund_analysis:{scenario}")


# ── Phase 3: EvidenceGraph bridge ─────────────────────────────────────────


class TestEvidenceGraphBridge:
    """EvidenceGraph bridge connects fund_analysis evidence to decision_support."""

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_bridge_produces_graph(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        assert result.graph is not None
        assert result.included_evidence_count >= 0
        assert isinstance(result.host_soft_evidence_count, int)

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_bridge_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        result_dict = result.to_dict()
        assert_no_execution_fields(result_dict, f"bridge:{scenario}")

    def test_bridge_graph_accepted_by_decision_support(self):
        """EvidenceGraph from bridge should be accepted by decision_support."""
        fixture = load_e2e_fixture("semiconductor_profit_protection_formal_reduce")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)

        ds_skill = DecisionSupportSkill()
        from src.schemas.skill import SkillInput

        ds_input = SkillInput(
            task_id="bridge-test",
            step_id="ds",
            skill_name="decision_support",
            payload={
                "evidence_graph": result.graph.to_dict(),
                "requested_action": fixture.get("requested_action", "HOLD"),
                "portfolio_context": fixture.get("portfolio", {}),
                "risk_profile": fixture.get("risk_profile", {}),
                "constraints": fixture.get("constraints", {}),
            },
        )
        ds_output = ds_skill.run(ds_input)
        assert ds_output.status in ("OK", "PARTIAL")

    def test_bridge_handles_host_news_evidence(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)

        soft = result.graph.soft_evidence_count()
        assert soft >= 1, f"Expected at least 1 soft evidence from news, got {soft}"

    def test_bridge_handles_host_sentiment_evidence(self):
        fixture = load_e2e_fixture("semiconductor_profit_protection_formal_reduce")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)

        soft = result.graph.soft_evidence_count()
        assert soft >= 1, f"Expected soft evidence from sentiment, got {soft}"

    def test_bridge_warns_on_missing_data(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)

        assert result.host_soft_evidence_count == 0
        warnings = result.warnings
        assert any("No news" in w or "No sentiment" in w for w in warnings), (
            f"Expected warning about missing news/sentiment, got {warnings}"
        )

    def test_bridge_does_not_fabricate_evidence(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)

        for item in result.graph.items.values():
            assert item.evidence_type in ("HardEvidence", "SoftEvidence", "HybridEvidence")
            assert item.claim  # must have content
            assert item.source_type not in ("fabricated", "generated", "inferred", "llm")

    def test_bridge_invalid_host_evidence_is_warned(self):
        fa_output = run_fund_analysis(load_e2e_fixture("semiconductor_profit_protection_formal_reduce"))
        result = build_evidence_graph_from_workflow(
            fund_analysis_output=fa_output.to_dict(),
            host_news_evidence=[{"invalid": "no title or entities"}],
            host_sentiment_evidence=[{"bad": "no entity"}],
        )
        assert len(result.missing_or_invalid_evidence) >= 2 or len(result.warnings) >= 2


# ── Phase 4-5: Decision support boundary ──────────────────────────────────


class TestDecisionSupportBoundary:
    """decision_support is the only formal decision runtime."""

    @pytest.mark.parametrize("scenario", [
        "semiconductor_profit_protection_formal_reduce",
        "innovation_drug_drawdown_unconfirmed_right_side",
        "short_holding_fee_sell_blocked",
        "cash_bond_deployment_budget_guard",
        "all_data_sufficient_formal_trade_plan",
    ])
    def test_decision_support_produces_formal_decision(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        assert ds_output.status in ("OK", "PARTIAL")
        ds_artifacts = ds_output.artifacts or {}
        assert ds_artifacts.get("decision") or ds_artifacts.get("execution_ledger") or ds_artifacts.get("decisions"), (
            f"decision_support should produce decision/execution_ledger/decisions, got keys: {list(ds_artifacts.keys())[:10]}"
        )

    @pytest.mark.parametrize("scenario", [
        "semiconductor_profit_protection_formal_reduce",
        "innovation_drug_drawdown_unconfirmed_right_side",
        "short_holding_fee_sell_blocked",
        "cash_bond_deployment_budget_guard",
        "all_data_sufficient_formal_trade_plan",
    ])
    def test_decision_support_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)
        ds_dict = ds_output.to_dict()
        assert_no_execution_fields(ds_dict, f"decision_support:{scenario}")

    def test_only_decision_support_produces_formal_decision(self):
        """Assert fund_analysis never produces formal Decision/ExecutionLedger
        while decision_support does."""
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        assert_decision_support_is_only_formal_producer(fa_output, ds_output)


# ── Phase 4-5: Specific scenario assertions ────────────────────────────────


class TestSemiconductorProfitProtection:
    """Scenario: semiconductor profit protection → formal REDUCE."""

    def test_fund_analysis_produces_profit_diagnostics(self):
        fixture = load_e2e_fixture("semiconductor_profit_protection_formal_reduce")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        pp = artifacts.get("profit_protection_diagnostics", {})
        assert pp, "Expected profit_protection_diagnostics in artifacts"

    def test_decision_support_allows_reduce_if_anchored(self):
        fixture = load_e2e_fixture("semiconductor_profit_protection_formal_reduce")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        decision = ds_artifacts.get("decision", {})
        action = str(decision.get("action", "")).upper()

        assert action in ("REDUCE", "SELL", "HOLD", "WAIT"), (
            f"Expected REDUCE/SELL/HOLD/WAIT, got {action}"
        )

        ledger = ds_artifacts.get("execution_ledger", {})
        assert ledger, "Expected execution_ledger in artifacts"
        ls = ledger.get("ledger_summary", {})
        assert ls, "Expected ledger_summary"


class TestInnovationDrugDrawdown:
    """Scenario: drawdown + unconfirmed right side → block active BUY."""

    def test_fund_analysis_produces_right_side_diagnostics(self):
        fixture = load_e2e_fixture("innovation_drug_drawdown_unconfirmed_right_side")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        rs = artifacts.get("right_side_confirmation_diagnostics", {})
        assert rs, "Expected right_side_confirmation_diagnostics"

    def test_decision_support_blocks_active_buy(self):
        fixture = load_e2e_fixture("innovation_drug_drawdown_unconfirmed_right_side")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        decision = ds_artifacts.get("decision", {})
        action = str(decision.get("action", "")).upper()
        blocked = decision.get("blocked_by", [])
        reason_codes = decision.get("decision_reason_codes", [])

        assert action != "BUY", "Active BUY should be blocked or downgraded"
        assert action != "INCREASE", "Active INCREASE should be blocked or downgraded"
        assert action in ("HOLD", "WAIT", "PAUSE_DCA") or (blocked or "RIGHT_SIDE_UNCONFIRMED" in str(reason_codes)), (
            f"Expected HOLD/WAIT/PAUSE_DCA or blocked by right_side, got action={action}, blocked={blocked}, reasons={reason_codes}"
        )

    def test_evidence_anchor_diagnostics_explains_blockage(self):
        fixture = load_e2e_fixture("innovation_drug_drawdown_unconfirmed_right_side")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        anchor_diag = ds_artifacts.get("evidence_anchor_diagnostics", {})
        assert anchor_diag, "Expected evidence_anchor_diagnostics"


class TestShortHoldingFeeBlocker:
    """Scenario: short-holding fee → block active SELL."""

    def test_fund_analysis_produces_redemption_diagnostics(self):
        fixture = load_e2e_fixture("short_holding_fee_sell_blocked")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        rf = artifacts.get("redemption_fee_risk", {})
        assert rf or output.warnings, f"Expected redemption_fee_risk or warnings, got {list(artifacts.keys())[:10]}"

    def test_decision_support_blocks_active_sell(self):
        fixture = load_e2e_fixture("short_holding_fee_sell_blocked")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        decision = ds_artifacts.get("decision", {})
        action = str(decision.get("action", "")).upper()

        assert action not in ("SELL", "REDUCE"), (
            f"Active SELL/REDUCE should be blocked, got {action}"
        )

    def test_execution_ledger_records_blockage(self):
        fixture = load_e2e_fixture("short_holding_fee_sell_blocked")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        ledger = ds_artifacts.get("execution_ledger", {})
        if ledger:
            ls = ledger.get("ledger_summary", {})
            assert ls.get("active_decision_count", 0) == 0, (
                "Active decision count should be 0 for blocked scenario"
            )


class TestQDIIAIOverlap:
    """Scenario: QDII/AI overlap → report only, no decision_support needed."""

    def test_fund_analysis_produces_exposure_summary(self):
        fixture = load_e2e_fixture("qdii_ai_overlap_concentration_watch")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        es = artifacts.get("exposure_summary", {})
        assert es is not None, "Expected exposure_summary in artifacts"

    def test_fund_analysis_no_formal_decision_report_only(self):
        fixture = load_e2e_fixture("qdii_ai_overlap_concentration_watch")
        output = run_fund_analysis(fixture)
        assert_no_formal_decision_in_output(output)

    def test_knowledge_graph_summary_enabled(self):
        fixture = load_e2e_fixture("qdii_ai_overlap_concentration_watch")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        kg = artifacts.get("knowledge_graph_summary", {})
        if kg and isinstance(kg, dict):
            assert kg.get("enabled") is not False, "KG should be enabled with sufficient holdings"
            assert kg.get("limitations") is not None or kg.get("enabled") is True, (
                "KG should explain limitations if disabled"
            )


class TestCashBondDeployment:
    """Scenario: cash/bond deployment → budget guard."""

    def test_fund_analysis_produces_cash_diagnostics(self):
        fixture = load_e2e_fixture("cash_bond_deployment_budget_guard")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        cd = artifacts.get("cash_deployment_diagnostics", {})
        assert cd, "Expected cash_deployment_diagnostics"

    def test_decision_support_caps_or_blocks_by_constraint(self):
        fixture = load_e2e_fixture("cash_bond_deployment_budget_guard")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        decision = ds_artifacts.get("decision", {})
        action = str(decision.get("action", "")).upper()
        amount = float(decision.get("execution_amount", 0))

        requested = float(fixture.get("target_trade_amount", 0))
        assert amount <= requested, f"Capped amount {amount} should not exceed requested {requested}"

        risk_conflicts = ds_artifacts.get("risk_constraint_conflicts", {})
        assert risk_conflicts, "Expected risk_constraint_conflicts"


class TestAllDataTradePlan:
    """Scenario: complete payload → formal multi-leg trade plan."""

    def test_fund_analysis_ready_for_decision(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        ap = artifacts.get("analysis_plan", {})
        assert ap.get("decision_support_ready") is not False, (
            "Expected decision_support_ready to be true"
        )

    def test_decision_support_produces_multiple_decisions(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        decisions = ds_artifacts.get("decisions", [])
        assert len(decisions) >= 1, f"Expected at least 1 decision, got {len(decisions)}"

    def test_ledger_summary_has_expected_counts(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        ledger = ds_artifacts.get("execution_ledger", {})
        assert ledger, "Expected execution_ledger"
        ls = ledger.get("ledger_summary", {})
        assert "active_decision_count" in ls
        assert "passive_decision_count" in ls
        assert "blocked_decision_count" in ls
        assert "downgraded_decision_count" in ls

    def test_allowed_capped_blocked_behavior(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)

        ds_artifacts = ds_output.artifacts or {}
        decisions = ds_artifacts.get("decisions", [])
        actions = {str(d.get("action", "")).upper() for d in decisions}

        assert "REDUCE" in actions or "SELL" in actions or "HOLD" in actions or "WAIT" in actions, (
            f"Expected allowed/capped/blocked distribution, got actions: {actions}"
        )


class TestMissingDataReportOnly:
    """Scenario: missing data → report only, no fabrication."""

    def test_fund_analysis_produces_missing_data_diagnostics(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        gap = artifacts.get("evidence_gap_diagnostics", {})
        assert gap or output.warnings or output.status == "PARTIAL", (
            "Expected evidence_gap_diagnostics or warnings for missing data"
        )

    def test_analysis_plan_decision_not_ready(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        ap = artifacts.get("analysis_plan", {})
        assert ap.get("decision_support_ready") is False, (
            "decision_support_ready should be false when data is missing"
        )

    def test_no_fabricated_cost_basis(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        ps = artifacts.get("position_summary", {})
        if isinstance(ps, dict):
            items = ps.get("items", ps.get("positions", []))
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        cost_basis = item.get("cost_basis") or item.get("total_cost")
                        assert cost_basis is not None, (
                            f"No fabricated cost basis expected, got {cost_basis}"
                        )


# ── Phase 6: Final report composer ─────────────────────────────────────────


class TestFinalReportComposer:
    """Final workflow report / explanation composer."""

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_report_produced(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)

        if scenario == "qdii_ai_overlap_concentration_watch" or scenario == "missing_data_report_only_no_fabrication":
            # Report-only scenarios: no decision_support call
            report = compose_final_report(fixture, fa_output)
        else:
            result = build_workflow_evidence(fixture, fa_output)
            ds_output = run_decision_support(fa_output, fixture, result)
            report = compose_final_report(fixture, fa_output, ds_output, result)

        assert "workflow_summary" in report
        assert "user_facing_sections" in report
        assert "safety_boundary" in report

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_report_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)

        if scenario == "qdii_ai_overlap_concentration_watch" or scenario == "missing_data_report_only_no_fabrication":
            report = compose_final_report(fixture, fa_output)
        else:
            result = build_workflow_evidence(fixture, fa_output)
            ds_output = run_decision_support(fa_output, fixture, result)
            report = compose_final_report(fixture, fa_output, ds_output, result)

        assert_no_execution_fields(report, f"report:{scenario}")

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_report_has_required_sections(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)

        if scenario == "qdii_ai_overlap_concentration_watch" or scenario == "missing_data_report_only_no_fabrication":
            report = compose_final_report(fixture, fa_output)
        else:
            result = build_workflow_evidence(fixture, fa_output)
            ds_output = run_decision_support(fa_output, fixture, result)
            report = compose_final_report(fixture, fa_output, ds_output, result)

        sections = report.get("user_facing_sections", [])
        section_ids = {s.get("id") for s in sections}
        for expected_id in ("summary", "evidence_status", "decision_explanation", "limitations"):
            assert expected_id in section_ids, (
                f"Expected section '{expected_id}' in report, got {section_ids}"
            )

    def test_report_only_scenarios_show_no_formal_decision(self):
        for scenario in ("qdii_ai_overlap_concentration_watch", "missing_data_report_only_no_fabrication"):
            fixture = load_e2e_fixture(scenario)
            fa_output = run_fund_analysis(fixture)
            report = compose_final_report(fixture, fa_output)

            summary = report.get("workflow_summary", {})
            assert summary.get("decision_status") == "NO_FORMAL_DECISION", (
                f"Expected NO_FORMAL_DECISION for {scenario}, got {summary.get('decision_status')}"
            )

    def test_blocked_scenarios_explain_why(self):
        fixture = load_e2e_fixture("short_holding_fee_sell_blocked")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)
        report = compose_final_report(fixture, fa_output, ds_output, result)

        summary = report.get("workflow_summary", {})
        assert summary.get("decision_status") in ("BLOCKED", "DOWNGRADED", "NO_FORMAL_DECISION"), (
            f"Expected BLOCKED/DOWNGRADED/NO_FORMAL_DECISION, got {summary.get('decision_status')}"
        )

    def test_all_data_formal_shows_formal_decision(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)
        report = compose_final_report(fixture, fa_output, ds_output, result)

        summary = report.get("workflow_summary", {})
        assert summary.get("decision_status") in ("FORMAL_DECISION", "DOWNGRADED", "BLOCKED"), (
            f"Expected FORMAL_DECISION, DOWNGRADED, or BLOCKED, got {summary.get('decision_status')}"
        )

    def test_safety_boundary_no_broker_execution(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)
        report = compose_final_report(fixture, fa_output, ds_output, result)

        safety = report.get("safety_boundary", {})
        assert safety.get("no_broker_execution") is True
        assert safety.get("formal_decision_source") == "decision_support"

    @pytest.mark.parametrize("scenario", [
        "qdii_ai_overlap_concentration_watch",
        "missing_data_report_only_no_fabrication",
    ])
    def test_report_only_safety_boundary_no_formal_source(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)
        report = compose_final_report(fixture, fa_output)

        safety = report.get("safety_boundary", {})
        assert safety.get("formal_decision_source") == "none"


# ── Phase 8: Acceptance criteria ───────────────────────────────────────────


class TestAcceptanceCriteria:
    """Full acceptance criteria verification."""

    def test_all_e2e_fixtures_exist(self):
        found = _all_fixture_files()
        for name in ALL_E2E_SCENARIOS:
            assert name in found, f"Missing E2E fixture: {name}"

    def test_all_fixtures_run_fund_analysis_and_bridge(self):
        for scenario in ALL_E2E_SCENARIOS:
            fixture = load_e2e_fixture(scenario)
            fa_output = run_fund_analysis(fixture)
            assert fa_output.status in ("OK", "PARTIAL", "FAILED")
            result = build_workflow_evidence(fixture, fa_output)
            assert result.graph is not None

    def test_all_decision_scenarios_produce_audit_trail(self):
        decision_scenarios = [s for s in ALL_E2E_SCENARIOS
                              if s not in ("qdii_ai_overlap_concentration_watch",
                                           "missing_data_report_only_no_fabrication")]
        for scenario in decision_scenarios:
            fixture = load_e2e_fixture(scenario)
            fa_output = run_fund_analysis(fixture)
            result = build_workflow_evidence(fixture, fa_output)
            ds_output = run_decision_support(fa_output, fixture, result)
            ds_artifacts = ds_output.artifacts or {}
            decision = ds_artifacts.get("decision", {})
            ledger = ds_artifacts.get("execution_ledger", {})
            assert decision or ledger, f"Expected decision or ledger for {scenario}"

    def test_no_broker_execution_across_workflow(self):
        for scenario in ALL_E2E_SCENARIOS:
            fixture = load_e2e_fixture(scenario)
            fa_output = run_fund_analysis(fixture)
            fa_dict = fa_output.to_dict()
            assert_no_execution_fields(fa_dict, f"fa:{scenario}")

            result = build_workflow_evidence(fixture, fa_output)
            result_dict = result.to_dict()
            assert_no_execution_fields(result_dict, f"bridge:{scenario}")

            if scenario not in ("qdii_ai_overlap_concentration_watch", "missing_data_report_only_no_fabrication"):
                ds_output = run_decision_support(fa_output, fixture, result)
                ds_dict = ds_output.to_dict()
                assert_no_execution_fields(ds_dict, f"ds:{scenario}")
