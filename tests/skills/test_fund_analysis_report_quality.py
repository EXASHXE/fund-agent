"""Tests for FundAnalysisSkill report quality integration."""

from __future__ import annotations

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill


def _base_payload(**overrides):
    """Construct a base payload with all required sections."""
    payload = {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 200000,
            "cash_available": 20000,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Example Fund A",
                    "current_value": 80000,
                    "total_cost": 75000,
                    "shares": 50000,
                    "target_weight": 0.4,
                    "tags": ["equity", "growth"],
                },
                {
                    "fund_code": "220022",
                    "fund_name": "Example Fund B",
                    "current_value": 100000,
                    "total_cost": 95000,
                    "shares": 80000,
                    "target_weight": 0.5,
                    "tags": ["bond", "income"],
                },
            ],
        },
        "fund_profiles": {
            "110011": {
                "fund_code": "110011",
                "name": "Example Fund A",
                "fund_type": "equity",
                "manager": "Manager A",
                "benchmark": "CSI 300",
            },
            "220022": {
                "fund_code": "220022",
                "name": "Example Fund B",
                "fund_type": "bond",
                "manager": "Manager B",
                "benchmark": "ChinaBond Index",
            },
        },
        "nav_history": {
            "110011": [
                {"date": "2025-06-01", "nav": 1.40},
                {"date": "2026-06-01", "nav": 1.60},
            ],
            "220022": [
                {"date": "2025-06-01", "nav": 1.15},
                {"date": "2026-06-01", "nav": 1.25},
            ],
        },
        "holdings": {
            "110011": [
                {"name": "Stock A", "weight": 0.08, "industry": "tech"},
            ],
            "220022": [
                {"name": "Bond B", "weight": 0.05, "industry": "govt"},
            ],
        },
        "risk_profile": {
            "risk_level": "moderate",
            "max_single_fund_weight": 0.5,
            "max_theme_weight": 0.4,
            "max_trade_pct": 0.1,
            "liquidity_reserve_pct": 0.1,
            "short_term_trade_budget_pct": 0.1,
        },
        "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
    }
    payload.update(overrides)
    return payload


def _skill_input(payload, skill_name="fund_analysis"):
    return SkillInput(
        task_id="test-report-quality",
        step_id="fa-1",
        skill_name=skill_name,
        payload=payload,
    )


class TestReportQualityIntegration:
    def test_full_payload_produces_data_completeness(self):
        skill = FundAnalysisSkill()
        output = skill.run(_skill_input(_base_payload()))
        report = output.artifacts["fund_analysis_report"]
        assert "data_completeness" in report
        assert "analysis_coverage" in report
        assert "report_limitations" in report
        dc = report["data_completeness"]
        assert "score" in dc
        assert "grade" in dc

    def test_full_payload_produces_artifacts_with_quality(self):
        skill = FundAnalysisSkill()
        output = skill.run(_skill_input(_base_payload()))
        assert "data_completeness" in output.artifacts
        assert "analysis_coverage" in output.artifacts
        assert "report_limitations" in output.artifacts

    def test_missing_benchmark_does_not_fabricate_benchmark_summary(self):
        skill = FundAnalysisSkill()
        payload = _base_payload()
        output = skill.run(_skill_input(payload))
        report = output.artifacts["fund_analysis_report"]
        # No benchmark/benchmark_history provided
        benchmark = report.get("benchmark_summary")
        assert benchmark is None or benchmark == {}

    def test_provided_fee_schedule_creates_fee_summary(self):
        skill = FundAnalysisSkill()
        payload = _base_payload(
            fee_schedules={
                "110011": {"management_fee": 0.015, "custody_fee": 0.0025},
                "220022": {"management_fee": 0.01},
            },
        )
        output = skill.run(_skill_input(payload))
        report = output.artifacts["fund_analysis_report"]
        assert "fee_summary" in report
        fee = report["fee_summary"]
        assert fee is not None
        assert "funds_with_fees" in fee

    def test_provided_redemption_rules_creates_redemption_summary(self):
        skill = FundAnalysisSkill()
        payload = _base_payload(
            redemption_rules={
                "110011": {"lockup_days": 30, "redemption_fee_pct": 0.005},
            },
        )
        output = skill.run(_skill_input(payload))
        report = output.artifacts["fund_analysis_report"]
        assert "redemption_summary" in report
        red = report["redemption_summary"]
        assert red is not None
        assert "funds_with_rules" in red

    def test_provided_manager_profile_creates_manager_summary(self):
        skill = FundAnalysisSkill()
        payload = _base_payload(
            manager_profiles={
                "110011": {"manager_name": "Alice", "tenure_years": 5},
            },
        )
        output = skill.run(_skill_input(payload))
        report = output.artifacts["fund_analysis_report"]
        assert "manager_summary" in report
        mgr = report["manager_summary"]
        assert mgr is not None
        assert "funds_with_profiles" in mgr

    def test_peer_group_with_rank_produces_peer_summary(self):
        skill = FundAnalysisSkill()
        payload = _base_payload(
            peer_group={
                "110011": {"rank": 3, "total": 50, "category": "equity"},
            },
        )
        output = skill.run(_skill_input(payload))
        report = output.artifacts["fund_analysis_report"]
        assert report.get("peer_summary") is not None
        peer = report["peer_summary"]
        assert "rankings" in peer

    def test_peer_group_without_rank_does_not_invent_ranking(self):
        skill = FundAnalysisSkill()
        payload = _base_payload(
            peer_group={
                "110011": {"name": "Peers", "category": "equity"},
            },
        )
        output = skill.run(_skill_input(payload))
        report = output.artifacts["fund_analysis_report"]
        peer = report.get("peer_summary")
        if peer:
            assert "rankings" not in peer or peer["rankings"] == []

    def test_factor_exposures_produce_factor_summary(self):
        skill = FundAnalysisSkill()
        payload = _base_payload(
            factor_exposures={
                "value": {"110011": 0.3, "220022": 0.1},
                "momentum": {"110011": 0.5, "220022": 0.0},
            },
        )
        output = skill.run(_skill_input(payload))
        report = output.artifacts["fund_analysis_report"]
        assert report.get("factor_summary") is not None
        factor = report["factor_summary"]
        assert "factors" in factor

    def test_no_decision_or_execution_ledger_emitted(self):
        skill = FundAnalysisSkill()
        output = skill.run(_skill_input(_base_payload()))
        assert "decision" not in output.artifacts
        assert "execution_ledger" not in output.artifacts
        for item in output.evidence_items:
            ev_type = getattr(item, "evidence_type", "")
            assert ev_type != "decision"

    def test_status_ok_when_complete_data(self):
        skill = FundAnalysisSkill()
        output = skill.run(_skill_input(_base_payload()))
        assert output.status in ("OK", "PARTIAL")

    def test_warnings_are_strings(self):
        skill = FundAnalysisSkill()
        output = skill.run(_skill_input(_base_payload()))
        for w in output.warnings:
            assert isinstance(w, str)
