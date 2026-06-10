"""Tests for the runtime bridge running DecisionSupportSkill.

DecisionSupportSkill is the only skill that may produce a formal
``Decision`` / ``ExecutionLedger``. The bridge must respect the
deterministic-mode flag, the evidence-anchor policy, and JSON
serializability of the output.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]


def _minimal_evidence_graph() -> dict:
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


def _ds_input(**extra) -> dict:
    payload = {
        "evidence_graph": _minimal_evidence_graph(),
        "objective": "review fund",
        "risk_budget": {"max_drawdown": 0.1},
        "portfolio_context": {},
        "time_horizon": "1 year",
    }
    payload.update(extra)
    return {"payload": payload}


def test_decision_support_runs_with_minimal_evidence_graph():
    out = run_bridge_inprocess_json(skill="decision_support", input_data=_ds_input())
    assert out.get("ok") is True
    assert out.get("skill_name") == "decision_support"
    assert out.get("status") in {"OK", "PARTIAL", "FAILED"}
    artifacts = out.get("artifacts") or {}
    assert isinstance(artifacts, dict)


def test_decision_support_output_is_json_serializable():
    out = run_bridge_inprocess_json(skill="decision_support", input_data=_ds_input())
    json.dumps(out, default=str)


def test_decision_support_with_deterministic_flag():
    out = run_bridge_inprocess_json(
        skill="decision_support",
        input_data=_ds_input(deterministic=True),
    )
    assert out.get("ok") is True


@pytest.mark.subprocess
def test_decision_support_hyphen_slug_works(tmp_path: Path):
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(_ds_input()), encoding="utf-8")
    proc = run_bridge_subprocess([
        "--skill", "decision-support",
        "--input", str(input_path),
    ])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload.get("skill_name") == "decision_support"


def test_decision_support_stdin_input():
    out = run_bridge_inprocess_json(
        skill="decision_support",
        input_text=json.dumps(_ds_input()),
    )
    assert out.get("ok") is True
    assert out.get("skill_name") == "decision_support"
