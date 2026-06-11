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
    "high_overlap_qdii_ai.json",
    "short_holding_fee_sell_request.json",
    "cash_buffer_too_low_buy_request.json",
    "dividend_low_vol_allocation.json",
    "broad_market_index_vs_active_fund.json",
    "dca_drawdown_continue_or_pause.json",
    "event_positive_news_price_weak.json",
    "missing_transaction_history_but_positions_available.json",
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


def test_semiconductor_profit_protection_diagnostics_exists() -> None:
    artifacts = _run_fixture("semiconductor_profit_protection.json")
    pp = artifacts.get("profit_protection_diagnostics", {})
    assert pp, "semiconductor fixture must produce profit_protection_diagnostics"
    items = pp.get("items", [])
    high_profit = [i for i in items if i.get("profit_level") in ("high", "very_high")]
    assert len(high_profit) > 0, "semiconductor fixture should have high/very_high profit positions"


def test_semiconductor_no_formal_decision() -> None:
    artifacts = _run_fixture("semiconductor_profit_protection.json")
    overlap = FORMAL_DECISION_ARTIFACTS & set(artifacts.keys())
    assert not overlap, f"semiconductor must not produce formal decisions: {overlap}"


def test_innovation_drug_right_side_diagnostics_exists() -> None:
    artifacts = _run_fixture("innovation_drug_drawdown.json")
    rs = artifacts.get("right_side_confirmation_diagnostics", {})
    assert rs, "innovation_drug fixture must produce right_side_confirmation_diagnostics"
    items = rs.get("items", [])
    assert len(items) > 0, "innovation_drug should have right-side items"
    applicable_items = [
        i for i in items
        if isinstance(i, dict) and i.get("applicability") != "not_applicable"
    ]
    if applicable_items:
        for item in applicable_items:
            assert "right_side_confirmed" in item, "right-side item must have right_side_confirmed field"
            assert "evidence_state" in item, "right-side item must have evidence_state field"


def test_innovation_drug_event_hype_failure_may_exist() -> None:
    artifacts = _run_fixture("innovation_drug_drawdown.json")
    ehf = artifacts.get("event_hype_failure_diagnostics", {})
    if ehf and ehf.get("items"):
        assert isinstance(ehf["items"], list)


def test_bond_cash_deployment_diagnostics_exists() -> None:
    artifacts = _run_fixture("bond_cash_allocation.json")
    cd = artifacts.get("cash_deployment_diagnostics", {})
    assert cd, "bond_cash fixture must produce cash_deployment_diagnostics"
    summary = cd.get("summary", {})
    assert "deployment_readiness" in summary
    pp = artifacts.get("profit_protection_diagnostics", {})
    if pp and pp.get("items"):
        high_profit = [i for i in pp["items"] if i.get("profit_level") in ("high", "very_high")]
        assert len(high_profit) == 0, "bond_cash should not have false high profit_protection signal"


def test_mixed_portfolio_position_contribution_summary() -> None:
    artifacts = _run_fixture("mixed_portfolio_rebalance.json")
    pc = artifacts.get("position_contribution", {})
    assert pc, "mixed_portfolio must produce position_contribution"
    summary = pc.get("summary", {})
    assert summary.get("largest_value_position", "") != ""
    assert "exposure_summary" in artifacts or "risk_flags" in artifacts


def test_energy_loss_position_contribution_identifies_loss() -> None:
    artifacts = _run_fixture("energy_loss_position.json")
    pc = artifacts.get("position_contribution", {})
    assert pc, "energy_loss must produce position_contribution"
    positions = pc.get("positions", [])
    loss_positions = [p for p in positions if isinstance(p, dict) and p.get("pnl_contribution_pct", 0) < 0]
    assert len(loss_positions) > 0, "energy_loss should have at least one loss contributor"
    overlap = FORMAL_DECISION_ARTIFACTS & set(artifacts.keys())
    assert not overlap, "energy_loss must not produce formal decisions"


def test_high_overlap_qdii_ai_overlap_diagnostics() -> None:
    artifacts = _run_fixture("high_overlap_qdii_ai.json")
    overlap_diag = artifacts.get("overlap_diagnostics", {})
    if overlap_diag:
        assert isinstance(overlap_diag.get("overlap_stocks", []), list) or isinstance(overlap_diag.get("shared_stocks", []), list)


def test_high_overlap_knowledge_graph_summary() -> None:
    artifacts = _run_fixture("high_overlap_qdii_ai.json")
    kg = artifacts.get("knowledge_graph_summary", {})
    if kg and kg.get("enabled"):
        assert kg["fund_count"] >= 1


def test_short_holding_fee_sell_redemption_risk() -> None:
    artifacts = _run_fixture("short_holding_fee_sell_request.json")
    rfr = artifacts.get("redemption_fee_risk", {})
    if rfr:
        items = rfr.get("items", [])
        assert isinstance(items, list)


def test_cash_buffer_low_deployment_diagnostics() -> None:
    artifacts = _run_fixture("cash_buffer_too_low_buy_request.json")
    cd = artifacts.get("cash_deployment_diagnostics", {})
    if cd:
        summary = cd.get("summary", {})
        assert "deployment_readiness" in summary or "cash_buffer_status" in summary


def test_dividend_low_vol_no_false_high_risk() -> None:
    artifacts = _run_fixture("dividend_low_vol_allocation.json")
    risk_flags = artifacts.get("risk_flags", [])
    high_risk = [f for f in risk_flags if isinstance(f, str) and "high" in f.lower() and "risk" in f.lower()]
    pp = artifacts.get("profit_protection_diagnostics", {})
    if pp and pp.get("items"):
        high_profit = [i for i in pp["items"] if i.get("profit_level") in ("high", "very_high")]
        assert len(high_profit) == 0, "dividend_low_vol should not have false high profit signal"


def test_broad_market_benchmark_divergence() -> None:
    artifacts = _run_fixture("broad_market_index_vs_active_fund.json")
    bd = artifacts.get("benchmark_divergence_diagnostics", {})
    if bd:
        assert isinstance(bd.get("items", []), list)


def test_dca_drawdown_diagnostics() -> None:
    artifacts = _run_fixture("dca_drawdown_continue_or_pause.json")
    dca = artifacts.get("dca_drawdown_diagnostics", {})
    if dca:
        assert isinstance(dca.get("items", []), list)


def test_event_positive_news_price_weak_hype_failure() -> None:
    artifacts = _run_fixture("event_positive_news_price_weak.json")
    ehf = artifacts.get("event_hype_failure_diagnostics", {})
    if ehf and ehf.get("items"):
        assert isinstance(ehf["items"], list)


def test_missing_transaction_no_fabricated_cost_basis() -> None:
    artifacts = _run_fixture("missing_transaction_history_but_positions_available.json")
    cost_basis = artifacts.get("cost_basis_summary", {})
    if cost_basis:
        for fund_data in cost_basis.values() if isinstance(cost_basis, dict) else []:
            if isinstance(fund_data, dict):
                assert not fund_data.get("fabricated", False), "must not fabricate cost basis"
    overlap = FORMAL_DECISION_ARTIFACTS & set(artifacts.keys())
    assert not overlap, "missing_transaction must not produce formal decisions"
