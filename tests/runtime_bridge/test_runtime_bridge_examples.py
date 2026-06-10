"""Tests that the runtime bridge example payloads and commands work
as documented in ``docs/install/runtime-bridge-cli.md``.

These tests pin the documented example commands so a refactor that
breaks the example contract is caught at test time.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json, run_bridge_inprocess_metadata, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def test_fund_analysis_example_input_loads_as_json():
    path = EXAMPLES / "runtime_bridge_fund_analysis_input.json"
    assert path.exists(), f"example input must exist: {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "payload" in payload, "example input must include 'payload'"


def test_decision_support_example_input_loads_as_json():
    path = EXAMPLES / "runtime_bridge_decision_support_input.json"
    assert path.exists(), f"example input must exist: {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "payload" in payload
    eg = payload["payload"].get("evidence_graph")
    assert isinstance(eg, dict) and eg.get("items"), (
        "decision support example must include a non-empty evidence_graph"
    )


def test_documented_fund_analysis_command_works():
    input_text = (EXAMPLES / "runtime_bridge_fund_analysis_input.json").read_text(encoding="utf-8")
    payload = run_bridge_inprocess_json(skill="fund_analysis", input_text=input_text)
    assert payload.get("ok") is True
    assert payload.get("skill_name") == "fund_analysis"


def test_documented_decision_support_command_works():
    input_text = (EXAMPLES / "runtime_bridge_decision_support_input.json").read_text(encoding="utf-8")
    payload = run_bridge_inprocess_json(skill="decision_support", input_text=input_text)
    assert payload.get("ok") is True
    assert payload.get("skill_name") == "decision_support"


def test_documented_list_skills_command_works():
    payload = run_bridge_inprocess_metadata(list_skills=True, pretty=True)
    assert payload.get("ok") is True
    assert isinstance(payload.get("skills"), list)
    assert len(payload["skills"]) == 5


@pytest.mark.subprocess
def test_minimal_python_host_example_runs():
    import os
    import subprocess
    import sys
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "examples/minimal_runtime_bridge_fund_analysis.py"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"minimal python host example must exit 0, got rc={proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    text = proc.stdout.strip()
    assert text, "example must emit JSON on stdout"
    payload = json.loads(text)
    assert payload.get("ok") is True, (
        f"example envelope must report ok=true, got {payload!r}"
    )
