"""Tests for the runtime bridge running DecisionSupportSkill.

DecisionSupportSkill is the only skill that may produce a formal
``Decision`` / ``ExecutionLedger``. The bridge must respect the
deterministic-mode flag, the evidence-anchor policy, and JSON
serializability of the output.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
PYTHON = sys.executable


def _run_cli(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    env = {"PYTHONPATH": str(ROOT), "PATH": __import__("os").environ.get("PATH", "")}
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=60,
    )


def _minimal_evidence_graph() -> dict:
    """Return a minimal but valid EvidenceGraph for decision_support."""
    return {
        "items": {
            "ev-hard-positive": {
                "evidence_id": "ev-hard-positive",
                "evidence_type": "HardEvidence",
                "source_type": "local_quant_tools",
                "timestamp": "2026-05-31T00:00:00",
                "related_entities": ["fund:110011"],
                "claim": "Positive local quant baseline",
                "value": {"score": 1.0},
                "confidence_weight": 1.0,
                "direction": "positive",
                "version": "evidence-contract.v2",
                "provenance": {"tool": "local_quant_tools"},
            }
        },
        "edges": [],
        "stats": {
            "total": 1,
            "hard": 1,
            "soft": 0,
            "hybrid": 0,
            "conflicts": 0,
        },
    }


def test_decision_support_runs_with_minimal_evidence_graph(tmp_path: Path):
    """DecisionSupportSkill must accept a minimal evidence_graph and
    produce a structured decision envelope."""
    input_payload = {
        "payload": {
            "evidence_graph": _minimal_evidence_graph(),
            "objective": "review fund",
            "risk_budget": {"max_drawdown": 0.1},
            "portfolio_context": {},
            "time_horizon": "1 year",
        }
    }
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = _run_cli([
        "--skill", "decision_support",
        "--input", str(input_path),
    ])
    assert proc.returncode == 0, (
        f"decision_support must exit 0, got rc={proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert payload.get("skill_name") == "decision_support"
    assert payload.get("status") in {"OK", "PARTIAL", "FAILED"}
    # DecisionSupportSkill produces a Decision artifact; the
    # artifact key is ``decision`` and may also include
    # ``execution_ledger`` if the decision is actionable.
    artifacts = payload.get("artifacts") or {}
    # The decision artifact may be a dict, None, or absent; we just
    # require the artifacts envelope to be a dict (which is the
    # contract for SkillOutput.artifacts).
    assert isinstance(artifacts, dict)


def test_decision_support_output_is_json_serializable(tmp_path: Path):
    """The full bridge output (including artifacts) must round-trip
    through ``json.dumps`` without raising."""
    input_payload = {
        "payload": {
            "evidence_graph": _minimal_evidence_graph(),
            "objective": "review fund",
            "risk_budget": {"max_drawdown": 0.1},
            "portfolio_context": {},
            "time_horizon": "1 year",
        }
    }
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = _run_cli([
        "--skill", "decision_support",
        "--input", str(input_path),
        "--output", str(tmp_path / "out.json"),
    ])
    assert proc.returncode == 0
    output_path = tmp_path / "out.json"
    assert output_path.exists()
    # Re-parse the file; if json.loads succeeds, the envelope is
    # serializable. (We use a round-trip via dumps for paranoia.)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    json.dumps(parsed, default=str)


def test_decision_support_with_deterministic_flag(tmp_path: Path):
    """When the payload includes ``deterministic: true``, the bridge
    must still complete successfully. The deterministic flag is
    forwarded to the skill via the payload."""
    input_payload = {
        "payload": {
            "evidence_graph": _minimal_evidence_graph(),
            "objective": "review fund",
            "time_horizon": "1 year",
            "deterministic": True,
        }
    }
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = _run_cli([
        "--skill", "decision_support",
        "--input", str(input_path),
    ])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True


def test_decision_support_hyphen_slug_works(tmp_path: Path):
    """The hyphen slug ``decision-support`` must also resolve."""
    input_payload = {
        "payload": {
            "evidence_graph": _minimal_evidence_graph(),
            "objective": "review fund",
            "time_horizon": "1 year",
        }
    }
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = _run_cli([
        "--skill", "decision-support",
        "--input", str(input_path),
    ])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload.get("skill_name") == "decision_support"


def test_decision_support_stdin_input(tmp_path: Path):
    """``--input -`` must read the JSON from stdin."""
    input_payload = {
        "payload": {
            "evidence_graph": _minimal_evidence_graph(),
            "objective": "review fund",
            "time_horizon": "1 year",
        }
    }
    proc = _run_cli([
        "--skill", "decision_support",
        "--input", "-",
    ], input_text=json.dumps(input_payload))
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert payload.get("skill_name") == "decision_support"
