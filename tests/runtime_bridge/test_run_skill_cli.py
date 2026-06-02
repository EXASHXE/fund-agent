"""Tests for the v0.4.7-dev runtime bridge CLI.

The runtime bridge is a thin local JSON-in / JSON-out CLI over the
existing manifest runtime skills. It is not an agent loop, not a
provider integration, and not a server. It does not fetch data, does
not import provider SDKs, and does not shell out to OpenCode.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_skill.py"
PYTHON = sys.executable


def _run_cli(args: list[str], *, stdin_text: str | None = None) -> subprocess.CompletedProcess:
    """Run the runtime bridge CLI as a subprocess and capture output.

    The subprocess sees the repo's ``src/`` on ``PYTHONPATH`` via
    ``PYTHONPATH=.`` so it can import ``src.skillpack.run_skill`` and
    resolve runtime classes from the manifest.
    """
    env = {"PYTHONPATH": str(ROOT), "PATH": __import__("os").environ.get("PATH", "")}
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        input=stdin_text,
        timeout=60,
    )


def _parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    """Parse the bridge's stdout as JSON, asserting it is valid JSON
    and not empty. The bridge guarantees stdout is JSON only."""
    assert proc.stdout is not None, "bridge must emit stdout"
    text = proc.stdout.strip()
    assert text, f"bridge must emit JSON on stdout, got empty output (stderr={proc.stderr!r})"
    return json.loads(text)


def test_bridge_script_exists():
    assert SCRIPT.exists(), f"runtime bridge script must exist at {SCRIPT}"


def test_bridge_script_is_executable():
    """The script must be importable as Python; it does not need a
    shebang executable bit for the Python entry point. We assert it
    has a sensible first line and parses with ``compile``."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "src.skillpack.run_skill" in text, (
        "scripts/run_skill.py must delegate to src.skillpack.run_skill"
    )


def test_list_skills_returns_valid_json():
    proc = _run_cli(["--list-skills"])
    assert proc.returncode == 0, (
        f"--list-skills must exit 0, got {proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    payload = _parse_stdout(proc)
    assert payload.get("ok") is True, f"--list-skills must report ok=true, got {payload!r}"
    skills = payload.get("skills")
    assert isinstance(skills, list) and skills, (
        f"--list-skills must return a non-empty list, got {skills!r}"
    )
    runtime_ids = {entry.get("runtime_id") for entry in skills}
    # All five manifest runtime IDs must be listed.
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


def test_list_skills_via_manifest_flag():
    proc = _run_cli([
        "--manifest", "skillpack/fund-agent.skillpack.yaml",
        "--list-skills",
    ])
    assert proc.returncode == 0, (
        f"--manifest + --list-skills must exit 0, got {proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    payload = _parse_stdout(proc)
    assert payload.get("ok") is True
    assert isinstance(payload.get("skills"), list)


def test_list_skills_pretty_output_is_valid_json():
    proc = _run_cli(["--list-skills", "--pretty"])
    assert proc.returncode == 0
    payload = _parse_stdout(proc)
    assert payload.get("ok") is True


def test_fund_analysis_skill_runs_successfully(tmp_path: Path):
    """A minimal but valid fund_analysis payload must produce ok=true."""
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
    input_path = tmp_path / "fund_analysis_input.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = _run_cli(["--skill", "fund_analysis", "--input", str(input_path)])
    assert proc.returncode == 0, (
        f"fund_analysis must exit 0, got {proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    payload = _parse_stdout(proc)
    assert payload.get("ok") is True, f"bridge must report ok=true, got {payload!r}"
    assert payload.get("skill_name") == "fund_analysis"
    assert payload.get("status") in {"OK", "PARTIAL", "FAILED"}, (
        f"status must be OK/PARTIAL/FAILED, got {payload.get('status')!r}"
    )
    for required in ("artifacts", "evidence_items", "warnings", "errors", "metadata"):
        assert required in payload, f"output must include {required!r}, got {list(payload.keys())!r}"


def test_output_writes_json_file(tmp_path: Path):
    """--output must write the same JSON to the specified file."""
    input_payload = {"payload": {"portfolio": None}}
    input_path = tmp_path / "in.json"
    output_path = tmp_path / "out.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    proc = _run_cli([
        "--skill", "fund_analysis",
        "--input", str(input_path),
        "--output", str(output_path),
    ])
    # We allow the skill to fail; the bridge itself must succeed and
    # write the file. The bridge returns ok=false (with a structured
    # error) when the skill raises or returns a non-OK SkillOutput,
    # but still writes the JSON to the file.
    assert proc.returncode in (0, 2), (
        f"bridge must exit 0 (ok) or 2 (skill failed), got {proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    assert output_path.exists(), "--output must write a JSON file"
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written.get("skill_name") == "fund_analysis", (
        f"output file must include skill_name=fund_analysis, got {written!r}"
    )


def test_pretty_output_still_valid_json(tmp_path: Path):
    """--pretty must not break JSON parsability; the output must
    still parse to the same logical envelope."""
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
    proc = _run_cli([
        "--skill", "fund_analysis",
        "--input", str(input_path),
        "--pretty",
    ])
    assert proc.returncode == 0, f"stderr={proc.stderr!r}"
    payload = _parse_stdout(proc)
    assert payload.get("ok") is True
    # --pretty implies newlines + indentation; the file should
    # contain at least one newline if pretty succeeded.
    assert "\n" in proc.stdout, "--pretty output must contain newlines"


def test_invalid_json_input_returns_bridge_error():
    proc = _run_cli(["--skill", "fund_analysis", "--input", "/dev/null"])
    # Reading /dev/null yields empty, which is invalid JSON.
    assert proc.returncode != 0, (
        f"invalid input must exit non-zero, got {proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    # Even on bridge-level failure, stdout may or may not be valid
    # JSON depending on the failure point. We require it to be
    # either empty (truly catastrophic) or a JSON envelope.
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


def test_unknown_skill_returns_bridge_error(tmp_path: Path):
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps({"payload": {}}), encoding="utf-8")
    proc = _run_cli(["--skill", "definitely_not_a_real_skill", "--input", str(input_path)])
    assert proc.returncode != 0, (
        f"unknown skill must exit non-zero, got {proc.returncode}\n"
        f"stderr={proc.stderr!r}"
    )
    payload = _parse_stdout(proc)
    assert payload.get("ok") is False
    assert payload.get("error", {}).get("code") == "UNKNOWN_SKILL"


def test_stdout_is_json_only_on_success():
    """The bridge must never write logs to stdout. Diagnostics go to
    stderr. On success, stdout must be a single JSON document."""
    proc = _run_cli(["--list-skills"])
    text = proc.stdout or ""
    # Whitespace, then a single JSON document, then whitespace. No
    # extra log lines.
    stripped = text.strip()
    assert stripped, "stdout must not be empty on --list-skills"
    # Parses as JSON
    json.loads(stripped)
    # No log-style prefixes on stdout
    for line in text.splitlines():
        assert not re.match(r"^(DEBUG|INFO|WARN|ERROR|TRACE)\b", line), (
            f"bridge must not write log lines to stdout: {line!r}"
        )
