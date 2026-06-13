"""Tests for advisory_markdown_adapter — deterministic compose → render bridge."""

from __future__ import annotations

import pytest

from src.skills_runtime.workflow.advisory_markdown_adapter import (
    adapt_personal_fund_report_to_advisory_markdown_report,
)


def _make_source_section(
    section_id: str,
    bullets: list[str] | None = None,
    status: str = "OK",
    data_sources: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict:
    return {
        "id": section_id,
        "title": section_id.replace("_", " ").title(),
        "status": status,
        "bullets": bullets or [],
        "data_sources": data_sources or [],
        "limitations": limitations or [],
    }


def _make_final_report(sections: list[dict], warnings: list[str] | None = None) -> dict:
    return {
        "report_sections": sections,
        "report_outline": [],
        "quality_gate": {"grade": "B", "can_publish_professional_report": True, "reason": "ok"},
        "warnings": warnings or [],
    }


class TestAdapterMapping:
    def test_maps_executive_summary_to_direct_answer(self):
        sections = [
            _make_source_section("executive_summary", bullets=["组合总市值：50000"], status="PARTIAL"),
        ]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections)
        )
        adapted_sections = adapted["report_sections"]
        direct = _find_by_id(adapted_sections, "direct_answer")
        assert direct is not None
        assert "组合总市值：50000" in direct["bullets"]
        assert direct["status"] == "PARTIAL"
        assert "报告模式" in direct["bullets"][-1] or "不包含正式交易决策" in str(direct["bullets"])

    def test_maps_portfolio_snapshot_to_portfolio_overview(self):
        sections = [
            _make_source_section("portfolio_snapshot", bullets=["截至 2024-12-31，总市值 50,000"]),
            _make_source_section("allocation_and_exposure", bullets=["最大持仓 000001"]),
        ]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections)
        )
        overview = _find_by_id(adapted["report_sections"], "portfolio_overview")
        assert overview is not None
        assert "截至 2024-12-31" in str(overview["bullets"])
        assert "最大持仓 000001" in str(overview["bullets"])

    def test_maps_risk_flags_to_current_risks(self):
        sections = [
            _make_source_section("risk_flags", bullets=["Risk flags: high, medium"], status="PARTIAL"),
            _make_source_section(
                "professional_diagnostics",
                bullets=["Overlap scan found 2 items"],
                status="PARTIAL",
            ),
        ]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections)
        )
        risks = _find_by_id(adapted["report_sections"], "current_risks")
        assert risks is not None
        assert "Risk flags" in str(risks["bullets"])
        assert "Overlap scan" in str(risks["bullets"])

    def test_maps_pnl_and_cost_basis_to_position_diagnostics(self):
        sections = [
            _make_source_section("pnl_and_cost_basis", bullets=["Unrealized PnL: 500"]),
            _make_source_section("position_contribution", bullets=["Largest profit: 000001"]),
        ]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections)
        )
        diag = _find_by_id(adapted["report_sections"], "position_diagnostics")
        assert diag is not None
        assert "Unrealized PnL" in str(diag["bullets"])
        assert "Largest profit" in str(diag["bullets"])

    def test_maps_missing_data_and_warnings_to_data_gaps(self):
        sections = [
            _make_source_section("missing_data", bullets=["Missing: NAV"]),
            _make_source_section(
                "data_completeness_and_limitations", bullets=["Completeness grade D"]
            ),
        ]
        warnings = ["NO_PROVIDER_SNAPSHOT", "MISSING_COST_BASIS"]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections, warnings=warnings)
        )
        gaps = _find_by_id(adapted["report_sections"], "data_gaps")
        assert gaps is not None
        assert "Missing: NAV" in str(gaps["bullets"])
        assert "Completeness grade D" in str(gaps["bullets"])
        assert "NO_PROVIDER_SNAPSHOT" in str(gaps["bullets"])
        assert "MISSING_COST_BASIS" in str(gaps["bullets"])


class TestWarningPreservation:
    def test_preserves_missing_cost_basis(self):
        sections = [
            _make_source_section("missing_data", bullets=["Cost basis absent for 000001"]),
        ]
        warnings = ["MISSING_COST_BASIS"]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections, warnings=warnings)
        )
        gaps = _find_by_id(adapted["report_sections"], "data_gaps")
        assert "MISSING_COST_BASIS" in str(gaps["bullets"])

    def test_preserves_no_provider_snapshot(self):
        sections = [
            _make_source_section("data_completeness_and_limitations", bullets=["Missing: provider data"]),
        ]
        warnings = ["NO_PROVIDER_SNAPSHOT"]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections, warnings=warnings)
        )
        gaps = _find_by_id(adapted["report_sections"], "data_gaps")
        assert "NO_PROVIDER_SNAPSHOT" in str(gaps["bullets"])

    def test_warnings_in_bullets_preserved(self):
        sections = [
            _make_source_section("missing_data", bullets=["MISSING_COST_BASIS: 000001"]),
            _make_source_section("data_completeness_and_limitations", bullets=["NO_PROVIDER_SNAPSHOT: ak"]),
        ]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections)
        )
        gaps = _find_by_id(adapted["report_sections"], "data_gaps")
        assert "MISSING_COST_BASIS" in str(gaps["bullets"])
        assert "NO_PROVIDER_SNAPSHOT" in str(gaps["bullets"])


class TestAnalysisModes:
    def test_report_only_does_not_create_formal_decision(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
            analysis_mode="report_only",
        )
        decision_sec = _find_by_id(adapted["report_sections"], "decision_explanation")
        assert "未调用决策支持" in str(decision_sec["bullets"])
        assert "report_only" in adapted["analysis_mode"]

    def test_formal_mode_without_decision_shows_blocked(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
            analysis_mode="formal_trade_decision",
            decision=None,
        )
        decision_sec = _find_by_id(adapted["report_sections"], "decision_explanation")
        assert "正式决策未生成" in str(decision_sec["bullets"])

    def test_formal_mode_with_decision_shows_action(self):
        decision = {
            "action": "HOLD",
            "fund_code": "000001",
            "execution_amount": 0,
            "evidence_anchors": [],
        }
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
            analysis_mode="formal_trade_decision",
            decision=decision,
        )
        decision_sec = _find_by_id(adapted["report_sections"], "decision_explanation")
        assert "HOLD" in str(decision_sec["bullets"])
        assert "000001" in str(decision_sec["bullets"])

    def test_no_formal_decision_invented_in_report_only(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
            analysis_mode="report_only",
        )
        decision_sec = _find_by_id(adapted["report_sections"], "decision_explanation")
        assert decision_sec is not None
        assert decision_sec["bullets"] and any(
            "未调用决策支持" in b for b in decision_sec["bullets"]
        )


class TestMissingSourceSections:
    def test_missing_executive_summary_marks_direct_answer_partial(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
        )
        direct = _find_by_id(adapted["report_sections"], "direct_answer")
        assert direct["status"] == "MISSING"

    def test_missing_portfolio_snapshot_marks_portfolio_overview_missing(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
        )
        overview = _find_by_id(adapted["report_sections"], "portfolio_overview")
        assert overview["status"] == "MISSING"

    def test_missing_action_watchlist_marks_action_boundary_partial(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
        )
        boundary = _find_by_id(adapted["report_sections"], "action_boundary")
        assert boundary["status"] in ("MISSING", "PARTIAL")

    def test_section_with_both_sources_missing_marks_missing(self):
        sections = [
            _make_source_section("pnl_and_cost_basis", bullets=[], status="MISSING"),
        ]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections),
        )
        diag = _find_by_id(adapted["report_sections"], "position_diagnostics")
        assert diag["status"] in ("MISSING", "PARTIAL")


class TestDeterministicOutput:
    def test_deterministic_with_same_input(self):
        sections = [
            _make_source_section("executive_summary", bullets=["组合总市值：50000"]),
            _make_source_section("portfolio_snapshot", bullets=["截至 2024-12-31"]),
        ]
        report = _make_final_report(sections)
        r1 = adapt_personal_fund_report_to_advisory_markdown_report(report)
        r2 = adapt_personal_fund_report_to_advisory_markdown_report(report)
        assert r1 == r2

    def test_deterministic_full_pipeline(self):
        from src.skills_runtime.workflow.markdown_report import render_advisory_report_markdown

        sections = [
            _make_source_section("executive_summary", bullets=["组合总市值：50000"]),
            _make_source_section("missing_data", bullets=["NAV数据缺失"]),
        ]
        warnings = ["MISSING_COST_BASIS", "NO_PROVIDER_SNAPSHOT"]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections, warnings=warnings),
        )
        md1 = render_advisory_report_markdown(adapted)
        md2 = render_advisory_report_markdown(adapted)
        assert md1 == md2


class TestNoBrokerExecution:
    def test_no_broker_language_in_action_boundary(self):
        sections = [
            _make_source_section("action_watchlist", bullets=["Action watchlist: 1"]),
            _make_source_section("rebalance_plan", bullets=["Rebalance: 0 trades"]),
        ]
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report(sections),
        )
        boundary = _find_by_id(adapted["report_sections"], "action_boundary")
        text = str(boundary["bullets"])
        assert "阻止" in text or "经纪" not in text
        for forbidden in ["买入指令", "卖出指令", "下单", "委托", "执行交易"]:
            assert forbidden not in text, f"forbidden: {forbidden}"

    def test_no_broker_language_in_decision_explanation(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
            analysis_mode="formal_trade_decision",
            decision={
                "action": "HOLD",
                "fund_code": "000001",
                "execution_amount": 0,
            },
        )
        decision_sec = _find_by_id(adapted["report_sections"], "decision_explanation")
        text = str(decision_sec["bullets"])
        for forbidden in ["买入指令", "卖出指令", "下单", "委托", "执行交易"]:
            assert forbidden not in text, f"forbidden: {forbidden}"


class TestAllRequiredSectionsPresent:
    EXPECTED_IDS = [
        "direct_answer",
        "portfolio_overview",
        "current_risks",
        "position_diagnostics",
        "evidence_status",
        "data_gaps",
        "action_boundary",
        "suggested_next_steps",
        "decision_explanation",
        "risk_disclaimer",
    ]

    def test_all_10_sections_produced(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
        )
        ids = {s["id"] for s in adapted["report_sections"]}
        for expected in self.EXPECTED_IDS:
            assert expected in ids, f"missing section: {expected}"

    def test_all_sections_have_required_fields(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
        )
        for s in adapted["report_sections"]:
            assert "id" in s
            assert "title" in s
            assert "status" in s
            assert "bullets" in s
            assert isinstance(s["bullets"], list)
            assert "data_sources" in s
            assert "limitations" in s

    def test_valid_statuses(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
        )
        for s in adapted["report_sections"]:
            assert s["status"] in {"OK", "PARTIAL", "MISSING"}, f"invalid status for {s['id']}"


class TestRiskDisclaimer:
    def test_risk_disclaimer_has_explicit_bullets(self):
        adapted = adapt_personal_fund_report_to_advisory_markdown_report(
            _make_final_report([]),
        )
        disclaimer = _find_by_id(adapted["report_sections"], "risk_disclaimer")
        assert disclaimer["status"] == "OK"
        bullets = str(disclaimer["bullets"])
        assert "不构成投资建议" in bullets
        assert "不执行" in bullets


def _find_by_id(sections: list[dict], section_id: str) -> dict | None:
    for s in sections:
        if isinstance(s, dict) and s.get("id") == section_id:
            return s
    return None
