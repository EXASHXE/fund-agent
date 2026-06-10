"""Import compatibility tests for the package-based fund_analysis runtime."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "examples" / "runtime_bridge_fund_analysis_input.json"


def test_fund_analysis_package_exposes_instantiable_skill() -> None:
    module = importlib.import_module("src.skills_runtime.fund_analysis")

    assert hasattr(module, "FundAnalysisSkill")
    skill = module.FundAnalysisSkill()
    assert skill.__class__.__name__ == "FundAnalysisSkill"


def test_runtime_bridge_still_runs_fund_analysis_aliases() -> None:
    input_text = INPUT.read_text(encoding="utf-8")
    output = run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text)
    assert output["ok"] is True
    assert output["skill_name"] == "fund_analysis"
    assert output["metadata"]["runtime_path"] == (
        "src.skills_runtime.fund_analysis:FundAnalysisSkill"
    )


@pytest.mark.subprocess
def test_runtime_bridge_still_runs_fund_analysis_hyphen_slug() -> None:
    import json
    proc = run_bridge_subprocess([
        "--skill", "fund-analysis",
        "--input", str(INPUT),
        "--pretty",
    ])
    assert proc.returncode == 0, proc.stderr
    output = json.loads(proc.stdout)
    assert output["ok"] is True
    assert output["skill_name"] == "fund_analysis"
