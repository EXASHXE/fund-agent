"""FundAnalysisSkill personal portfolio analysis tests."""

from __future__ import annotations

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill


def test_portfolio_payload_produces_hard_evidence_and_report_artifact():
    output = FundAnalysisSkill().run(_input(_portfolio_payload()))

    assert output.status == "OK"
    assert output.artifacts["fund_analysis_report"]
    assert output.artifacts["portfolio_summary"]["position_count"] == 3
    assert "risk_flags" in output.artifacts
    assert "suggested_rebalance_plan" in output.artifacts
    assert output.evidence_items
    assert all(item.evidence_type == "HardEvidence" for item in output.evidence_items)
    assert any(
        item.source_type == "fund_risk_return_metrics"
        for item in output.evidence_items
    )


def test_missing_nav_produces_partial_with_warning_not_crash():
    payload = _portfolio_payload()
    payload["nav_history"].pop("161725")

    output = FundAnalysisSkill().run(_input(payload))

    assert output.status == "PARTIAL"
    assert output.evidence_items
    assert any("Missing NAV history for fund_code=161725" in item for item in output.warnings)


def test_related_entities_only_payload_still_works_with_warning():
    output = FundAnalysisSkill().run(
        _input({"related_entities": ["fund:110011"]})
    )

    assert output.status == "OK"
    assert output.evidence_items
    assert output.warnings == [
        "FundAnalysisSkill received only related_entities; "
        "produced baseline evidence only."
    ]


def test_malformed_payload_returns_failed_invalid_input():
    output = FundAnalysisSkill().run(_input({"portfolio": {"positions": []}}))

    assert output.status == "FAILED"
    assert output.errors[0]["code"] == "INVALID_INPUT"
    assert not output.evidence_items


def _input(payload: dict) -> SkillInput:
    return SkillInput(
        task_id="fund-analysis-test",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    )


def _portfolio_payload() -> dict:
    return {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 200000.0,
            "cash_available": 30000.0,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Alpha Healthcare",
                    "current_value": 30000.0,
                    "total_cost": 28000.0,
                    "shares": 12000.0,
                    "target_weight": 0.12,
                    "tags": ["healthcare", "active"],
                },
                {
                    "fund_code": "000001",
                    "fund_name": "Balanced Core",
                    "current_value": 50000.0,
                    "total_cost": 48000.0,
                    "shares": 20000.0,
                    "target_weight": 0.24,
                    "tags": ["core", "balanced"],
                },
                {
                    "fund_code": "161725",
                    "fund_name": "Tech Growth",
                    "current_value": 40000.0,
                    "total_cost": 42000.0,
                    "shares": 18000.0,
                    "target_weight": 0.18,
                    "tags": ["technology", "growth"],
                },
            ],
        },
        "fund_profiles": {
            "110011": {"fund_code": "110011", "name": "Alpha Healthcare", "fund_type": "active"},
            "000001": {"fund_code": "000001", "name": "Balanced Core", "fund_type": "balanced"},
            "161725": {"fund_code": "161725", "name": "Tech Growth", "fund_type": "equity"},
        },
        "nav_history": {
            "110011": _nav(1.0, 1.12, 1.18),
            "000001": _nav(1.0, 1.04, 1.08),
            "161725": _nav(1.0, 0.96, 1.05),
        },
        "holdings": {
            "110011": [{"name": "A", "weight": 1.0, "industry": "healthcare", "region": "CN"}],
            "000001": [{"name": "B", "weight": 1.0, "industry": "balanced", "region": "CN"}],
            "161725": [{"name": "C", "weight": 1.0, "industry": "technology", "region": "US"}],
        },
        "risk_profile": {
            "risk_level": "moderate",
            "max_single_fund_weight": 0.35,
            "max_theme_weight": 0.45,
            "max_trade_pct": 0.1,
            "liquidity_reserve_pct": 0.1,
            "short_term_trade_budget_pct": 0.1,
        },
        "constraints": {
            "min_trade_amount": 100.0,
            "forbidden_actions": [],
        },
    }


def _nav(first: float, middle: float, last: float) -> list[dict]:
    return [
        {"date": "2025-06-01", "nav": first},
        {"date": "2025-12-01", "nav": middle},
        {"date": "2026-06-01", "nav": last},
    ]
