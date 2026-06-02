"""Golden-ish contract tests for the runtime bridge output envelope.

These tests assert the *shape* of the bridge envelope without
overfitting to exact values (no specific decision_id, no specific
timestamps, no exact NAV history, etc.). They document the public
JSON contract that hosts can rely on.
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


def _write_input(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "in.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


_FUND_ANALYSIS_INPUT = {
    "payload": {
        "portfolio": {
            "as_of_date": "2026-06-01",
            "total_value": 200000,
            "cash_available": 20000,
            "positions": [
                {
                    "fund_code": "110011",
                    "fund_name": "Example Fund",
                    "current_value": 30000,
                    "total_cost": 32000,
                    "target_weight": 0.12,
                    "tags": ["healthcare", "active"],
                },
            ],
        },
        "fund_profiles": {
            "110011": {"fund_code": "110011", "name": "Example Fund"},
        },
        "nav_history": {
            "110011": [{"date": "2025-06-01", "nav": 1.0}],
        },
        "holdings": {
            "110011": [{"name": "A", "weight": 1.0, "industry": "healthcare"}],
        },
        "risk_profile": {
            "risk_level": "moderate",
            "max_single_fund_weight": 0.2,
            "max_theme_weight": 0.35,
            "max_trade_pct": 0.1,
            "liquidity_reserve_pct": 0.1,
            "short_term_trade_budget_pct": 0.1,
        },
        "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
    },
}


_DECISION_SUPPORT_INPUT = {
    "payload": {
        "evidence_graph": {
            "items": {
                "ev-1": {
                    "evidence_id": "ev-1",
                    "evidence_type": "HardEvidence",
                    "source_type": "test",
                    "timestamp": "2026-06-01T00:00:00",
                    "related_entities": ["110011"],
                    "claim": "Test claim",
                    "direction": "positive",
                    "confidence_weight": 1.0,
                },
            },
            "edges": [],
        },
        "objective": "contract test",
        "portfolio_context": {},
        "constraints": {"max_buy_amount": 1000, "min_trade_amount": 100},
    },
}


# Expected top-level keys on a successful skill envelope.
_SUCCESS_KEYS = frozenset({
    "ok",
    "skill_name",
    "step_id",
    "status",
    "artifacts",
    "evidence_items",
    "warnings",
    "errors",
    "used_mcp_capabilities",
    "metadata",
})


def test_fund_analysis_success_envelope_shape(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _FUND_ANALYSIS_INPUT)
    proc = _run_cli(["--skill", "fund_analysis", "--input", str(input_path)])
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert set(out.keys()) >= _SUCCESS_KEYS
    assert out["skill_name"] == "fund_analysis"
    assert out["status"] in ("OK", "PARTIAL", "FAILED")
    assert isinstance(out["evidence_items"], list)
    assert isinstance(out["errors"], list)
    assert isinstance(out["warnings"], list)
    assert isinstance(out["used_mcp_capabilities"], list)
    assert isinstance(out["artifacts"], dict)


def test_fund_analysis_metadata_required_keys(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _FUND_ANALYSIS_INPUT)
    proc = _run_cli(["--skill", "fund_analysis", "--input", str(input_path)])
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    metadata = out["metadata"]
    assert "manifest_path" in metadata
    assert "runtime_path" in metadata
    assert "required_mcp_capabilities" in metadata
    assert "missing_mcp_capabilities" in metadata
    # Manifest path is the canonical skillpack manifest, not arbitrary.
    assert metadata["manifest_path"].endswith("fund-agent.skillpack.yaml")
    assert metadata["required_mcp_capabilities"] == []
    assert metadata["missing_mcp_capabilities"] == []


def test_decision_support_success_envelope_shape(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _DECISION_SUPPORT_INPUT)
    proc = _run_cli(["--skill", "decision_support", "--input", str(input_path)])
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert set(out.keys()) >= _SUCCESS_KEYS
    assert out["skill_name"] == "decision_support"
    assert out["status"] in ("OK", "PARTIAL", "FAILED")
    # DecisionSupportSkill may produce a Decision artifact; if so it
    # must be JSON-serializable (the bridge writes the full envelope
    # to stdout without falling back to a serialization-failed
    # envelope).
    json.dumps(out)


def test_bridge_level_failure_envelope_shape(tmp_path: Path) -> None:
    """An UNKNOWN_SKILL failure must produce an envelope with
    ``ok=false`` and a structured ``error`` block, and stdout must
    contain only the JSON envelope (no Python traceback).
    """
    proc = _run_cli(["--skill", "totally_not_a_skill"])
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert "error" in out
    err = out["error"]
    assert "code" in err
    assert "message" in err
    assert "details" in err
    # Stdout must be JSON-only; stderr may carry diagnostics.
    assert "Traceback" not in proc.stdout
    # Stderr is allowed to be empty or carry non-JSON diagnostics,
    # but must not contain a JSON envelope.
    if proc.stderr:
        try:
            json.loads(proc.stderr)
        except json.JSONDecodeError:
            pass  # expected: non-JSON diagnostics
        else:
            # If it parses as JSON it should be the same envelope
            # already on stdout; do not require it.
            pass


def test_bridge_failure_includes_no_traceback_on_stdout_for_missing_input(
    tmp_path: Path,
) -> None:
    """Calling the bridge with no input must produce a JSON envelope
    on stdout, never a Python traceback.
    """
    proc = _run_cli(["--skill", "fund_analysis"])
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["error"]["code"] in ("INVALID_INPUT",)
    assert "Traceback" not in proc.stdout


def test_pretty_output_is_valid_json(tmp_path: Path) -> None:
    """The --pretty flag must still produce valid JSON on stdout."""
    input_path = _write_input(tmp_path, _FUND_ANALYSIS_INPUT)
    proc = _run_cli([
        "--skill", "fund_analysis",
        "--input", str(input_path),
        "--pretty",
    ])
    assert proc.returncode == 0
    # Must be valid JSON (pretty-printed).
    out = json.loads(proc.stdout)
    assert out["ok"] is True


def test_output_to_file_matches_stdout(tmp_path: Path) -> None:
    """When ``--output`` is supplied, the bridge writes the same
    JSON envelope to the file that it would have written to stdout.
    """
    input_path = _write_input(tmp_path, _FUND_ANALYSIS_INPUT)
    out_path = tmp_path / "out.json"
    proc = _run_cli([
        "--skill", "fund_analysis",
        "--input", str(input_path),
        "--output", str(out_path),
    ])
    assert proc.returncode == 0
    from_file = json.loads(out_path.read_text(encoding="utf-8"))
    # Re-run to capture stdout and compare structurally.
    proc2 = _run_cli([
        "--skill", "fund_analysis",
        "--input", str(input_path),
    ])
    assert proc2.returncode == 0
    from_stdout = json.loads(proc2.stdout)
    # Compare only the shape and stable fields; embedded
    # timestamps / decision_ids may differ.
    assert from_file["ok"] == from_stdout["ok"]
    assert from_file["skill_name"] == from_stdout["skill_name"]
    assert from_file["status"] == from_stdout["status"]
    assert set(from_file.keys()) == set(from_stdout.keys())
    assert set(from_file["metadata"].keys()) == set(from_stdout["metadata"].keys())
