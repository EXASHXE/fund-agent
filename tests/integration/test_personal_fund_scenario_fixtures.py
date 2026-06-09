"""Integration tests for fake personal fund scenario fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import parse_json_stdout, run_bridge
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


def _run(args: list[str]):
    return run_bridge(args)


def _load_json_output(proc) -> dict:
    return parse_json_stdout(proc)


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_exists_and_uses_payload_envelope(fixture_name: str) -> None:
    path = SCENARIO_DIR / fixture_name
    assert path.exists()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"payload"}
    assert isinstance(data["payload"], dict)


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_validates_successfully(fixture_name: str) -> None:
    path = SCENARIO_DIR / fixture_name
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(path),
        "--validate-input",
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr

    out = _load_json_output(proc)
    result = out["validation_result"]
    assert out["ok"] is True
    assert result["valid"] is True
    assert result["severity"] in {"OK", "PARTIAL"}
    assert result["severity"] != "INVALID"


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_runs_without_formal_decision_artifacts(
    fixture_name: str,
) -> None:
    path = SCENARIO_DIR / fixture_name
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(path),
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr

    out = _load_json_output(proc)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert out["status"] in {"OK", "PARTIAL"}

    artifacts = out["artifacts"]
    assert isinstance(artifacts, dict)
    assert_no_formal_decision_artifacts(artifacts)

    report_sections = artifacts.get("report_sections")
    if report_sections is not None:
        assert isinstance(report_sections, list)
        assert report_sections
        assert artifacts.get("report_outline")
        assert artifacts.get("report_quality_gate")


@pytest.mark.parametrize("fixture_name", SCENARIO_FIXTURES)
def test_scenario_fixture_emit_report_markdown_when_sections_exist(
    fixture_name: str,
    tmp_path: Path,
) -> None:
    path = SCENARIO_DIR / fixture_name
    run_proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(path),
        "--pretty",
    ])
    assert run_proc.returncode == 0, run_proc.stderr
    run_out = _load_json_output(run_proc)
    if not run_out["artifacts"].get("report_sections"):
        return

    report_path = tmp_path / f"{path.stem}.md"
    proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(path),
        "--emit-report",
        "markdown",
        "--output",
        str(report_path),
    ])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""

    text = report_path.read_text(encoding="utf-8")
    assert text.startswith("# Personal fund report\n")
    assert "## Executive summary" in text
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


def test_ledger_derived_scenario_detects_mode_and_surfaces_current_artifacts() -> None:
    path = SCENARIO_DIR / "cn_fund_ledger_derived_snapshot.json"

    validate_proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(path),
        "--validate-input",
        "--pretty",
    ])
    assert validate_proc.returncode == 0, validate_proc.stderr
    validation = _load_json_output(validate_proc)["validation_result"]
    assert validation["detected_input_mode"] == "ledger_derived"

    run_proc = _run([
        "--skill",
        "fund_analysis",
        "--input",
        str(path),
        "--pretty",
    ])
    assert run_proc.returncode == 0, run_proc.stderr
    out = _load_json_output(run_proc)
    assert out["ok"] is True

    artifacts = out["artifacts"]
    emitted = LEDGER_DERIVED_ARTIFACTS & set(artifacts)
    assert emitted, (
        "ledger_derived run succeeded but emitted no current ledger-derived "
        "artifacts; update this test if that becomes the documented behavior"
    )


# ── Scenario-specific diagnostic assertions ────────────────────────────────

def test_cn_fund_7d_redemption_fee_emits_redemption_fee_risk():
    path = SCENARIO_DIR / "cn_fund_7d_redemption_fee.json"
    proc = _run(["--skill", "fund_analysis", "--input", str(path), "--pretty"])
    artifacts = _load_json_output(proc)["artifacts"]
    assert "redemption_fee_risk" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_qdii_sp500_overlap_emits_overlap_diagnostics():
    path = SCENARIO_DIR / "cn_fund_qdii_sp500_overlap.json"
    proc = _run(["--skill", "fund_analysis", "--input", str(path), "--pretty"])
    artifacts = _load_json_output(proc)["artifacts"]
    assert "overlap_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_ai_semiconductor_overweight_emits_theme_overweight():
    path = SCENARIO_DIR / "cn_fund_ai_semiconductor_overweight.json"
    proc = _run(["--skill", "fund_analysis", "--input", str(path), "--pretty"])
    artifacts = _load_json_output(proc)["artifacts"]
    assert "theme_overweight_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_dca_drawdown_review_emits_dca_diagnostics():
    path = SCENARIO_DIR / "cn_fund_dca_drawdown_review.json"
    proc = _run(["--skill", "fund_analysis", "--input", str(path), "--pretty"])
    artifacts = _load_json_output(proc)["artifacts"]
    assert "dca_drawdown_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)


def test_cn_fund_ledger_derived_snapshot_emits_cash_budget_diagnostics():
    path = SCENARIO_DIR / "cn_fund_ledger_derived_snapshot.json"
    proc = _run(["--skill", "fund_analysis", "--input", str(path), "--pretty"])
    artifacts = _load_json_output(proc)["artifacts"]
    assert "cash_budget_diagnostics" in artifacts
    assert "professional_diagnostics" in artifacts
    assert_no_formal_decision_artifacts(artifacts)
