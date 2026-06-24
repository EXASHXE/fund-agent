"""Tests for analysis-only rebalance plan — must not contain execution/trading semantics."""

from __future__ import annotations

from src.tools.portfolio.report_composer import compose_personal_fund_report


def _base_artifacts(**overrides):
    artifacts = {
        "portfolio_summary": {
            "as_of_date": "2026-06-01",
            "total_value": 200000,
            "cash_available": 20000,
            "position_count": 2,
            "position_weights": {"110011": 0.4, "220022": 0.5},
        },
        "position_summary": {
            "110011": {"fund_code": "110011", "current_value": 80000, "total_cost": 75000},
            "220022": {"fund_code": "220022", "current_value": 100000, "total_cost": 95000},
        },
        "pnl_summary": {
            "total_cost": 170000,
            "total_value": 180000,
            "unrealized_pnl": 10000,
            "unrealized_pnl_pct": 0.058824,
            "positions": {"110011": {"unrealized_pnl": 5000}},
        },
        "exposure_summary": {
            "fund_type_exposure": {"equity": 0.4, "bond": 0.5},
            "industry_exposure": {"industry:tech": 0.2},
            "theme_exposure": {"tag:growth": 0.4},
        },
        "risk_flags": [],
        "suggested_rebalance_plan": {"suggested_trade_plan": [], "warnings": [], "total_trade_amount": 0},
        "fund_analysis_report": {
            "fund_metrics": {"110011": {"total_return": 0.1}},
            "concentration": {"single_fund_max_weight": 0.5, "hhi": 0.41},
            "trade_budget": {
                "max_buy_amount": 10000,
                "max_sell_amount": 15000,
                "liquidity_reserve": 20000,
            },
        },
        "data_completeness": {
            "score": 0.85,
            "grade": "B",
            "available_sections": ["Portfolio Snapshot", "Fund Profiles"],
            "missing_sections": [],
            "optional_missing": ["Peer Group"],
            "limitations": [],
        },
        "analysis_coverage": {
            "performance": "available",
            "research_plan": "not_requested",
        },
        "report_limitations": ["Optional peer data is unavailable."],
    }
    artifacts.update(overrides)
    return artifacts


class TestRebalancePlanAnalysisOnly:
    """Rebalance plan section must be analysis-only, not execution/trading instructions."""

    def test_rebalance_plan_contains_analysis_language(self):
        """Rebalance plan section should contain 'simulation' or 'analysis-only' language."""
        artifacts = _base_artifacts(
            suggested_rebalance_plan={
                "suggested_trade_plan": [
                    {"fund_code": "110011", "action": "reduce", "amount": 5000},
                ],
                "warnings": [],
                "total_trade_amount": 5000,
            },
        )
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "rebalance_plan")
        assert section is not None
        bullets_text = " ".join(section["bullets"]).lower()
        # Should use simulation/analysis language
        assert "simulation" in bullets_text or "analysis" in bullets_text

    def test_rebalance_plan_does_not_contain_execution_semantics(self):
        """Rebalance plan should NOT contain execution/trading command language."""
        artifacts = _base_artifacts(
            suggested_rebalance_plan={
                "suggested_trade_plan": [
                    {"fund_code": "110011", "action": "reduce", "amount": 5000},
                ],
                "warnings": [],
                "total_trade_amount": 5000,
            },
        )
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "rebalance_plan")
        assert section is not None
        bullets_text = " ".join(section["bullets"]).lower()
        # Should NOT contain execution command language
        execution_phrases = ["execute", "place order", "submit trade", "confirm trade"]
        for phrase in execution_phrases:
            assert phrase not in bullets_text

    def test_rebalance_plan_missing_shows_missing(self):
        """When rebalance plan is missing, section should be MISSING."""
        artifacts = _base_artifacts(suggested_rebalance_plan=None)
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "rebalance_plan")
        assert section is not None
        assert section["status"] == "MISSING"


class TestActionWatchlistAnalysisOnly:
    """Action watchlist must be analysis-only; active recommendations need evidence anchors."""

    def test_action_watchlist_contains_analysis_only_language(self):
        """Action watchlist should mention analysis-only or decision_support."""
        artifacts = _base_artifacts(
            suggested_rebalance_plan={
                "suggested_trade_plan": [
                    {"fund_code": "110011", "action": "reduce", "amount": 5000},
                ],
                "warnings": [],
                "total_trade_amount": 5000,
            },
        )
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "action_watchlist")
        assert section is not None
        bullets_text = " ".join(section["bullets"]).lower()
        # Should mention analysis-only or decision_support
        assert "analysis-only" in bullets_text or "decision_support" in bullets_text

    def test_action_watchlist_with_blockers_shows_wait(self):
        """When blockers exist, watchlist should show wait/check language."""
        artifacts = _base_artifacts(
            analysis_plan={
                "decision_support_ready": False,
                "blockers": ["insufficient_nav_data"],
                "warnings": [],
                "missing_inputs": ["nav_history"],
                "next_data_to_fetch": ["nav_history"],
            },
            evidence_gap_diagnostics={
                "missing_nav_history": True,
                "details": [
                    {"code": "missing_nav_history", "recommended_next_data": "nav_history"},
                ],
            },
        )
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "action_watchlist")
        assert section is not None
        bullets_text = " ".join(section["bullets"]).lower()
        # Should show blocker/wait language
        assert "blocker" in bullets_text or "not" in bullets_text or "wait" in bullets_text or "check" in bullets_text


class TestInsufficientEvidenceProducesPassiveActions:
    """When evidence is insufficient, report should produce WATCH/WAIT/HOLD/CHECK, not active BUY/SELL."""

    def test_insufficient_evidence_shows_missing_in_evidence_status(self):
        """When evidence is missing, evidence_status should show it."""
        artifacts = _base_artifacts(
            analysis_plan={
                "decision_support_ready": False,
                "blockers": ["insufficient_evidence"],
                "warnings": ["no_benchmark_data"],
                "missing_inputs": ["benchmark_data", "peer_data"],
                "next_data_to_fetch": ["benchmark_data"],
            },
            evidence_gap_diagnostics={
                "missing_benchmark": True,
                "missing_peer": True,
                "details": [
                    {"code": "missing_benchmark", "recommended_next_data": "benchmark_data"},
                    {"code": "missing_peer", "recommended_next_data": "peer_group_data"},
                ],
            },
        )
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "evidence_status")
        assert section is not None
        # Should show missing evidence
        bullets_text = " ".join(section["bullets"])
        assert "missing" in bullets_text.lower() or "insufficient" in bullets_text.lower()

    def test_uncertainty_note_mentions_no_formal_decision(self):
        """Uncertainty note should always mention no formal decision was generated."""
        artifacts = _base_artifacts()
        report = compose_personal_fund_report(artifacts)
        section = _find_section(report, "uncertainty_note")
        assert section is not None
        bullets_text = " ".join(section["bullets"]).lower()
        assert "no formal decision" in bullets_text or "decision-support" in bullets_text


def _find_section(report: dict, section_id: str) -> dict | None:
    for section in report["report_sections"]:
        if section.get("id") == section_id:
            return section
    return None
