"""Integration tests for fake personal fund scenario fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import (
    run_bridge_inprocess_json,
    run_bridge_inprocess_metadata,
    run_bridge_inprocess_text,
    run_bridge_subprocess,
)
from tests.support.formal_boundary import assert_no_formal_decision_artifacts

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "examples" / "scenarios"

SCENARIO_FIXTURES = [
    "cn_fund_7d_redemption_fee.json",
    "cn_fund_qdii_sp500_overlap.json",
    "cn_fund_ai_semiconductor_overweight.json",
    "cn_fund_dca_drawdown_review.json",
    "cn_fund_ledger_derived_snapshot.json",
]

LEDGER_DERIVED_ARTIFACTS = {
    "derived_portfolio_snapshot",
    "source_of_truth",
    "ledger_cashflow_summary",
    "ledger_quality_summary",
}


def _run_fund_analysis(fixture_name: str) -> dict:
    input_text = (SCENARIO_DIR / fixture_name).read_text(encoding="utf-8")
    return run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text)


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_exists_and_uses_payload_envelope(fixture_name: str) -> None:
    path = SCENARIO_DIR / fixture_name
    assert path.exists()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"payload"}
    assert isinstance(data["payload"], dict)


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_validates_successfully(fixture_name: str) -> None:
    input_text = (SCENARIO_DIR / fixture_name).read_text(encoding="utf-8")
    out = run_bridge_inprocess_metadata(
        skill="fund_analysis",
        validate_input=True,
        input_text=input_text,
        pretty=True,
    )
    result = out["validation_result"]
    assert out["ok"] is True
    assert result["valid"] is True
    assert result["severity"] in {"OK", "PARTIAL"}
    assert result["severity"] != "INVALID"


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_runs_without_formal_decision_artifacts(
    fixture_name: str,
) -> None:
    out = _run_fund_analysis(fixture_name)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert out["status"] in {"OK", "PARTIAL"}

    artifacts = out["artifacts"]
    assert isinstance(artifacts, dict)
    assert_no_formal_decision_artifacts(artifacts)

    report_sections = artifacts.get("report_sections")
    assert isinstance(report_sections, list)
    assert report_sections
    assert artifacts.get("report_outline")
    assert artifacts.get("report_quality_gate")


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_emit_report_markdown_when_sections_exist(
    fixture_name: str,
) -> None:
    path = SCENARIO_DIR / fixture_name
    run_out = _run_fund_analysis(fixture_name)
    if not run_out["artifacts"].get("report_sections"):
        return

    input_text = path.read_text(encoding="utf-8")
    raw = run_bridge_inprocess_text(
        skill="fund_analysis",
        input_text=input_text,
        emit_report="markdown",
    )
    text = raw.replace("\r\n", "\n")
    assert text.startswith("# Personal fund report\n")
    assert "## Executive summary" in text
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


def test_ledger_derived_scenario_detects_mode_and_surfaces_current_artifacts() -> None:
    input_text = (SCENARIO_DIR / "cn_fund_ledger_derived_snapshot.json").read_text(encoding="utf-8")

    validation_out = run_bridge_inprocess_metadata(
        skill="fund_analysis",
        validate_input=True,
        input_text=input_text,
        pretty=True,
    )
    validation = validation_out["validation_result"]
    assert validation["detected_input_mode"] == "ledger_derived"

    out = run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text)
    assert out["ok"] is True

    artifacts = out["artifacts"]
    emitted = LEDGER_DERIVED_ARTIFACTS & set(artifacts)
    assert emitted, (
        "ledger_derived run succeeded but emitted no current ledger-derived "
        "artifacts; update this test if that becomes the documented behavior"
    )


# ── Scenario-specific diagnostic assertions ────────────────────────────────

def test_cn_fund_7d_redemption_fee_emits_redemption_fee_risk():
    artifacts = _run_fund_analysis("cn_fund_7d_redemption_fee.json")["artifacts"]
    assert "redemption_fee_risk" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_qdii_sp500_overlap_emits_overlap_diagnostics():
    artifacts = _run_fund_analysis("cn_fund_qdii_sp500_overlap.json")["artifacts"]
    assert "overlap_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_ai_semiconductor_overweight_emits_theme_overweight():
    artifacts = _run_fund_analysis("cn_fund_ai_semiconductor_overweight.json")["artifacts"]
    assert "theme_overweight_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_dca_drawdown_review_emits_dca_diagnostics():
    artifacts = _run_fund_analysis("cn_fund_dca_drawdown_review.json")["artifacts"]
    assert "dca_drawdown_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_ledger_derived_snapshot_emits_cash_budget_diagnostics():
    artifacts = _run_fund_analysis("cn_fund_ledger_derived_snapshot.json")["artifacts"]
    assert "cash_budget_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)
