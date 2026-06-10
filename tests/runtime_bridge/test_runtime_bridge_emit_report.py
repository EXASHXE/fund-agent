"""Runtime bridge tests for explicit Markdown report emission."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schemas.skill import SkillInput, SkillOutput
from tests.support.bridge_runner import run_bridge_inprocess_json, run_bridge_inprocess_metadata, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]
REPORT_INPUT = ROOT / "examples" / "runtime_bridge_personal_report_quality_input.json"


def _assert_not_json(text: str) -> None:
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)


@pytest.mark.subprocess
def test_emit_report_markdown_writes_markdown_to_stdout() -> None:
    proc = run_bridge_subprocess([
        "--skill", "fund_analysis",
        "--input", str(REPORT_INPUT),
        "--emit-report", "markdown",
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("# Personal fund report\n")
    assert "## Executive summary" in proc.stdout
    assert "## Limitations" in proc.stdout
    _assert_not_json(proc.stdout)


@pytest.mark.subprocess
def test_emit_report_markdown_accepts_hyphenated_slug() -> None:
    proc = run_bridge_subprocess([
        "--skill", "fund-analysis",
        "--input", str(REPORT_INPUT),
        "--emit-report", "markdown",
    ])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("# Personal fund report\n")
    assert "## Portfolio snapshot" in proc.stdout


@pytest.mark.subprocess
def test_emit_report_markdown_output_file_contains_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "report.md"
    proc = run_bridge_subprocess([
        "--skill", "fund_analysis",
        "--input", str(REPORT_INPUT),
        "--emit-report", "markdown",
        "--output", str(output_path),
    ])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    text = output_path.read_text(encoding="utf-8")
    assert text.startswith("# Personal fund report\n")
    assert "## Executive summary" in text
    _assert_not_json(text)


def test_normal_runtime_bridge_command_still_returns_json() -> None:
    input_text = REPORT_INPUT.read_text(encoding="utf-8")
    out = run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text)
    assert out["ok"] is True
    assert out["skill_name"] == "fund_analysis"
    assert "report_sections" in out["artifacts"]


def test_metadata_commands_still_return_json() -> None:
    commands = [
        lambda: run_bridge_inprocess_metadata(list_skills=True),
        lambda: run_bridge_inprocess_metadata(list_skills=True),
        lambda: run_bridge_inprocess_metadata(skill="fund_analysis", explain_input=True),
        lambda: run_bridge_inprocess_metadata(
            skill="fund_analysis",
            validate_input=True,
            input_text=REPORT_INPUT.read_text(encoding="utf-8"),
        ),
        lambda: run_bridge_inprocess_metadata(skill="fund_analysis", output_schema=True),
    ]
    for cmd in commands:
        out = cmd()
        assert out["ok"] is True


def test_non_fund_analysis_emit_report_returns_json_error() -> None:
    ds_input_path = ROOT / "examples" / "runtime_bridge_decision_support_input.json"
    if not ds_input_path.exists():
        pytest.skip("decision support example not found")
    input_text = ds_input_path.read_text(encoding="utf-8")
    out = run_bridge_inprocess_json(
        skill="decision_support",
        input_text=input_text,
        emit_report="markdown",
    )
    assert out["ok"] is False
    assert out["error"]["code"] == "UNSUPPORTED_EMIT_REPORT"


def test_emit_report_missing_report_sections_returns_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from src.skillpack import run_skill as bridge

    class FakeFundAnalysisSkill:
        def run(self, skill_input: SkillInput) -> SkillOutput:
            return SkillOutput(
                step_id=skill_input.step_id,
                skill_name=skill_input.skill_name,
                artifacts={"portfolio_summary": {"total_value": 1}},
                status="OK",
            )

    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps({"payload": {"related_entities": ["fund:110011"]}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bridge, "resolve_runtime", lambda _: FakeFundAnalysisSkill)

    rc = bridge.run_bridge(
        skill_name="fund_analysis",
        input_path=str(input_path),
        emit_report="markdown",
        pretty=True,
    )

    captured = capsys.readouterr()
    assert rc == 2
    out = json.loads(captured.out)
    assert out["ok"] is False
    assert out["error"]["code"] == "MISSING_REPORT_SECTIONS"
    assert out["error"]["details"]["available_artifact_keys"] == [
        "portfolio_summary",
    ]


@pytest.mark.subprocess
def test_emit_report_markdown_includes_professional_diagnostics_heading() -> None:
    fixture = ROOT / "examples" / "scenarios" / "cn_fund_7d_redemption_fee.json"
    proc = run_bridge_subprocess([
        "--skill", "fund_analysis",
        "--input", str(fixture),
        "--emit-report", "markdown",
    ])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("# Personal fund report\n")
    assert "## Professional diagnostics" in proc.stdout
    assert "## Decision" not in proc.stdout
    assert "## Execution ledger" not in proc.stdout
    _assert_not_json(proc.stdout)
