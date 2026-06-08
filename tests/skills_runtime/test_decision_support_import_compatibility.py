"""Import compatibility tests for the package-based decision_support runtime."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_import_decision_support_as_package():
    module = __import__("src.skills_runtime.decision_support", fromlist=["DecisionSupportSkill"])
    assert hasattr(module, "DecisionSupportSkill")


def test_decision_support_skill_can_be_instantiated():
    from src.skills_runtime.decision_support import DecisionSupportSkill

    instance = DecisionSupportSkill()
    assert instance is not None
    assert type(instance).__name__ == "DecisionSupportSkill"


def test_manifest_runtime_path_resolves():
    from src.skillpack.loader import load_skillpack_manifest, resolve_runtime
    from src.skills_runtime.decision_support import DecisionSupportSkill

    manifest = load_skillpack_manifest()
    spec = next(skill for skill in manifest.skills if skill.name == "decision_support")
    assert resolve_runtime(spec.runtime) is DecisionSupportSkill


def test_runtime_bridge_runs_with_underscore_slug():
    fixture = ROOT / "examples" / "decision_support" / "single_active_buy_with_evidence.json"
    proc = _run(["--skill", "decision_support", "--input", str(fixture), "--pretty"])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    envelope = json.loads(proc.stdout)
    assert envelope.get("skill_name") == "decision_support"


def test_runtime_bridge_runs_with_hyphen_slug():
    fixture = ROOT / "examples" / "decision_support" / "single_active_buy_with_evidence.json"
    proc = _run(["--skill", "decision-support", "--input", str(fixture), "--pretty"])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    envelope = json.loads(proc.stdout)
    assert envelope.get("skill_name") == "decision_support"
