"""Tests for deterministic personal fund report composition."""

from __future__ import annotations

import json

from src.tools.portfolio.report_composer import (
    SECTION_ORDER,
    compose_personal_fund_report,
    render_report_markdown,
)


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


def test_composer_emits_required_section_ids_in_order():
    report = compose_personal_fund_report(_base_artifacts())
    ids = [section["id"] for section in report["report_sections"]]
    assert ids == [section_id for section_id, _ in SECTION_ORDER]
    assert [item["id"] for item in report["report_outline"]] == ids


def test_quality_gate_allows_grade_b_professional_report():
    report = compose_personal_fund_report(_base_artifacts())
    gate = report["quality_gate"]
    assert gate["grade"] == "B"
    assert gate["can_publish_professional_report"] is True


def test_quality_gate_allows_grade_c_with_limitations():
    artifacts = _base_artifacts(
        data_completeness={
            "score": 0.61,
            "grade": "C",
            "available_sections": ["Portfolio Snapshot"],
            "missing_sections": ["Nav History"],
            "optional_missing": [],
            "limitations": ["NAV history is missing."],
        },
    )
    report = compose_personal_fund_report(artifacts)
    gate = report["quality_gate"]
    assert gate["grade"] == "C"
    assert gate["can_publish_professional_report"] is True
    assert "limitations" in gate["reason"].lower()


def test_quality_gate_blocks_grade_d_without_minimal_report_mode():
    artifacts = _base_artifacts(
        data_completeness={
            "score": 0.2,
            "grade": "D",
            "available_sections": [],
            "missing_sections": ["Portfolio Snapshot"],
            "optional_missing": [],
            "limitations": ["No usable portfolio."],
        },
    )
    report = compose_personal_fund_report(artifacts)
    assert report["quality_gate"]["can_publish_professional_report"] is False


def test_quality_gate_allows_grade_d_in_minimal_mode_when_core_exists():
    artifacts = _base_artifacts(
        data_completeness={
            "score": 0.2,
            "grade": "D",
            "available_sections": ["Portfolio Snapshot"],
            "missing_sections": ["Nav History"],
            "optional_missing": [],
            "limitations": ["NAV history missing."],
        },
    )
    report = compose_personal_fund_report(artifacts, options={"minimal_report_mode": True})
    assert report["quality_gate"]["can_publish_professional_report"] is True


def test_composer_does_not_emit_formal_decision_artifacts():
    report = compose_personal_fund_report(_base_artifacts())
    dumped = json.dumps(report)
    assert '"decision"' not in dumped
    assert '"execution_ledger"' not in dumped
    assert "No formal decision generated" in dumped


def test_composer_output_is_deterministic_and_json_serializable():
    first = compose_personal_fund_report(_base_artifacts(), warnings=["w1"])
    second = compose_personal_fund_report(_base_artifacts(), warnings=["w1"])
    assert first == second
    assert json.loads(json.dumps(first)) == first


def test_render_report_markdown_is_deterministic():
    report = compose_personal_fund_report(_base_artifacts())
    rendered = render_report_markdown(report)
    assert rendered == render_report_markdown(report)
    assert "# Personal fund report" in rendered
    assert "Executive summary" in rendered
