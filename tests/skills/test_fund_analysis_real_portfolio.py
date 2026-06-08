"""FundAnalysisSkill tests with realistic portfolio data from JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill


def _load_json(name: str) -> dict:
    return json.loads(Path(f"examples/{name}").read_text(encoding="utf-8"))


def test_realistic_portfolio_produces_artifacts():
    payload = _load_json("portfolio_review_200k.json")
    output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="step1", skill_name="fund_analysis",
        payload=payload,
    ))

    artifacts = output.artifacts
    required_keys = {
        "portfolio_summary", "position_summary", "exposure_summary",
        "risk_flags", "suggested_rebalance_plan", "fund_analysis_report",
    }
    for key in required_keys:
        assert key in artifacts, f"Missing artifact key: {key}"


def test_realistic_portfolio_produces_hard_evidence():
    payload = _load_json("portfolio_review_200k.json")
    output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="step1", skill_name="fund_analysis",
        payload=payload,
    ))

    assert len(output.evidence_items) > 0
    assert all(item.evidence_type == "HardEvidence" for item in output.evidence_items)


def test_fund_analysis_never_returns_decision():
    payload = _load_json("portfolio_review_200k.json")
    output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="step1", skill_name="fund_analysis",
        payload=payload,
    ))

    assert "decision" not in output.artifacts
    assert "execution_ledger" not in output.artifacts


def test_missing_optional_data_returns_partial():
    payload = {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 50000.0,
            "cash_available": 5000.0,
            "positions": [
                {"fund_code": "F001", "fund_name": "Fund One", "current_value": 50000.0, "total_cost": 48000.0, "tags": ["equity"]},
            ],
        },
    }
    output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="step1", skill_name="fund_analysis",
        payload=payload,
    ))

    assert output.status == "PARTIAL"
    assert len(output.warnings) > 0
    assert output.evidence_items


def test_transactions_produce_cost_basis():
    payload = _load_json("portfolio_review_200k.json")
    output = FundAnalysisSkill().run(SkillInput(
        task_id="test", step_id="step1", skill_name="fund_analysis",
        payload=payload,
    ))

    assert output.artifacts.get("cost_basis_summary") is not None
    assert isinstance(output.artifacts["cost_basis_summary"], dict)
    assert len(output.artifacts["cost_basis_summary"]) > 0
