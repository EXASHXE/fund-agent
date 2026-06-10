"""Tests for the v0.4.7-dev runtime bridge CLI.

The runtime bridge is a thin local JSON-in / JSON-out CLI over the
existing manifest runtime skills. It is not an agent loop, not a
provider integration, and not a server. It does not fetch data, does
not import provider SDKs, and does not shell out to OpenCode.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.support.bridge_runner import run_bridge_inprocess_json, run_bridge_subprocess


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"


def test_bridge_script_exists():
    assert SCRIPT.exists(), f"runtime bridge script must exist at {SCRIPT}"


def test_bridge_script_is_executable():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "src.skillpack.run_skill" in text, (
        "scripts/run_skill.py must delegate to src.skillpack.run_skill"
    )


@pytest.mark.subprocess
def test_list_skills_returns_valid_json():
    proc = run_bridge_subprocess(["--list-skills"])
    assert proc.returncode == 0, (
        f"--list-skills must exit 0, got {proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True, f"--list-skills must report ok=true, got {payload!r}"
    skills = payload.get("skills")
    assert isinstance(skills, list) and skills, (
        f"--list-skills must return a non-empty list, got {skills!r}"
    )
    runtime_ids = {entry.get("runtime_id") for entry in skills}
    for expected in [
        "fund_analysis",
        "news_research",
        "sentiment_analysis",
        "thesis_generation",
        "decision_support",
    ]:
        assert expected in runtime_ids, (
            f"--list-skills must list manifest runtime_id {expected!r}, got {runtime_ids!r}"
        )


@pytest.mark.subprocess
def test_list_skills_via_manifest_flag():
    proc = run_bridge_subprocess([
        "--manifest", "skillpack/fund-agent.skillpack.yaml",
        "--list-skills",
    ])
    assert proc.returncode == 0, (
        f"--manifest + --list-skills must exit 0, got {proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert isinstance(payload.get("skills"), list)


@pytest.mark.subprocess
def test_list_skills_pretty_output_is_valid_json():
    proc = run_bridge_subprocess(["--list-skills", "--pretty"])
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True


def test_fund_analysis_skill_runs_successfully():
    input_payload = {
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
                        "shares": 12345.67,
                        "target_weight": 0.12,
                        "tags": ["healthcare", "active"],
                    },
                ],
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
        }
    }
    payload = run_bridge_inprocess_json(skill="fund_analysis", input_data=input_payload)
    assert payload.get("ok") is True, f"bridge must report ok=true, got {payload!r}"
    assert payload.get("skill_name") == "fund_analysis"
    assert payload.get("status") in {"OK", "PARTIAL", "FAILED"}, (
        f"status must be OK/PARTIAL/FAILED, got {payload.get('status')!r}"
    )
    for required in ("artifacts", "evidence_items", "warnings", "errors", "metadata"):
        assert required in payload, f"output must include {required!r}, got {list(payload.keys())!r}"


@pytest.mark.subprocess
def test_output_writes_json_file(tmp_path: Path):
    input_payload = {"payload": {"portfolio": None}}
    input_path = tmp_path / "in.json"
    output_path = tmp_path / "out.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = run_bridge_subprocess([
        "--skill", "fund_analysis",
        "--input", str(input_path),
        "--output", str(output_path),
    ])
    assert proc.returncode in (0, 2), (
        f"bridge must exit 0 (ok) or 2 (skill failed), got {proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    assert output_path.exists(), "--output must write a JSON file"
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written.get("skill_name") == "fund_analysis", (
        f"output file must include skill_name=fund_analysis, got {written!r}"
    )


@pytest.mark.subprocess
def test_pretty_output_still_valid_json(tmp_path: Path):
    input_payload = {
        "payload": {
            "portfolio": {
                "as_of_date": "2026-06-01",
                "total_value": 100000,
                "cash_available": 10000,
                "positions": [],
            },
            "risk_profile": {"risk_level": "moderate"},
            "constraints": {"min_trade_amount": 100, "forbidden_actions": []},
        }
    }
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = run_bridge_subprocess([
        "--skill", "fund_analysis",
        "--input", str(input_path),
        "--pretty",
    ])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert "\n" in proc.stdout, "--pretty output must contain newlines"


@pytest.mark.subprocess
def test_invalid_json_input_returns_bridge_error():
    proc = run_bridge_subprocess(["--skill", "fund_analysis", "--input", "NUL"])
    assert proc.returncode != 0, (
        f"invalid input must exit non-zero, got {proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    text = (proc.stdout or "").strip()
    if text:
        payload = json.loads(text)
        assert payload.get("ok") is False, (
            f"invalid input must report ok=false, got {payload!r}"
        )
        assert payload.get("error", {}).get("code") in {
            "INVALID_INPUT",
            "JSON_SERIALIZATION_FAILED",
        }


@pytest.mark.subprocess
def test_unknown_skill_returns_bridge_error(tmp_path: Path):
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps({"payload": {}}), encoding="utf-8")
    proc = run_bridge_subprocess(["--skill", "definitely_not_a_real_skill", "--input", str(input_path)])
    assert proc.returncode != 0, (
        f"unknown skill must exit non-zero, got {proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is False
    assert payload.get("error", {}).get("code") == "UNKNOWN_SKILL"


@pytest.mark.subprocess
def test_stdout_is_json_only_on_success():
    proc = run_bridge_subprocess(["--list-skills"])
    text = proc.stdout or ""
    stripped = text.strip()
    assert stripped, "stdout must not be empty on --list-skills"
    json.loads(stripped)
    for line in text.splitlines():
        assert not re.match(r"^(DEBUG|INFO|WARN|ERROR|TRACE)\b", line), (
            f"bridge must not write log lines to stdout: {line!r}"
        )
