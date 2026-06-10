"""Integration tests for examples/user_flows/*.json scenarios.

Validates that each user flow fixture can be processed end-to-end through
FundAnalysisSkill and produces valid analysis_plan and evidence_gap_diagnostics
artifacts with contract-aligned field names.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis.skill import FundAnalysisSkill

USER_FLOWS_DIR = Path(__file__).resolve().parents[2] / "examples" / "user_flows"

FIXTURE_FILES = [
    "semiconductor_profit_protection.json",
    "innovation_drug_drawdown.json",
    "bond_cash_allocation.json",
    "mixed_portfolio_rebalance.json",
    "energy_loss_position.json",
]

FORMAL_DECISION_ARTIFACTS = {
    "decision",
    "decisions",
    "execution_ledger",
    "execution_ledgers",
}

skill = FundAnalysisSkill()


def _load_fixture(filename: str) -> dict:
    path = USER_FLOWS_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _run_fixture(filename: str) -> dict:
    payload = _load_fixture(filename)
    si = SkillInput(
        task_id=f"user-flow-{filename}",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    )
    output = skill.run(si)
    assert output.status in ("OK", "PARTIAL"), (
        f"{filename} unexpected status {output.status}: {output.errors}"
    )
    return output.artifacts


def test_fixture_uses_runtime_contract_field_names() -> None:
    for filename in FIXTURE_FILES:
        data = _load_fixture(filename)
        assert "fund_profiles" in data, f"{filename}: must use fund_profiles (dict), not fund_metadata (list)"
        assert isinstance(data["fund_profiles"], dict), f"{filename}: fund_profiles must be a dict"
        assert "fee_schedules" in data, f"{filename}: must use fee_schedules (dict)"
        assert "redemption_rules" in data, f"{filename}: must use redemption_rules (dict)"
        assert "constraints" in data, f"{filename}: must use constraints, not user_constraints"
        assert "benchmarks" in data, f"{filename}: must use benchmarks (dict)"
        assert "benchmark_history" in data, f"{filename}: must use benchmark_history (dict)"


def test_fixture_user_question_propagated_to_analysis_plan() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        plan = artifacts.get("analysis_plan", {})
        data = _load_fixture(filename)
        expected_goal = data.get("user_question", "")
        assert plan.get("user_goal") == expected_goal, (
            f"{filename}: analysis_plan.user_goal should match user_question"
        )


def test_fixture_produces_analysis_plan_artifact() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "analysis_plan" in artifacts, f"{filename}: missing analysis_plan artifact"
        plan = artifacts["analysis_plan"]
        assert isinstance(plan["available_inputs"], list)
        assert isinstance(plan["missing_inputs"], list)
        assert isinstance(plan["recommended_skill_sequence"], list)
        assert isinstance(plan["blockers"], list)
        assert isinstance(plan["decision_support_ready"], bool)


def test_fixture_produces_evidence_gap_diagnostics() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "evidence_gap_diagnostics" in artifacts, f"{filename}: missing evidence_gap_diagnostics"
        gap = artifacts["evidence_gap_diagnostics"]
        assert isinstance(gap["missing_holdings"], bool)
        assert isinstance(gap["missing_recent_news"], bool)
        assert isinstance(gap["missing_sentiment"], bool)
        assert isinstance(gap["details"], list)


def test_fixture_no_formal_decision_artifacts() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        overlap = FORMAL_DECISION_ARTIFACTS & set(artifacts.keys())
        assert not overlap, f"{filename}: fund_analysis must not produce {overlap}"


def test_fixture_decision_support_not_ready_when_news_missing() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        plan = artifacts.get("analysis_plan", {})
        gap = artifacts.get("evidence_gap_diagnostics", {})
        if gap.get("missing_recent_news"):
            assert plan["decision_support_ready"] is False, (
                f"{filename}: decision_support_ready must be False when news missing"
            )
            assert "decision_support" not in plan["recommended_skill_sequence"], (
                f"{filename}: decision_support must not be recommended when not ready"
            )


def test_fixture_with_news_evidence_marks_news_present() -> None:
    payload = _load_fixture("semiconductor_profit_protection.json")
    payload["news_evidence"] = [
        {"source": "test", "headline": "semiconductor rally", "date": "2026-06-01"},
    ]
    si = SkillInput(
        task_id="test-news-present",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    )
    output = skill.run(si)
    gap = output.artifacts.get("evidence_gap_diagnostics", {})
    assert gap.get("missing_recent_news") is False, (
        "missing_recent_news should be False when news_evidence is provided"
    )


def test_fixture_with_sentiment_evidence_marks_sentiment_present() -> None:
    payload = _load_fixture("semiconductor_profit_protection.json")
    payload["sentiment_evidence"] = [
        {"fund_code": "008253", "sentiment": "bullish", "score": 0.8},
    ]
    si = SkillInput(
        task_id="test-sentiment-present",
        step_id="fund-analysis",
        skill_name="fund_analysis",
        payload=payload,
    )
    output = skill.run(si)
    gap = output.artifacts.get("evidence_gap_diagnostics", {})
    assert gap.get("missing_sentiment") is False, (
        "missing_sentiment should be False when sentiment_evidence is provided"
    )


def test_fixture_produces_position_contribution() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "position_contribution" in artifacts, f"{filename}: missing position_contribution"
        pc = artifacts["position_contribution"]
        assert isinstance(pc["positions"], list)
        assert len(pc["positions"]) > 0
        assert "summary" in pc


def test_fixture_produces_profit_protection_diagnostics() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        assert "profit_protection_diagnostics" in artifacts, f"{filename}: missing profit_protection_diagnostics"
        pp = artifacts["profit_protection_diagnostics"]
        assert isinstance(pp["items"], list)
        assert "summary" in pp


def test_semiconductor_triggers_high_profit_protection() -> None:
    artifacts = _run_fixture("semiconductor_profit_protection.json")
    pp = artifacts.get("profit_protection_diagnostics", {})
    items = pp.get("items", [])
    high_profit = [i for i in items if i.get("profit_level") in ("high", "very_high")]
    assert len(high_profit) > 0, "semiconductor fixture should have high/very_high profit positions"


def test_mixed_portfolio_has_position_contribution_summary() -> None:
    artifacts = _run_fixture("mixed_portfolio_rebalance.json")
    pc = artifacts.get("position_contribution", {})
    summary = pc.get("summary", {})
    assert summary.get("largest_value_position", "") != "", "should identify largest value position"


def test_no_user_flow_produces_formal_decision_from_phase2() -> None:
    for filename in FIXTURE_FILES:
        artifacts = _run_fixture(filename)
        for key in ("position_contribution", "profit_protection_diagnostics"):
            artifact = artifacts.get(key, {})
            overlap = FORMAL_DECISION_ARTIFACTS & set(artifact.keys()) if isinstance(artifact, dict) else set()
            assert not overlap, f"{filename} {key}: must not contain formal decision keys"
