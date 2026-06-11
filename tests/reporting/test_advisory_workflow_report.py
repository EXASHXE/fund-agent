"""Tests for the advisory workflow final report composer."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

from src.schemas.evidence import EvidenceItem
from src.schemas.evidence_graph import EvidenceGraph
from src.tools.workflow.final_report import compose_advisory_workflow_report


def _make_fa_output(status="OK", decision_ready=True, with_quality_gate=True):
    """Make a minimal fund_analysis output dict."""
    artifacts = {
        "portfolio_summary": {"total_value": 300000, "position_count": 4},
        "analysis_plan": {
            "decision_support_ready": decision_ready,
            "blockers": [] if decision_ready else ["missing_data"],
        },
        "evidence_gap_diagnostics": {
            "missing_recent_news": False,
            "missing_sentiment": False,
        },
    }
    if with_quality_gate:
        artifacts["report_quality_gate"] = {
            "grade": "B",
            "can_publish_professional_report": True,
            "can_publish_limited_report": True,
        }
    return {
        "status": status,
        "artifacts": artifacts,
        "evidence_items": [],
        "warnings": [],
    }


def _make_ds_output(action="BUY", amount=10000, blocked_by=None):
    """Make a minimal decision_support output dict."""
    decision = {
        "action": action,
        "execution_amount": amount,
        "evidence_state": "ANCHORED" if not blocked_by else "DOWNGRADED",
        "blocked_by": blocked_by or [],
        "decision_reason_codes": ["EVIDENCE_AVAILABLE"],
        "trigger_conditions": ["test"],
        "invalidating_conditions": ["test"],
        "risk_budget": 0.05,
        "time_horizon": "medium_term",
        "rationale_anchor": ["ev-001"],
        "audit_trail": ["test audit"],
    }
    ledger = {
        "ledger_id": "test-ledger",
        "decisions": [decision],
        "ledger_summary": {
            "decision_count": 1,
            "active_decision_count": 1 if not blocked_by else 0,
            "passive_decision_count": 0 if not blocked_by else 1,
            "blocked_decision_count": 1 if blocked_by else 0,
            "downgraded_decision_count": 1 if blocked_by else 0,
        },
    }
    return {
        "status": "OK",
        "artifacts": {
            "decision": decision,
            "execution_ledger": ledger,
            "evidence_anchor_diagnostics": {
                "valid_anchor_refs": ["ev-001"],
                "invalid_anchor_refs": [],
                "missing_anchor_refs": [],
            },
            "risk_constraint_conflicts": {
                "summary": {
                    "has_blocking_conflict": bool(blocked_by),
                    "has_capping_conflict": False,
                }
            },
        },
    }


def _make_eg_diagnostics():
    """Make minimal evidence graph diagnostics."""
    return {
        "graph": {
            "items": {"ev-001": {"evidence_id": "ev-001", "evidence_type": "SoftEvidence"}},
            "edges": [],
            "stats": {"total": 1, "hard": 0, "soft": 1, "hybrid": 0, "conflicts": 0},
        },
        "included_evidence_count": 1,
        "host_soft_evidence_count": 0,
        "warnings": [],
        "missing_or_invalid_evidence": [],
    }


class TestReportSummary:
    """Workflow summary section tests."""

    def test_ok_with_decision(self):
        fa = _make_fa_output(status="OK", decision_ready=True)
        ds = _make_ds_output(action="BUY", amount=10000)
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
            evidence_graph_diagnostics=_make_eg_diagnostics(),
        )
        summary = report["workflow_summary"]
        assert summary["report_status"] == "OK"
        assert summary["decision_status"] == "FORMAL_DECISION"
        assert summary["decision_support_ready"] is True

    def test_partial_with_missing_data(self):
        fa = _make_fa_output(status="PARTIAL", decision_ready=False)
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        summary = report["workflow_summary"]
        assert summary["report_status"] == "PARTIAL"
        assert summary["decision_status"] == "NO_FORMAL_DECISION"
        assert summary["decision_support_ready"] is False

    def test_blocked_decision(self):
        fa = _make_fa_output(status="OK", decision_ready=True)
        ds = _make_ds_output(action="HOLD", amount=0, blocked_by=["evidence"])
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        summary = report["workflow_summary"]
        assert summary["decision_status"] in ("BLOCKED", "DOWNGRADED")

    def test_downgraded_decision(self):
        fa = _make_fa_output(status="OK", decision_ready=True)
        ds = _make_ds_output(action="HOLD", amount=0)
        # Make reasons indicate downgrade
        ds["artifacts"]["decision"]["decision_reason_codes"] = [
            "DOWNGRADED_ACTIVE_TO_HOLD", "PASSIVE_ACTION"
        ]
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        summary = report["workflow_summary"]
        assert summary["decision_status"] == "DOWNGRADED"

    def test_failed_status(self):
        fa = _make_fa_output(status="FAILED")
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        summary = report["workflow_summary"]
        assert summary["report_status"] == "FAILED"


class TestUserFacingSections:
    """User-facing section composition tests."""

    def test_has_all_required_sections(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
            evidence_graph_diagnostics=_make_eg_diagnostics(),
        )
        sections = report["user_facing_sections"]
        section_ids = {s["id"] for s in sections}
        assert "summary" in section_ids
        assert "evidence_status" in section_ids
        assert "decision_explanation" in section_ids
        assert "limitations" in section_ids

    def test_analysis_only_scenario_decision_section(self):
        fa = _make_fa_output(status="OK", decision_ready=False)
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        sections = report["user_facing_sections"]
        decision_section = next(s for s in sections if s["id"] == "decision_explanation")
        assert "analysis-only" in " ".join(str(b) for b in decision_section.get("bullets", [])).lower() or \
               "no formal" in " ".join(str(b) for b in decision_section.get("bullets", [])).lower()

    def test_evidence_section_shows_stats(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
            evidence_graph_diagnostics=_make_eg_diagnostics(),
        )
        evidence_section = next(s for s in report["user_facing_sections"] if s["id"] == "evidence_status")
        bullets_text = " ".join(evidence_section.get("bullets", []))
        assert "Total" in bullets_text or "total" in bullets_text.lower()
        assert "Hard" in bullets_text or "hard" in bullets_text.lower()
        assert "Soft" in bullets_text or "soft" in bullets_text.lower()

    def test_limitations_section_explicit(self):
        fa = _make_fa_output(status="OK", decision_ready=False, with_quality_gate=True)
        fa["artifacts"]["report_quality_gate"] = {
            "grade": "C",
            "can_publish_professional_report": False,
            "can_publish_limited_report": True,
        }
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        limitations = next(s for s in report["user_facing_sections"] if s["id"] == "limitations")
        bullets = limitations.get("bullets", [])
        assert any("Limited" in b or "limited" in b.lower() for b in bullets) or \
               any("cannot" in b.lower() for b in bullets)


class TestSafetyBoundary:
    """Safety boundary section tests."""

    def test_no_broker_execution_flag(self):
        fa = _make_fa_output()
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is True

    def test_formal_decision_source_decision_support(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        safety = report["safety_boundary"]
        assert safety["formal_decision_source"] == "decision_support"

    def test_formal_decision_source_none(self):
        fa = _make_fa_output(decision_ready=False)
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        safety = report["safety_boundary"]
        assert safety["formal_decision_source"] == "none"

    def test_analysis_only_sections_listed(self):
        fa = _make_fa_output()
        fa["artifacts"]["suggested_rebalance_plan"] = {"trades": []}
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        safety = report["safety_boundary"]
        assert "suggested_rebalance_plan" in safety["analysis_only_sections"]

    def test_no_fabricated_data(self):
        fa = _make_fa_output()
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        assert isinstance(report, dict)
        assert report["workflow_summary"]["scenario_id"] == "test"


class TestEdgeCases:
    """Edge case handling."""

    def test_all_none_inputs(self):
        report = compose_advisory_workflow_report(scenario_id="none_test")
        assert report["workflow_summary"]["scenario_id"] == "none_test"
        assert report["workflow_summary"]["report_status"] in ("PARTIAL", "FAILED")
        assert report["workflow_summary"]["decision_status"] == "NO_FORMAL_DECISION"
        assert len(report["user_facing_sections"]) >= 2

    def test_quality_gate_limits_professional_report(self):
        fa = _make_fa_output(decision_ready=False)
        fa["artifacts"]["report_quality_gate"] = {
            "grade": "D",
            "can_publish_professional_report": False,
            "can_publish_limited_report": True,
        }
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        assert report["workflow_summary"]["report_status"] == "PARTIAL"

    def test_missing_data_diagnostics_fed_through(self):
        fa = _make_fa_output(decision_ready=False)
        md = {"critical_missing": "transaction_history", "blockers": ["missing_cost_basis"]}
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            missing_data_diagnostics=md,
        )
        assert report["workflow_summary"]["report_status"] == "PARTIAL"

    def test_workflow_summary_json_serializable(self):
        import json
        fa = _make_fa_output()
        ds = _make_ds_output()
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
            evidence_graph_diagnostics=_make_eg_diagnostics(),
        )
        json_str = json.dumps(report)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["workflow_summary"]["scenario_id"] == "test"


# ── E. Recursive execution field detection ──────────────────────────────────


class TestSafetyBoundaryExecutionFieldDetection:
    """Recursive detection of forbidden broker/order execution fields."""

    def test_clean_output_no_forbidden_fields(self):
        fa = _make_fa_output()
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is True
        assert safety["forbidden_execution_fields_found"] == []

    def test_nested_forbidden_field_detected(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        ds["artifacts"]["execution_ledger"]["decisions"][0]["broker_order_id"] = "evil-001"
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is False
        found = safety["forbidden_execution_fields_found"]
        assert len(found) > 0
        assert any("broker_order_id" in f for f in found)

    def test_deeply_nested_forbidden_field_detected(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        ds["artifacts"]["decision"]["submitted_at"] = "2026-01-01T00:00:00Z"
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is False
        found = safety["forbidden_execution_fields_found"]
        assert any("submitted_at" in f for f in found)

    def test_multiple_forbidden_fields_all_detected(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        ds["artifacts"]["execution_ledger"]["decisions"][0]["order_id"] = "o-1"
        ds["artifacts"]["execution_ledger"]["decisions"][0]["broker"] = "bad-broker"
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is False
        found = safety["forbidden_execution_fields_found"]
        assert len(found) >= 2


# ── D. Decision status reporting ────────────────────────────────────────────


class TestDecisionStatusReporting:
    """Tests for correct decision_status in various scenarios."""

    def test_blocked_formal_decision_is_blocked_not_no_formal(self):
        fa = _make_fa_output(status="OK", decision_ready=True)
        ds = _make_ds_output(action="HOLD", amount=0, blocked_by=["redemption_fee_blocker"])
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        assert report["workflow_summary"]["decision_status"] in ("BLOCKED", "DOWNGRADED")

    def test_no_decision_support_output_is_no_formal(self):
        fa = _make_fa_output(status="OK", decision_ready=False)
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
        )
        assert report["workflow_summary"]["decision_status"] == "NO_FORMAL_DECISION"

    def test_active_formal_decision_is_formal(self):
        fa = _make_fa_output(status="OK", decision_ready=True)
        ds = _make_ds_output(action="BUY", amount=10000)
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        assert report["workflow_summary"]["decision_status"] == "FORMAL_DECISION"

    def test_blocked_decision_never_returns_no_formal(self):
        """Blocked decision with decision_support output must NOT return NO_FORMAL_DECISION."""
        fa = _make_fa_output(status="OK", decision_ready=False)
        ds = _make_ds_output(action="HOLD", amount=0, blocked_by=["evidence", "fee"])
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        assert report["workflow_summary"]["decision_status"] != "NO_FORMAL_DECISION", (
            f"Blocked decision should not return NO_FORMAL_DECISION, got {report['workflow_summary']['decision_status']}"
        )

    def test_formal_decision_cannot_be_blocked_unless_specifically_blocked(self):
        """A BUY with no blockers must return FORMAL_DECISION."""
        fa = _make_fa_output(status="OK", decision_ready=True)
        ds = _make_ds_output(action="BUY", amount=5000)
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        assert report["workflow_summary"]["decision_status"] == "FORMAL_DECISION"


# ── Extra: nested forbidden field in multi-level objects ─────────────────────


class TestSafetyBoundaryExtraNesting:
    """Extra tests for deeply nested forbidden execution fields."""

    def test_forbidden_field_5_levels_deep(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        # Create 5-level deep nested forbidden field
        ds["artifacts"]["execution_ledger"]["decisions"][0]["extra"] = {
            "nested1": {
                "nested2": {
                    "nested3": {
                        "exchange_order_id": "deeply-hidden-001"
                    }
                }
            }
        }
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is False
        found = safety["forbidden_execution_fields_found"]
        assert any("exchange_order_id" in f for f in found)

    def test_forbidden_fields_in_list_items(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        ds["artifacts"]["extra_list"] = [
            {"ok_field": "safe"},
            {"order_id": "list-item-bad"},
        ]
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is False

    def test_multiple_forbidden_fields_at_various_depths(self):
        fa = _make_fa_output()
        ds = _make_ds_output()
        ds["artifacts"]["broker"] = "top-level-broker"
        ds["artifacts"]["execution_ledger"]["decisions"][0]["order_status"] = "filled"
        report = compose_advisory_workflow_report(
            scenario_id="test",
            fund_analysis_output=fa,
            decision_support_output=ds,
        )
        safety = report["safety_boundary"]
        assert safety["no_broker_execution"] is False
        found = safety["forbidden_execution_fields_found"]
        assert len(found) >= 2
