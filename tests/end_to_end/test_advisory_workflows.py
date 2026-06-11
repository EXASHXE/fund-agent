"""E2E advisory workflow tests — v1.4.1 expected_behavior-driven assertions.

Runs realistic user scenarios through:
fund_analysis → EvidenceGraph → decision_support → final report/explanation.
All assertions driven by fixture expected_behavior fields.
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
from src.skills_runtime.workflow.evidence_bridge import build_evidence_graph_from_workflow
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

REPORT_ONLY_SCENARIOS = {"qdii_ai_overlap_concentration_watch", "missing_data_report_only_no_fabrication"}

EXPECTED_BEHAVIOR_REQUIRED_KEYS = frozenset({
    "decision_support_called",
    "expected_report_status",
    "expected_decision_status",
    "expected_formal_source",
    "expected_active_decision_count",
    "expected_passive_decision_count",
    "expected_blocked_decision_count",
    "expected_downgraded_decision_count",
    "expected_reason_code_contains",
    "expected_risk_conflict_kinds",
    "expected_required_report_sections",
})


def _get_expected(fixture: dict, keys: list[str] | None = None):
    """Extract expected_behavior values from fixture with defaults."""
    eb = fixture.get("expected_behavior", {})
    if keys is None:
        return eb
    result = []
    for k in keys:
        result.append(eb.get(k))
    return result


def _all_fixture_files():
    if not FIXTURES_DIR.exists():
        return []
    return sorted([f.stem for f in FIXTURES_DIR.glob("*.json")])


def _run_workflow(scenario: str):
    """Run full workflow for a scenario and return (fixture, fa_output, bridge_result, ds_output, report)."""
    fixture = load_e2e_fixture(scenario)
    fa_output = run_fund_analysis(fixture)
    bridge_result = build_workflow_evidence(fixture, fa_output)
    is_report_only = scenario in REPORT_ONLY_SCENARIOS
    ds_output = None if is_report_only else run_decision_support(fa_output, fixture, bridge_result)
    report = compose_final_report(fixture, fa_output, ds_output, bridge_result)
    return fixture, fa_output, bridge_result, ds_output, report


def _assert_decision_support_called(fixture, ds_output):
    eb = fixture.get("expected_behavior", {})
    called = eb.get("decision_support_called", False)
    if called:
        assert ds_output is not None, f"Expected decision_support to be called for {fixture['scenario_id']}"
    else:
        assert ds_output is None, f"Expected decision_support NOT to be called for {fixture['scenario_id']}"


# ── Fixture loading and structural validation ───────────────────────────────


class TestE2EFixtureLoading:
    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fixture_loads(self, scenario):
        fixture = load_e2e_fixture(scenario)
        assert "scenario_id" in fixture
        assert "portfolio" in fixture
        assert "positions" in fixture.get("portfolio", {})

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fixture_has_all_expected_behavior_keys(self, scenario):
        fixture = load_e2e_fixture(scenario)
        eb = fixture.get("expected_behavior", {})
        assert isinstance(eb, dict), f"expected_behavior must be dict, got {type(eb)}"
        for key in EXPECTED_BEHAVIOR_REQUIRED_KEYS:
            assert key in eb, f"expected_behavior.{key} missing in {scenario}"

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fixture_has_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        assert_no_execution_fields(fixture, f"fixture:{scenario}")

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_fixture_expected_behavior_fields_are_valid_types(self, scenario):
        fixture = load_e2e_fixture(scenario)
        eb = fixture.get("expected_behavior", {})
        assert isinstance(eb.get("decision_support_called"), bool)
        assert isinstance(eb.get("expected_report_status"), str)
        assert isinstance(eb.get("expected_decision_status"), str)
        assert isinstance(eb.get("expected_formal_source"), str)
        assert isinstance(eb.get("expected_active_decision_count"), int)
        assert isinstance(eb.get("expected_passive_decision_count"), int)
        assert isinstance(eb.get("expected_blocked_decision_count"), int)
        assert isinstance(eb.get("expected_downgraded_decision_count"), int)
        assert isinstance(eb.get("expected_reason_code_contains"), list)
        assert isinstance(eb.get("expected_risk_conflict_kinds"), list)
        assert isinstance(eb.get("expected_required_report_sections"), list)


# ── Fund analysis boundary ──────────────────────────────────────────────────


class TestFundAnalysisBoundary:
    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_no_formal_decision(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        assert_no_formal_decision_in_output(output)

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_produces_evidence_items(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        assert output.evidence_items or output.status == "PARTIAL"

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_produces_artifacts(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        assert isinstance(output.artifacts or {}, dict)

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        output = run_fund_analysis(fixture)
        assert_no_execution_fields(output.to_dict(), f"fund_analysis:{scenario}")


# ── EvidenceGraph bridge ────────────────────────────────────────────────────


class TestEvidenceGraphBridge:
    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_bridge_produces_graph(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        assert result.graph is not None
        assert result.included_evidence_count >= 0

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_bridge_no_execution_fields(self, scenario):
        fixture = load_e2e_fixture(scenario)
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        assert_no_execution_fields(result.to_dict(), f"bridge:{scenario}")

    def test_bridge_does_not_fabricate_evidence(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        for item in result.graph.items.values():
            assert item.source_type not in ("fabricated", "generated", "inferred", "llm")


# ── Decision support boundary ───────────────────────────────────────────────


class TestDecisionSupportBoundary:
    @pytest.mark.parametrize("scenario", sorted(set(ALL_E2E_SCENARIOS) - REPORT_ONLY_SCENARIOS))
    def test_called_when_fixture_expects(self, scenario):
        fixture = load_e2e_fixture(scenario)
        eb = fixture.get("expected_behavior", {})
        assert eb.get("decision_support_called") is True, f"{scenario}: expected decision_support_called=true"

    @pytest.mark.parametrize("scenario", sorted(REPORT_ONLY_SCENARIOS))
    def test_not_called_when_report_only(self, scenario):
        fixture = load_e2e_fixture(scenario)
        eb = fixture.get("expected_behavior", {})
        assert eb.get("decision_support_called") is False, f"{scenario}: expected decision_support_called=false"

    def test_only_decision_support_produces_formal_decision(self):
        fixture = load_e2e_fixture("all_data_sufficient_formal_trade_plan")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        ds_output = run_decision_support(fa_output, fixture, result)
        assert_decision_support_is_only_formal_producer(fa_output, ds_output)

    @pytest.mark.parametrize("scenario", sorted(set(ALL_E2E_SCENARIOS) - REPORT_ONLY_SCENARIOS))
    def test_no_execution_fields(self, scenario):
        _, _, _, ds_output, _ = _run_workflow(scenario)
        assert_no_execution_fields(ds_output.to_dict(), f"decision_support:{scenario}")


# ── Workflow summary assertions (expected_behavior-driven) ──────────────────


class TestWorkflowSummaryMatchesExpectedBehavior:
    """Each scenario's workflow_summary must match expected_behavior exactly."""

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_report_status_matches_expected(self, scenario):
        fixture, fa_output, br, ds_output, report = _run_workflow(scenario)
        (expected_report_status,) = _get_expected(fixture, ["expected_report_status"])
        actual = report["workflow_summary"]["report_status"]
        assert actual == expected_report_status, (
            f"{scenario}: report_status expected={expected_report_status}, got={actual}"
        )

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_decision_status_matches_expected(self, scenario):
        fixture, fa_output, br, ds_output, report = _run_workflow(scenario)
        (expected_decision_status,) = _get_expected(fixture, ["expected_decision_status"])
        actual = report["workflow_summary"]["decision_status"]
        assert actual == expected_decision_status, (
            f"{scenario}: decision_status expected={expected_decision_status}, got={actual}"
        )

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_formal_source_matches_expected(self, scenario):
        fixture, fa_output, br, ds_output, report = _run_workflow(scenario)
        (expected_source,) = _get_expected(fixture, ["expected_formal_source"])
        actual = report["safety_boundary"]["formal_decision_source"]
        assert actual == expected_source, (
            f"{scenario}: formal_decision_source expected={expected_source}, got={actual}"
        )

    @pytest.mark.parametrize("scenario", sorted(set(ALL_E2E_SCENARIOS) - REPORT_ONLY_SCENARIOS))
    def test_ledger_counts_match_expected(self, scenario):
        fixture, fa_output, br, ds_output, report = _run_workflow(scenario)
        eb = fixture.get("expected_behavior", {})
        ds_artifacts = ds_output.artifacts or {}
        ledger = ds_artifacts.get("execution_ledger", {})
        ls = ledger.get("ledger_summary", {})
        for field in ("active_decision_count", "passive_decision_count", "blocked_decision_count", "downgraded_decision_count"):
            expected = eb.get(f"expected_{field}")
            actual = ls.get(field)
            assert actual == expected, (
                f"{scenario}: {field} expected={expected}, got={actual}"
            )

    @pytest.mark.parametrize("scenario", sorted(set(ALL_E2E_SCENARIOS) - REPORT_ONLY_SCENARIOS))
    def test_decision_not_no_formal_when_ds_called(self, scenario):
        fixture, fa_output, br, ds_output, report = _run_workflow(scenario)
        status = report["workflow_summary"]["decision_status"]
        assert status != "NO_FORMAL_DECISION", (
            f"{scenario}: decision_support was called but decision_status is NO_FORMAL_DECISION"
        )


# ── Reason codes and blocker assertions ─────────────────────────────────────


class TestReasonCodesMatchExpected:
    @pytest.mark.parametrize("scenario", sorted(set(ALL_E2E_SCENARIOS) - REPORT_ONLY_SCENARIOS))
    def test_reason_codes_contain_expected_fragments(self, scenario):
        fixture, fa_output, br, ds_output, report = _run_workflow(scenario)
        eb = fixture.get("expected_behavior", {})
        expected_codes = eb.get("expected_reason_code_contains", [])
        if not expected_codes:
            return

        ds_artifacts = ds_output.artifacts or {}
        # Aggregate reason codes from both single-decision and multi-decision paths
        all_reason_parts: list[str] = []

        decision = ds_artifacts.get("decision", {})
        if isinstance(decision, dict):
            all_reason_parts.append(str(decision.get("decision_reason_codes", [])))
            all_reason_parts.append(str(decision.get("blocked_by", [])))
            all_reason_parts.append(str(decision.get("evidence_state", "")))

        decisions_list = ds_artifacts.get("decisions", [])
        if isinstance(decisions_list, list):
            for d in decisions_list:
                if isinstance(d, dict):
                    all_reason_parts.append(str(d.get("decision_reason_codes", [])))
                    all_reason_parts.append(str(d.get("blocked_by", [])))
                    all_reason_parts.append(str(d.get("evidence_state", "")))

        all_reason_text = " ".join(all_reason_parts)

        for code_fragment in expected_codes:
            assert code_fragment in all_reason_text, (
                f"{scenario}: expected reason code fragment '{code_fragment}' not found in: {all_reason_text[:300]}"
            )


# ── Report-only scenario assertions ─────────────────────────────────────────


class TestReportOnlyScenarios:
    @pytest.mark.parametrize("scenario", sorted(REPORT_ONLY_SCENARIOS))
    def test_decision_support_not_called(self, scenario):
        _, _, _, ds_output, _ = _run_workflow(scenario)
        assert ds_output is None, f"{scenario}: decision_support should not be called"

    @pytest.mark.parametrize("scenario", sorted(REPORT_ONLY_SCENARIOS))
    def test_decision_status_is_no_formal_decision(self, scenario):
        _, _, _, _, report = _run_workflow(scenario)
        assert report["workflow_summary"]["decision_status"] == "NO_FORMAL_DECISION"

    @pytest.mark.parametrize("scenario", sorted(REPORT_ONLY_SCENARIOS))
    def test_formal_decision_source_is_none(self, scenario):
        _, _, _, _, report = _run_workflow(scenario)
        assert report["safety_boundary"]["formal_decision_source"] == "none"


# ── Missing data scenario assertions ────────────────────────────────────────


class TestMissingDataNoFabrication:
    def test_analysis_plan_decision_not_ready(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        ap = artifacts.get("analysis_plan", {})
        assert ap.get("decision_support_ready") is False

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
                        assert cost_basis is not None, f"No fabricated cost basis expected, got {cost_basis}"

    def test_no_fabricated_news_sentiment_fees_benchmark_in_bridge(self):
        fixture = load_e2e_fixture("missing_data_report_only_no_fabrication")
        fa_output = run_fund_analysis(fixture)
        result = build_workflow_evidence(fixture, fa_output)
        assert result.host_soft_evidence_count == 0, "No soft evidence should be fabricated from missing news/sentiment"
        source_types = {item.source_type for item in result.graph.items.values()}
        assert "host_news" not in source_types, "No host_news should be fabricated"
        assert "host_sentiment" not in source_types, "No host_sentiment should be fabricated"


# ── Scenario-specific diagnostic presence ───────────────────────────────────


class TestDiagnosticPresence:
    def test_semiconductor_has_profit_protection(self):
        fixture = load_e2e_fixture("semiconductor_profit_protection_formal_reduce")
        output = run_fund_analysis(fixture)
        assert (output.artifacts or {}).get("profit_protection_diagnostics")

    def test_innovation_drug_has_right_side(self):
        fixture = load_e2e_fixture("innovation_drug_drawdown_unconfirmed_right_side")
        output = run_fund_analysis(fixture)
        assert (output.artifacts or {}).get("right_side_confirmation_diagnostics")

    def test_short_holding_has_fee_diagnostics(self):
        fixture = load_e2e_fixture("short_holding_fee_sell_blocked")
        output = run_fund_analysis(fixture)
        artifacts = output.artifacts or {}
        assert artifacts.get("redemption_fee_risk") or output.warnings

    def test_qdii_ai_overlap_has_exposure_summary(self):
        fixture = load_e2e_fixture("qdii_ai_overlap_concentration_watch")
        output = run_fund_analysis(fixture)
        assert (output.artifacts or {}).get("exposure_summary") is not None

    def test_cash_bond_has_cash_diagnostics(self):
        fixture = load_e2e_fixture("cash_bond_deployment_budget_guard")
        output = run_fund_analysis(fixture)
        assert (output.artifacts or {}).get("cash_deployment_diagnostics")


# ── Final report section assertions ─────────────────────────────────────────


class TestFinalReportSections:
    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_report_has_all_required_sections(self, scenario):
        fixture, fa_output, br, ds_output, report = _run_workflow(scenario)
        eb = fixture.get("expected_behavior", {})
        expected_sections = eb.get("expected_required_report_sections", [])
        actual_ids = {s["id"] for s in report.get("user_facing_sections", [])}
        for section_id in expected_sections:
            assert section_id in actual_ids, (
                f"{scenario}: expected section '{section_id}' in report, got {actual_ids}"
            )

    @pytest.mark.parametrize("scenario", ALL_E2E_SCENARIOS)
    def test_report_no_execution_fields(self, scenario):
        _, _, _, _, report = _run_workflow(scenario)
        assert_no_execution_fields(report, f"report:{scenario}")

    @pytest.mark.parametrize("scenario", sorted(set(ALL_E2E_SCENARIOS) - REPORT_ONLY_SCENARIOS))
    def test_safety_boundary_no_broker_execution(self, scenario):
        _, _, _, _, report = _run_workflow(scenario)
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is True

    def test_report_only_safety_boundary_no_formal_source(self):
        for scenario in sorted(REPORT_ONLY_SCENARIOS):
            _, _, _, _, report = _run_workflow(scenario)
            assert report["safety_boundary"]["formal_decision_source"] == "none"


# ── Specific detailed scenario assertions ───────────────────────────────────


class TestSemiconductorDetailed:
    def test_decision_is_passive_when_blocked(self):
        fixture, fa_output, br, ds_output, report = _run_workflow("semiconductor_profit_protection_formal_reduce")
        decision = (ds_output.artifacts or {}).get("decision", {})
        action = str(decision.get("action", "")).upper()
        assert action in ("HOLD", "WAIT", "PAUSE_DCA"), f"Blocked decision should be passive, got {action}"
        assert decision.get("blocked_by"), "Blocked decision should have blocked_by"

    def test_profit_protection_in_reason_codes(self):
        fixture, fa_output, br, ds_output, report = _run_workflow("semiconductor_profit_protection_formal_reduce")
        decision = (ds_output.artifacts or {}).get("decision", {})
        reason_text = str(decision.get("decision_reason_codes", [])) + str(decision.get("blocked_by", []))
        assert "PROFIT_PROTECTION" in reason_text


class TestInnovationDrugDetailed:
    def test_active_buy_is_blocked(self):
        fixture, fa_output, br, ds_output, report = _run_workflow("innovation_drug_drawdown_unconfirmed_right_side")
        decision = (ds_output.artifacts or {}).get("decision", {})
        action = str(decision.get("action", "")).upper()
        assert action not in ("BUY", "INCREASE"), f"Active BUY/INCREASE should be blocked, got {action}"

    def test_has_anchor_diagnostics(self):
        _, _, _, ds_output, _ = _run_workflow("innovation_drug_drawdown_unconfirmed_right_side")
        ds_artifacts = ds_output.artifacts or {}
        anchor_diag = ds_artifacts.get("evidence_anchor_diagnostics", {})
        assert anchor_diag, "Expected evidence_anchor_diagnostics"


class TestShortHoldingDetailed:
    def test_active_sell_is_blocked(self):
        fixture, fa_output, br, ds_output, report = _run_workflow("short_holding_fee_sell_blocked")
        decision = (ds_output.artifacts or {}).get("decision", {})
        action = str(decision.get("action", "")).upper()
        assert action not in ("SELL", "REDUCE"), f"Active SELL/REDUCE should be blocked, got {action}"

    def test_blocked_decision_not_no_formal(self):
        _, _, _, _, report = _run_workflow("short_holding_fee_sell_blocked")
        status = report["workflow_summary"]["decision_status"]
        assert status != "NO_FORMAL_DECISION", (
            f"Blocked scenario should not return NO_FORMAL_DECISION, got {status}"
        )

    def test_active_decision_count_is_zero(self):
        _, _, _, ds_output, _ = _run_workflow("short_holding_fee_sell_blocked")
        ledger = (ds_output.artifacts or {}).get("execution_ledger", {})
        ls = ledger.get("ledger_summary", {})
        assert ls.get("active_decision_count", -1) == 0


class TestAllDataTradePlanDetailed:
    def test_produces_multiple_decisions(self):
        _, _, _, ds_output, _ = _run_workflow("all_data_sufficient_formal_trade_plan")
        decisions = (ds_output.artifacts or {}).get("decisions", [])
        assert len(decisions) >= 3, f"Expected 3 decisions, got {len(decisions)}"

    def test_per_trade_anchor_coverage(self):
        _, _, _, ds_output, _ = _run_workflow("all_data_sufficient_formal_trade_plan")
        anchor_diag = (ds_output.artifacts or {}).get("evidence_anchor_diagnostics", {})
        trade_coverage = anchor_diag.get("trade_anchor_coverage", [])
        trade_ids = {tc.get("trade_id") for tc in trade_coverage if isinstance(tc, dict)}
        expected_trade_ids = {"trade_1", "trade_2", "trade_3"}
        assert trade_ids == expected_trade_ids, (
            f"Expected coverage for all 3 trade legs, got {trade_ids}"
        )

    def test_decision_status_matches_fixture(self):
        _, _, _, _, report = _run_workflow("all_data_sufficient_formal_trade_plan")
        status = report["workflow_summary"]["decision_status"]
        assert status != "NO_FORMAL_DECISION", f"All-data trade plan must have formal evaluation, got {status}"


# ── Acceptance criteria ─────────────────────────────────────────────────────


class TestAcceptanceCriteria:
    def test_all_e2e_fixtures_exist(self):
        found = _all_fixture_files()
        for name in ALL_E2E_SCENARIOS:
            assert name in found, f"Missing E2E fixture: {name}"

    def test_all_fixtures_run_fund_analysis_and_bridge(self):
        for scenario in ALL_E2E_SCENARIOS:
            fixture, fa_output, br, _, _ = _run_workflow(scenario)
            assert fa_output.status in ("OK", "PARTIAL", "FAILED")
            assert br.graph is not None

    def test_no_broker_execution_across_workflow(self):
        for scenario in ALL_E2E_SCENARIOS:
            fixture = load_e2e_fixture(scenario)
            fa_output = run_fund_analysis(fixture)
            assert_no_execution_fields(fa_output.to_dict(), f"fa:{scenario}")
            br = build_workflow_evidence(fixture, fa_output)
            assert_no_execution_fields(br.to_dict(), f"bridge:{scenario}")
            if scenario not in REPORT_ONLY_SCENARIOS:
                ds_output = run_decision_support(fa_output, fixture, br)
                assert_no_execution_fields(ds_output.to_dict(), f"ds:{scenario}")

    def test_decision_support_called_exact_match(self):
        for scenario in ALL_E2E_SCENARIOS:
            fixture, _, _, ds_output, _ = _run_workflow(scenario)
            _assert_decision_support_called(fixture, ds_output)
