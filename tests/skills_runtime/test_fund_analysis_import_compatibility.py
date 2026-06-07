"""Import compatibility tests for the package-based fund_analysis runtime."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
INPUT = ROOT / "examples" / "runtime_bridge_fund_analysis_input.json"


def test_fund_analysis_package_exposes_instantiable_skill() -> None:
    module = importlib.import_module("src.skills_runtime.fund_analysis")

    assert hasattr(module, "FundAnalysisSkill")
    skill = module.FundAnalysisSkill()
    assert skill.__class__.__name__ == "FundAnalysisSkill"


def _run_bridge(skill_name: str) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--skill",
            skill_name,
            "--input",
            str(INPUT),
            "--pretty",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip()
    return json.loads(proc.stdout)


@pytest.mark.parametrize("skill_name", ["fund_analysis", "fund-analysis"])
def test_runtime_bridge_still_runs_fund_analysis_aliases(skill_name: str) -> None:
    output = _run_bridge(skill_name)

    assert output["ok"] is True
    assert output["skill_name"] == "fund_analysis"
    assert output["metadata"]["runtime_path"] == (
        "src.skills_runtime.fund_analysis:FundAnalysisSkill"
    )
