"""Unit tests for professional diagnostics rules in fund_analysis."""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.skill import SkillInput
from src.skills_runtime.fund_analysis import FundAnalysisSkill


def _make_skill_input() -> SkillInput:
    return SkillInput(
        task_id="test-diag", step_id="fa-diag",
        skill_name="fund_analysis", payload={},
    )
from src.skills_runtime.fund_analysis.professional_rules import (
    compute_redemption_fee_risk,
    compute_overlap_diagnostics,
    compute_theme_overweight_diagnostics,
    compute_dca_drawdown_diagnostics,
    compute_cash_budget_diagnostics,
    run_professional_diagnostics,
)
from src.skills_runtime.fund_analysis.input_stage import (
    build_portfolio_input_bundle,
    collect_fund_codes,
    dict_or_empty,
)
from src.skills_runtime.fund_analysis.metrics_stage import compute_core_metrics

ROOT = Path(__file__).resolve().parents[2]


def _load_scenario(name: str) -> dict:
    return json.loads((ROOT / "examples" / "scenarios" / name).read_text(encoding="utf-8"))


def _bundle_from_payload(payload: dict) -> tuple:
    portfolio = dict_or_empty(payload.get("portfolio"))
    positions = portfolio.get("positions", [])
    fund_codes = collect_fund_codes(positions)
    bundle = build_portfolio_input_bundle(
        payload=payload,
        portfolio=portfolio,
        positions=positions,
        fund_codes=fund_codes,
    )
    return bundle, fund_codes


def test_redemption_fee_risk_from_7d_fixture():
    payload = _load_scenario("cn_fund_7d_redemption_fee.json")["payload"]
    bundle, _ = _bundle_from_payload(payload)
    metrics = compute_core_metrics(bundle, [], _make_skill_input())
    result = compute_redemption_fee_risk(bundle, metrics)
    assert result is not None
    assert "affected_funds" in result
    assert len(result["affected_funds"]) >= 1
    syn7d = [f for f in result["affected_funds"] if f["fund_code"] == "SYN7D001"]
    assert len(syn7d) >= 1


def test_overlap_from_qdii_sp500_fixture():
    payload = _load_scenario("cn_fund_qdii_sp500_overlap.json")["payload"]
    bundle, _ = _bundle_from_payload(payload)
    metrics = compute_core_metrics(bundle, [], _make_skill_input())
    result = compute_overlap_diagnostics(bundle, metrics)
    assert result is not None
    assert "overlapping_holdings" in result
    assert "overlapping_themes" in result


def test_theme_overweight_from_ai_semiconductor_fixture():
    payload = _load_scenario("cn_fund_ai_semiconductor_overweight.json")["payload"]
    bundle, _ = _bundle_from_payload(payload)
    metrics = compute_core_metrics(bundle, [], _make_skill_input())
    result = compute_theme_overweight_diagnostics(bundle, metrics)
    assert result is not None
    assert "overweight_themes" in result
    assert len(result["overweight_themes"]) >= 1
    themes = {t["theme"] for t in result["overweight_themes"]}
    assert "ai_semiconductor" in themes or "semiconductor" in themes


def test_dca_drawdown_from_dca_fixture():
    payload = _load_scenario("cn_fund_dca_drawdown_review.json")["payload"]
    bundle, _ = _bundle_from_payload(payload)
    metrics = compute_core_metrics(bundle, [], _make_skill_input())
    result = compute_dca_drawdown_diagnostics(bundle, metrics)
    assert result is not None
    assert "reviewed_funds" in result


def test_cash_budget_diagnostics_for_low_cash():
    payload = _load_scenario("cn_fund_ai_semiconductor_overweight.json")["payload"]
    bundle, _ = _bundle_from_payload(payload)
    metrics = compute_core_metrics(bundle, [], _make_skill_input())
    result = compute_cash_budget_diagnostics(bundle, metrics)
    assert result is not None
    assert "cash_ratio" in result
    assert result["cash_ratio"] < 0.1  # low cash scenario


def test_diagnostics_are_deterministic():
    payload = _load_scenario("cn_fund_7d_redemption_fee.json")["payload"]
    bundle, _ = _bundle_from_payload(payload)
    metrics = compute_core_metrics(bundle, [], _make_skill_input())
    r1 = compute_redemption_fee_risk(bundle, metrics)
    r2 = compute_redemption_fee_risk(bundle, metrics)
    assert r1 == r2


def test_run_all_diagnostics():
    payload = _load_scenario("cn_fund_qdii_sp500_overlap.json")["payload"]
    bundle, _ = _bundle_from_payload(payload)
    metrics = compute_core_metrics(bundle, [], _make_skill_input())
    warnings: list[str] = []
    diag = run_professional_diagnostics(bundle=bundle, metrics=metrics, warnings=warnings)
    assert "professional_warnings" in diag
    assert isinstance(diag.get("professional_warnings"), list)


def test_fund_analysis_artifacts_include_professional_diagnostics():
    payload = _load_scenario("cn_fund_qdii_sp500_overlap.json")["payload"]
    si = SkillInput(
        task_id="test-diag", step_id="fa-diag",
        skill_name="fund_analysis", payload=payload,
    )
    output = FundAnalysisSkill().run(si)
    artifacts = output.artifacts
    assert "professional_diagnostics" in artifacts
    assert "overlap_diagnostics" in artifacts or "redemption_fee_risk" in artifacts


def test_fund_analysis_no_formal_decisions_in_diagnostics():
    payload = _load_scenario("cn_fund_qdii_sp500_overlap.json")["payload"]
    si = SkillInput(
        task_id="test-diag-formal", step_id="fa-diag-formal",
        skill_name="fund_analysis", payload=payload,
    )
    output = FundAnalysisSkill().run(si)
    artifacts = output.artifacts
    assert "decision" not in artifacts
    assert "decisions" not in artifacts
    assert "execution_ledger" not in artifacts


def test_professional_warnings_not_duplicated():
    """Professional warnings must appear only once in output.warnings and artifacts.warnings."""
    payload = _load_scenario("cn_fund_qdii_sp500_overlap.json")["payload"]
    si = SkillInput(
        task_id="test-dedup", step_id="fa-dedup",
        skill_name="fund_analysis", payload=payload,
    )
    output = FundAnalysisSkill().run(si)

    output_warnings = output.warnings or []
    artifact_warnings = output.artifacts.get("warnings") or []

    # Check no exact duplicates in output warnings
    assert len(output_warnings) == len(set(output_warnings)), (
        f"Duplicate strings in output.warnings: {output_warnings}"
    )

    # Check no exact duplicates in artifact warnings
    artifact_strs = [str(w) for w in artifact_warnings if w is not None]
    assert len(artifact_strs) == len(set(artifact_strs)), (
        f"Duplicate strings in artifacts.warnings: {artifact_strs}"
    )
