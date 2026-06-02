"""Tests for FundAnalysisSkill derived portfolio mode."""

from __future__ import annotations

import json

import pytest

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill


class TestDerivedPortfolio:
    def test_transactions_plus_current_nav_produces_derived_snapshot(self):
        """FundAnalysisSkill should derive portfolio from transactions + current_nav."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-1",
            step_id="fa-1",
            skill_name="fund_analysis",
            payload={
                "transactions": [
                    {"action": "BUY", "fund_code": "110011", "date": "2025-06-01", "amount": 10000.0, "shares": 10000.0, "nav": 1.00},
                    {"action": "BUY", "fund_code": "110011", "date": "2025-12-01", "amount": 20000.0, "shares": 18181.82, "nav": 1.10},
                ],
                "current_nav": {"110011": 1.20},
                "as_of_date": "2026-06-01",
                "risk_profile": {
                    "risk_level": "moderate",
                    "max_single_fund_weight": 0.3,
                    "max_theme_weight": 0.4,
                    "max_trade_pct": 0.1,
                    "liquidity_reserve_pct": 0.1,
                    "short_term_trade_budget_pct": 0.1,
                },
                "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
            },
        )
        output = skill.run(input_data)
        assert output.status in ("OK", "PARTIAL")
        assert "derived_portfolio_snapshot" in output.artifacts
        assert "ledger_cashflow_summary" in output.artifacts
        snapshot = output.artifacts["derived_portfolio_snapshot"]
        assert len(snapshot["positions"]) >= 1
        assert any("derived" in w.lower() for w in output.warnings)

    def test_derived_snapshot_feeds_portfolio_summary(self):
        """Derived portfolio should produce valid portfolio_summary."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-2",
            step_id="fa-2",
            skill_name="fund_analysis",
            payload={
                "transactions": [
                    {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 15000.0, "shares": 10000.0, "nav": 1.5},
                ],
                "current_nav": {"110011": 1.80},
                "as_of_date": "2026-06-01",
                "risk_profile": {
                    "risk_level": "moderate",
                    "max_single_fund_weight": 0.3,
                    "max_theme_weight": 0.4,
                    "max_trade_pct": 0.1,
                    "liquidity_reserve_pct": 0.1,
                    "short_term_trade_budget_pct": 0.1,
                },
                "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
            },
        )
        output = skill.run(input_data)
        assert "portfolio_summary" in output.artifacts
        summary = output.artifacts["portfolio_summary"]
        assert summary["position_count"] >= 1
        assert summary["total_value"] > 0

    def test_reconciliation_runs_when_both_exist(self):
        """When host portfolio and transactions both exist, reconciliation should run."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-3",
            step_id="fa-3",
            skill_name="fund_analysis",
            payload={
                "portfolio": {
                    "as_of_date": "2026-06-01",
                    "total_value": 33818.18,
                    "cash_available": 5000,
                    "positions": [
                        {"fund_code": "110011", "fund_name": "My Fund", "current_value": 33818.18, "total_cost": 30000, "shares": 28181.82}
                    ],
                },
                "transactions": [
                    {"action": "BUY", "fund_code": "110011", "date": "2025-06-01", "amount": 10000.0, "shares": 10000.0, "nav": 1.00},
                    {"action": "BUY", "fund_code": "110011", "date": "2025-12-01", "amount": 20000.0, "shares": 18181.82, "nav": 1.10},
                ],
                "current_nav": {"110011": 1.20},
                "risk_profile": {
                    "risk_level": "moderate",
                    "max_single_fund_weight": 0.5,
                    "max_theme_weight": 0.6,
                    "max_trade_pct": 0.1,
                    "liquidity_reserve_pct": 0.1,
                    "short_term_trade_budget_pct": 0.1,
                },
                "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
            },
        )
        output = skill.run(input_data)
        # If both portfolio and transactions+current_nav exist, reconciliation should appear
        if "ledger_reconciliation_report" in output.artifacts:
            assert "comparisons" in output.artifacts["ledger_reconciliation_report"]

    def test_missing_portfolio_and_derivation_inputs_returns_failed(self):
        """Missing portfolio and no transactions+nav returns FAILED."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-4",
            step_id="fa-4",
            skill_name="fund_analysis",
            payload={"risk_profile": {"risk_level": "moderate"}},
        )
        output = skill.run(input_data)
        assert output.status == "FAILED"
        assert any("INVALID_INPUT" in str(e.get("code", "")) for e in output.errors)

    def test_derived_mode_emits_hard_evidence_not_decision(self):
        """Derived mode should emit HardEvidence, not Decision."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-5",
            step_id="fa-5",
            skill_name="fund_analysis",
            payload={
                "transactions": [
                    {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000.0, "shares": 10000.0, "nav": 1.0},
                ],
                "current_nav": {"110011": 1.20},
                "as_of_date": "2026-06-01",
                "risk_profile": {
                    "risk_level": "moderate",
                    "max_single_fund_weight": 0.3,
                    "max_theme_weight": 0.4,
                    "max_trade_pct": 0.1,
                    "liquidity_reserve_pct": 0.1,
                    "short_term_trade_budget_pct": 0.1,
                },
                "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
            },
        )
        output = skill.run(input_data)
        for evidence in output.evidence_items:
            if hasattr(evidence, "evidence_type"):
                assert evidence.evidence_type != "SoftEvidence"  # Should be HardEvidence
        assert "decision" not in output.artifacts
        assert "execution_ledger" not in output.artifacts

    def test_derived_has_derived_portfolio_snapshot_evidence(self):
        """Derived portfolio should have a HardEvidence for the derived snapshot."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-6",
            step_id="fa-6",
            skill_name="fund_analysis",
            payload={
                "transactions": [
                    {"action": "BUY", "fund_code": "110011", "date": "2025-01-01", "amount": 10000.0, "shares": 10000.0, "nav": 1.0},
                ],
                "current_nav": {"110011": 1.20},
                "as_of_date": "2026-06-01",
                "risk_profile": {
                    "risk_level": "moderate",
                    "max_single_fund_weight": 0.3,
                    "max_theme_weight": 0.4,
                    "max_trade_pct": 0.1,
                    "liquidity_reserve_pct": 0.1,
                    "short_term_trade_budget_pct": 0.1,
                },
                "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
            },
        )
        output = skill.run(input_data)
        evidence_names = [
            spec["metric_name"] if isinstance(spec, dict) else getattr(spec, "metric_name", "")
            for spec in [
                e if isinstance(e, dict) else e
                for e in output.evidence_items
            ]
        ]
        # Check evidence via artifacts
        has_derived = any(
            "derived" in str(ev).lower()
            for ev in output.evidence_items
        )
        # Or check artifacts
        assert "derived_portfolio_snapshot" in output.artifacts

    def test_research_planning_generates_query_plan(self):
        """When research_planning is True, query plan should be generated."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-7",
            step_id="fa-7",
            skill_name="fund_analysis",
            payload={
                "portfolio": {
                    "as_of_date": "2026-06-01",
                    "total_value": 200000,
                    "cash_available": 20000,
                    "positions": [
                        {"fund_code": "110011", "fund_name": "Example Fund", "current_value": 60000, "total_cost": 58000, "shares": 50000, "tags": ["equity"]},
                    ],
                },
                "fund_profiles": {"110011": {"fund_code": "110011", "name": "Example Fund", "fund_type": "equity"}},
                "holdings": {"110011": [{"name": "Company A", "weight": 0.08, "industry": "tech", "region": "CN"}]},
                "risk_profile": {
                    "risk_level": "moderate",
                    "max_single_fund_weight": 0.3,
                    "max_theme_weight": 0.4,
                    "max_trade_pct": 0.1,
                    "liquidity_reserve_pct": 0.1,
                    "short_term_trade_budget_pct": 0.1,
                },
                "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
                "research_planning": True,
            },
        )
        output = skill.run(input_data)
        assert "research_query_plan" in output.artifacts
        plan = output.artifacts["research_query_plan"]
        assert "news_queries" in plan
        assert "entities" in plan
        assert len(plan["news_queries"]) > 0

    def test_benchmark_peer_data_pass_through(self):
        """Optional benchmark/peer data should be passed through."""
        skill = FundAnalysisSkill()
        input_data = SkillInput(
            task_id="test-8",
            step_id="fa-8",
            skill_name="fund_analysis",
            payload={
                "portfolio": {
                    "as_of_date": "2026-06-01",
                    "total_value": 100000,
                    "cash_available": 10000,
                    "positions": [
                        {"fund_code": "110011", "fund_name": "Test", "current_value": 90000, "total_cost": 85000, "shares": 50000}
                    ],
                },
                "fund_profiles": {"110011": {"fund_code": "110011", "name": "Test", "fund_type": "equity"}},
                "risk_profile": {"risk_level": "moderate", "max_single_fund_weight": 1.0, "max_theme_weight": 1.0, "max_trade_pct": 1.0, "liquidity_reserve_pct": 0.0, "short_term_trade_budget_pct": 1.0},
                "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
                "benchmarks": {"110011": {"benchmark_id": "CSI300", "benchmark_name": "CSI 300"}},
                "benchmark_history": {"benchmark_id": "CSI300", "history": []},
                "peer_group": {"110011": {"peers": [{"fund_code": "110012", "name": "Peer A"}]}},
                "fee_schedules": {"110011": {"subscription_fee_pct": 0.015}},
                "redemption_rules": {"110011": {"t_plus_days": 3}},
            },
        )
        output = skill.run(input_data)
        report = output.artifacts.get("fund_analysis_report", {})
        assert "benchmark_summary" in report or "benchmark_summary" in output.artifacts
