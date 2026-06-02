"""Tests that the runtime bridge example payloads and commands work
as documented in ``docs/install/runtime-bridge-cli.md``.

These tests pin the documented example commands so a refactor that
breaks the example contract is caught at test time.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
SCRIPT = ROOT / "scripts" / "run_skill.py"
PYTHON = sys.executable


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_fund_analysis_example_input_loads_as_json():
    path = EXAMPLES / "runtime_bridge_fund_analysis_input.json"
    assert path.exists(), f"example input must exist: {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    # The convenience envelope shape is {task_id, step_id,
    # skill_name, payload}; we allow full SkillInput shape too.
    assert "payload" in payload, "example input must include 'payload'"


def test_decision_support_example_input_loads_as_json():
    path = EXAMPLES / "runtime_bridge_decision_support_input.json"
    assert path.exists(), f"example input must exist: {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "payload" in payload
    # Decision support requires an evidence_graph.
    eg = payload["payload"].get("evidence_graph")
    assert isinstance(eg, dict) and eg.get("items"), (
        "decision support example must include a non-empty evidence_graph"
    )


def test_documented_fund_analysis_command_works():
    """The command shown in the docs must run successfully."""
    proc = _run_cli([
        "--skill", "fund_analysis",
        "--input", "examples/runtime_bridge_fund_analysis_input.json",
        "--pretty",
    ])
    assert proc.returncode == 0, (
        f"documented fund_analysis command must succeed, got rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert payload.get("skill_name") == "fund_analysis"


def test_documented_decision_support_command_works():
    proc = _run_cli([
        "--skill", "decision_support",
        "--input", "examples/runtime_bridge_decision_support_input.json",
        "--pretty",
    ])
    assert proc.returncode == 0, (
        f"documented decision_support command must succeed, got rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert payload.get("skill_name") == "decision_support"


def test_documented_list_skills_command_works():
    proc = _run_cli(["--list-skills", "--pretty"])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert isinstance(payload.get("skills"), list)
    assert len(payload["skills"]) == 5


def test_minimal_python_host_example_runs():
    """``examples/minimal_runtime_bridge_fund_analysis.py`` must run
    end-to-end without raising."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [PYTHON, "examples/minimal_runtime_bridge_fund_analysis.py"],
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
    # The example prints a JSON envelope (possibly multi-line) to
    # stdout. Parse the entire stdout.
    text = proc.stdout.strip()
    assert text, "example must emit JSON on stdout"
    payload = json.loads(text)
    assert payload.get("ok") is True, (
        f"example envelope must report ok=true, got {payload!r}"
    )
