"""Golden-ish contract tests for the runtime bridge output envelope.

These tests assert the *shape* of the bridge envelope without
overfitting to exact values (no specific decision_id, no specific
timestamps, no exact NAV history, etc.). They document the public
JSON contract that hosts can rely on.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]


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


def test_fund_analysis_success_envelope_shape() -> None:
    out = run_bridge_inprocess_json(skill="fund_analysis", input_data=_FUND_ANALYSIS_INPUT)
    assert out["ok"] is True
    assert set(out.keys()) >= _SUCCESS_KEYS
    assert out["skill_name"] == "fund_analysis"
    assert out["status"] in ("OK", "PARTIAL", "FAILED")
    assert isinstance(out["evidence_items"], list)
    assert isinstance(out["errors"], list)
    assert isinstance(out["warnings"], list)
    assert isinstance(out["used_mcp_capabilities"], list)
    assert isinstance(out["artifacts"], dict)


def test_fund_analysis_metadata_required_keys() -> None:
    out = run_bridge_inprocess_json(skill="fund_analysis", input_data=_FUND_ANALYSIS_INPUT)
    metadata = out["metadata"]
    assert "manifest_path" in metadata
    assert "runtime_path" in metadata
    assert "required_mcp_capabilities" in metadata
    assert "missing_mcp_capabilities" in metadata
    assert metadata["manifest_path"].endswith("fund-agent.skillpack.yaml")
    assert metadata["required_mcp_capabilities"] == []
    assert metadata["missing_mcp_capabilities"] == []


def test_decision_support_success_envelope_shape() -> None:
    out = run_bridge_inprocess_json(skill="decision_support", input_data=_DECISION_SUPPORT_INPUT)
    assert out["ok"] is True
    assert set(out.keys()) >= _SUCCESS_KEYS
    assert out["skill_name"] == "decision_support"
    assert out["status"] in ("OK", "PARTIAL", "FAILED")
    json.dumps(out)


@pytest.mark.subprocess
def test_bridge_level_failure_envelope_shape() -> None:
    proc = run_bridge_subprocess(["--skill", "totally_not_a_skill"])
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert "error" in out
    err = out["error"]
    assert "code" in err
    assert "message" in err
    assert "details" in err
    assert "Traceback" not in proc.stdout
    if proc.stderr:
        try:
            json.loads(proc.stderr)
        except json.JSONDecodeError:
            pass


@pytest.mark.subprocess
def test_bridge_failure_includes_no_traceback_on_stdout_for_missing_input() -> None:
    proc = run_bridge_subprocess(["--skill", "fund_analysis"])
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert out["error"]["code"] in ("INVALID_INPUT",)
    assert "Traceback" not in proc.stdout


@pytest.mark.subprocess
def test_pretty_output_is_valid_json() -> None:
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(_FUND_ANALYSIS_INPUT, f)
        f.flush()
        path = f.name
    proc = run_bridge_subprocess(["--skill", "fund_analysis", "--input", path, "--pretty"])
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True


@pytest.mark.subprocess
def test_output_to_file_matches_stdout() -> None:
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(_FUND_ANALYSIS_INPUT, f)
        f.flush()
        input_path = f.name
    out_path = tempfile.mktemp(suffix=".json")
    proc = run_bridge_subprocess(["--skill", "fund_analysis", "--input", input_path, "--output", out_path])
    assert proc.returncode == 0
    from_file = json.loads(Path(out_path).read_text(encoding="utf-8"))
    proc2 = run_bridge_subprocess(["--skill", "fund_analysis", "--input", input_path])
    assert proc2.returncode == 0
    from_stdout = json.loads(proc2.stdout)
    assert from_file["ok"] == from_stdout["ok"]
    assert from_file["skill_name"] == from_stdout["skill_name"]
    assert from_file["status"] == from_stdout["status"]
    assert set(from_file.keys()) == set(from_stdout.keys())
    assert set(from_file["metadata"].keys()) == set(from_stdout["metadata"].keys())
